"""Supabase Auth: verify the ``Authorization: Bearer <jwt>`` and expose the
verified user to routers.

Identity now comes from the token, not the request body (see backend/CLAUDE.md
"Auth"). Supabase signs the access token with the project's JWT secret
(HS256); we verify it locally with that secret -- no network round-trip per
request, and no parallel users table.

Two dependencies gate protected routes:
  * ``require_user``  -- any authenticated user (client endpoints).
  * ``require_owner`` -- the owner role (owner endpoints).

Roles are engine-neutral strings ("owner"/"client"), mirroring the frontend's
``roleOf`` and the backend's existing ``actor: "owner"`` concept. They are only
*labelled* via ``terms.admin`` / ``terms.client`` in user-facing messages.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import get_config

logger = logging.getLogger(__name__)

# Engine-neutral role identifiers (not domain vocabulary -- these are the same
# internal tokens the router already uses for `actor`). Labels come from config.
OWNER_ROLE = "owner"
CLIENT_ROLE = "client"

# Supabase's default audience claim for a signed-in user.
_AUDIENCE = "authenticated"

# auto_error=False so we raise our own 401 (not FastAPI's default 403) when the
# header is missing, and still advertise Bearer auth in the OpenAPI schema.
_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: str  # Supabase `sub` -> auth.users.id
    email: str | None
    role: str  # engine role: OWNER_ROLE | CLIENT_ROLE
    token: str  # the raw JWT, for building an RLS-scoped client (get_user_client)
    claims: dict

    @property
    def is_owner(self) -> bool:
        return self.role == OWNER_ROLE


def _resolve_role(sub: str, email: str | None, token_role: str) -> str:
    """The user's *trusted* engine role, read from the `profiles` table (the
    same source `is_owner()` uses in RLS, so backend and DB agree).

    `profiles.role` is admin-controllable, which is what closes the "role is
    self-asserted in the token" gap. On first sight of a user we seed their
    profile from the sign-up role (`token_role`) — insert-if-missing only, so a
    later admin change is never clobbered — which also makes profiles reliably
    populated even if the DB trigger was skipped for lack of privilege.

    Resilient: if the DB / `profiles` table is unavailable (e.g. offline tests,
    schema not applied), fall back to the token role rather than failing auth."""
    try:
        from app.db import get_supabase, maybe_row

        client = get_supabase()
        row = maybe_row(client.table("profiles").select("role").eq("id", sub))
        if row and row.get("role"):
            return row["role"]
        try:
            client.table("profiles").insert(
                {"id": sub, "email": email, "role": token_role}
            ).execute()
        except Exception:
            pass  # concurrent request already seeded it — fine
        return token_role
    except Exception:
        logger.warning(
            "profiles role lookup unavailable; using self-asserted token role.",
            exc_info=False,
        )
        return token_role


def _engine_role(claims: dict) -> str:
    """The engine role carried by the token. Prefer ``app_metadata.role`` (set
    server-side, trustworthy) and fall back to ``user_metadata.role`` (what the
    sign-up form sets). Anything else -- including no role -- is a client.

    Note: the top-level ``role`` claim is Postgres' "authenticated"/"anon", not
    our engine role, so we deliberately read from the metadata objects."""
    app_meta = claims.get("app_metadata") or {}
    user_meta = claims.get("user_metadata") or {}
    raw = app_meta.get("role") or user_meta.get("role")
    return OWNER_ROLE if raw == OWNER_ROLE else CLIENT_ROLE


def _jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        # Misconfiguration, not a client error: fail loud rather than letting
        # every request through unverified.
        raise HTTPException(500, "Auth is not configured: SUPABASE_JWT_SECRET is unset.")
    return secret


@lru_cache
def _jwks_client() -> PyJWKClient:
    """Cached client for the project's JSON Web Key Set — the public keys that
    verify asymmetric (ES256/RS256) access tokens. Supabase's newer projects
    sign with rotating asymmetric keys (a `kid` in the header) rather than the
    legacy HS256 shared secret; this fetches the matching public key by `kid`.

    `lifespan` bounds how long a fetched JWK set is trusted before a refetch, so
    a rotated key is eventually picked up on its own; `_decode_asymmetric` also
    forces a refresh on a verification failure for immediate recovery."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", lifespan=300)


def _decode_asymmetric(token: str, alg: str, *, refresh: bool = True) -> dict:
    """Verify an ES256/RS256 token against the project's JWKS. On a key/signature
    failure, drop the cached JWK set and retry once — this recovers from a stale
    cache after Supabase rotates its signing keys, which would otherwise 401
    perfectly valid tokens until the process restarts. A genuinely bad token
    fails the retry too and still raises."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=[alg], audience=_AUDIENCE)
    except (jwt.PyJWKClientError, jwt.InvalidSignatureError):
        if refresh:
            _jwks_client.cache_clear()  # next call rebuilds the client + refetches the JWK set
            return _decode_asymmetric(token, alg, refresh=False)
        raise


def _decode_token(token: str) -> dict:
    """Verify a Supabase access token, supporting both signing schemes:
    asymmetric (ES256/RS256 via JWKS, keyed by `kid`) and the legacy symmetric
    HS256 (SUPABASE_JWT_SECRET). The token header's `alg` selects the path."""
    alg = jwt.get_unverified_header(token).get("alg", "HS256")
    if alg == "HS256":
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"], audience=_AUDIENCE)
    return _decode_asymmetric(token, alg)


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """Verify the bearer token and return the authenticated user. 401 on a
    missing/invalid/expired token."""
    if creds is None or not creds.credentials:
        raise HTTPException(401, "Missing bearer token.")
    try:
        claims = _decode_token(creds.credentials)
    except jwt.PyJWKClientError:
        raise HTTPException(401, "Could not resolve the token's signing key.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token.")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(401, "Token is missing a subject (sub) claim.")
    email = claims.get("email")
    return AuthUser(
        id=sub,
        email=email,
        role=_resolve_role(sub, email, _engine_role(claims)),
        token=creds.credentials,
        claims=claims,
    )


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser | None:
    """Like ``require_user`` but never raises: returns the verified user when a
    valid token is present, else ``None``. For public reads (discovery) that
    still want to personalise when signed in — e.g. pinning followed providers
    to the top of search."""
    if creds is None or not creds.credentials:
        return None
    try:
        return require_user(creds)
    except HTTPException:
        return None


def require_owner(user: AuthUser = Depends(require_user)) -> AuthUser:
    """Gate owner-only endpoints. 403 for an authenticated non-owner."""
    if not user.is_owner:
        admin = get_config()["terms"]["admin"]
        raise HTTPException(403, f"{admin} access is required for this action.")
    return user


def enforce_rls_write(data, *, entity: str = "record"):
    """Raise 403 when an RLS-scoped write returns no rows. The in-router checks
    should have already authorized the caller, so an empty result means the
    database's Row Level Security refused the write — surface that as a clear
    403 instead of a silent empty 200."""
    if not data:
        raise HTTPException(
            403, f"Not permitted: row-level security denied this {entity} write."
        )
    return data
