# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Supabase Auth: verify the ``Authorization: Bearer <jwt>`` and expose the
verified user to routers.

Identity now comes from the token, not the request body (see backend/CLAUDE.md
"Auth"). Supabase signs the access token with a rotating **asymmetric** key and
publishes the matching public keys at the project's JWKS endpoint; we verify the
signature against those, keyed by the token header's `kid`. The key set is
cached, so the steady state is no network round-trip per request, and there is
no parallel users table.

Symmetric HS256 (the legacy shared `SUPABASE_JWT_SECRET`) is **not** accepted.
Supporting both meant the token header chose the scheme, so a forger could name
the weaker one and reduce the problem to guessing a static secret. Only the
algorithms in `_ALLOWED_ALGS` verify.

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
import time
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
# PyJWT checks `iat`/`nbf`/`exp` with zero tolerance, and Supabase stamps `iat`
# from its own clock. A sub-second difference between that clock and ours is
# enough to make a token the user has *just* been issued fail as
# `ImmatureSignatureError` ("not yet valid"), which is the login-then-/me
# sequence, so the symptom is a signed-in user whose profile will not load,
# clearing up on its own once the clocks converge. Leeway is what the claim is
# for: 60s absorbs ordinary skew without meaningfully extending a token's life
# (they last an hour).
_LEEWAY_SECONDS = 60

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


# Short-lived cache of the trusted engine role keyed by `sub`. Without it,
# _resolve_role hits Supabase (`profiles`) on EVERY authenticated request, a
# per-request internet round trip on the hot path of every page.
#
# The TTL is deliberately short: it exists to collapse the burst of requests a
# single page load fires, NOT to hold a role for minutes. Because owner gating
# (`require_owner`) trusts this value, a longer window would let a revoked/
# demoted owner keep owner-only access; a few seconds bounds that to roughly one
# page's worth of requests. Only roles actually read from `profiles` are cached
# (never the token fallback used on a DB outage), and the cache is size-bounded
# with expired entries purged, so it can't grow without limit.
_ROLE_TTL_SECONDS = 5.0
_ROLE_CACHE_MAX = 4096
_role_cache: dict[str, tuple[str, float]] = {}


def _cache_role(sub: str, role: str, now: float) -> None:
    """Store a resolved role, keeping the cache bounded: purge expired entries
    when it fills, and if it's still at the cap, evict the oldest one."""
    if len(_role_cache) >= _ROLE_CACHE_MAX:
        for key in [k for k, (_, ts) in _role_cache.items() if now - ts >= _ROLE_TTL_SECONDS]:
            del _role_cache[key]
        if len(_role_cache) >= _ROLE_CACHE_MAX:
            del _role_cache[min(_role_cache, key=lambda k: _role_cache[k][1])]
    _role_cache[sub] = (role, now)


def _resolve_role(sub: str, email: str | None, token_role: str) -> str:
    """The user's *trusted* engine role, read from the `profiles` table (the
    same source `is_owner()` uses in RLS, so backend and DB agree).

    `profiles.role` is admin-controllable, which is what closes the "role is
    self-asserted in the token" gap. On first sight of a user we seed their
    profile from the sign-up role (`token_role`), insert-if-missing only, so a
    later admin change is never clobbered, which also makes profiles reliably
    populated even if the DB trigger was skipped for lack of privilege.

    Cached per `sub` for `_ROLE_TTL_SECONDS` so a page's burst of requests
    doesn't each pay a `profiles` round trip. Only DB-resolved roles are cached;
    the token fallback below is returned but never cached, so a transient outage
    can't pin a self-asserted role. Resilient: if the DB / `profiles` table is
    unavailable (e.g. offline tests, schema not applied), fall back to the token
    role rather than failing auth."""
    now = time.monotonic()
    hit = _role_cache.get(sub)
    if hit is not None and (now - hit[1]) < _ROLE_TTL_SECONDS:
        return hit[0]
    role, cacheable = _resolve_role_uncached(sub, email, token_role)
    if cacheable:
        _cache_role(sub, role, now)
    return role


def _resolve_role_uncached(sub: str, email: str | None, token_role: str) -> tuple[str, bool]:
    """The uncached `profiles` lookup + seed-on-first-sight (see `_resolve_role`).

    Returns ``(role, cacheable)``. ``cacheable`` is False only for the token
    fallback used when `profiles` is unreachable, that self-asserted value must
    not be pinned in the cache, so it's re-checked on the very next request."""
    try:
        from app.db import get_supabase, maybe_row

        client = get_supabase()
        row = maybe_row(client.table("profiles").select("role").eq("id", sub))
        if row and row.get("role"):
            return row["role"], True
        try:
            client.table("profiles").insert(
                {"id": sub, "email": email, "role": token_role}
            ).execute()
        except Exception:
            pass  # concurrent request already seeded it, fine
        return token_role, True
    except Exception:
        logger.warning(
            "profiles role lookup unavailable; using self-asserted token role.",
            exc_info=False,
        )
        return token_role, False


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


# The only signatures we accept. Supabase signs with ECC P-256 (ES256) or RSA
# (RS256) depending on how the project's signing key was created; both arrive
# via JWKS with a `kid`. Pinning the list here is what makes the algorithm a
# server decision instead of an attacker-supplied token header.
_ALLOWED_ALGS = ("ES256", "RS256")


@lru_cache
def _jwks_client() -> PyJWKClient:
    """Cached client for the project's JSON Web Key Set, the public keys that
    verify the access tokens Supabase issues. The project signs with a rotating
    asymmetric key and names it in the token header's `kid`; this fetches the
    matching public key by that `kid`.

    `lifespan` bounds how long a fetched JWK set is trusted before a refetch, so
    a rotated key is eventually picked up on its own; `_decode_asymmetric` also
    forces a refresh on a verification failure for immediate recovery."""
    base = os.environ.get("SUPABASE_URL")
    if not base:
        # Misconfiguration, not a client error: fail loud rather than letting
        # every request through unverified.
        raise HTTPException(500, "Auth is not configured: SUPABASE_URL is unset.")
    return PyJWKClient(
        f"{base.rstrip('/')}/auth/v1/.well-known/jwks.json", lifespan=300
    )


def _decode_asymmetric(token: str, *, refresh: bool = True) -> dict:
    """Verify a token against the project's JWKS. On a key/signature failure,
    drop the cached JWK set and retry once, this recovers from a stale cache
    after Supabase rotates its signing keys, which would otherwise 401 perfectly
    valid tokens until the process restarts. A genuinely bad token fails the
    retry too and still raises.

    `algorithms` is the pinned allow-list, never the token's own header, so
    PyJWT enforces it a second time at the point of verification."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token, signing_key.key, algorithms=list(_ALLOWED_ALGS),
            audience=_AUDIENCE, leeway=_LEEWAY_SECONDS,
        )
    except (jwt.PyJWKClientError, jwt.InvalidSignatureError):
        if refresh:
            _jwks_client.cache_clear()  # next call rebuilds the client + refetches the JWK set
            return _decode_asymmetric(token, refresh=False)
        raise


def _decode_token(token: str) -> dict:
    """Verify a Supabase access token against the project's JWKS.

    The header's `alg` is checked against `_ALLOWED_ALGS` first so an
    unsupported one, `none`, or the retired HS256, is refused outright,
    without spending a JWKS lookup on it. There is no second scheme to fall
    back to: an algorithm we do not sign with is simply not a token we issued."""
    alg = jwt.get_unverified_header(token).get("alg")
    if alg not in _ALLOWED_ALGS:
        raise jwt.InvalidAlgorithmError(
            f"Unsupported token algorithm {alg!r}; "
            f"expected one of {', '.join(_ALLOWED_ALGS)}."
        )
    return _decode_asymmetric(token)


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
    still want to personalise when signed in, e.g. pinning followed providers
    to the top of search."""
    if creds is None or not creds.credentials:
        return None
    try:
        return require_user(creds)
    except HTTPException as exc:
        if exc.status_code != 401:
            # Only "this token isn't good" degrades to anonymous. A 500 means
            # auth is misconfigured (no SUPABASE_URL, so no JWKS to verify
            # against), swallowing that would serve every public read as
            # anonymous and let a broken deployment look healthy, which is the
            # opposite of the fail-loud the 500 exists for.
            raise
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
    database's Row Level Security refused the write, surface that as a clear
    403 instead of a silent empty 200."""
    if not data:
        raise HTTPException(
            403, f"Not permitted: row-level security denied this {entity} write."
        )
    return data
