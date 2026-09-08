# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Live auth verification against a running backend + the real Supabase project.

The offline suite (`test/backend/test_auth.py`) mints its own tokens and stubs
the JWKS endpoint. That covers the logic, but two things it *cannot* prove are
exactly the two that matter in production:

  * that the real project's tokens verify through the JWKS path, which is now
    the *only* path — the legacy HS256 shared-secret scheme has been removed, so
    if this deployment ever started issuing symmetric tokens every request would
    401. `test_the_live_project_signs_asymmetrically` is that canary;
  * whether Row Level Security is actually applied to the live database. The
    offline `FakeSupabase` returns the same store for the service client and the
    user client, so RLS is simulated by nothing at all. Slot writes in particular
    have **no router-level ownership check** — they rely entirely on the
    `slots_write_owner` policy — so RLS being live is load-bearing.

Read-only by design: these tests sign in and issue GETs. The single write is a
self-promotion attempt that is asserted to be *refused*, so a pass leaves the
project untouched. Skipped cleanly without live env, like the rest of `e2e`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import httpx
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

DEMO_EMAIL = os.environ.get("E2E_DEMO_EMAIL", "demo@codaro.app")
DEMO_PASSWORD = os.environ.get("E2E_DEMO_PASSWORD", "Codaro-Demo-2026")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (SUPABASE_URL and SUPABASE_ANON_KEY),
        reason="set SUPABASE_URL and SUPABASE_ANON_KEY to run live stack tests",
    ),
]


def _decode_segment(token: str, index: int) -> dict:
    part = token.split(".")[index]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def _b64(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def token() -> str:
    resp = httpx.post(
        f"{SUPABASE_URL.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=20.0,
    )
    if resp.status_code != 200:
        pytest.skip(f"demo sign-in failed ({resp.status_code}): {resp.text[:200]}")
    tok = resp.json().get("access_token")
    if not tok:
        pytest.skip("no access_token in the sign-in response")
    return tok


@pytest.fixture(scope="module")
def claims(token) -> dict:
    return _decode_segment(token, 1)


@pytest.fixture(scope="module")
def api(token) -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=20.0) as client:
        try:
            client.get("/health")
        except httpx.HTTPError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"backend not reachable at {BASE_URL}: {exc}")
        yield client


@pytest.fixture(scope="module")
def auth_headers(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def user_headers(token) -> dict:
    """Postgrest headers a browser would send: anon apikey + the user's JWT."""
    return {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}


# --- the token the real project issues --------------------------------------


def test_the_live_project_signs_asymmetrically(token):
    """The backend accepts only `_ALLOWED_ALGS`. If the project were ever
    reconfigured to sign symmetrically, every request would 401 — so assert the
    live tokens still match what the verifier will take."""
    header = _decode_segment(token, 0)
    assert header["alg"] in ("ES256", "RS256"), header
    assert header.get("kid"), "asymmetric tokens must carry a kid for JWKS lookup"


def test_a_legacy_hs256_token_is_refused(api, claims):
    """The retired scheme, end to end: an HS256 token carrying the real claims
    and an escalated role. Hand-signed, since PyJWT will not encode some of
    these. No secret guess can matter — there is no symmetric path left."""
    forged_claims = {**claims, "app_metadata": {**(claims.get("app_metadata") or {}), "role": "owner"}}
    header = _b64({"alg": "HS256", "typ": "JWT"})
    payload = _b64(forged_claims)
    signing_input = f"{header}.{payload}".encode()
    for secret in ("super-secret-jwt-token-with-at-least-32-characters-long", "", "secret"):
        sig = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        res = api.get("/me", headers={"Authorization": f"Bearer {header}.{payload}.{sig}"})
        assert res.status_code == 401, f"HS256 accepted with secret {secret!r}"


def test_audience_is_authenticated(claims):
    assert claims["aud"] == "authenticated"


# --- verification ------------------------------------------------------------


def test_a_real_token_authenticates(api, auth_headers):
    assert api.get("/me", headers=auth_headers).status_code == 200


def test_identity_comes_from_the_token(api, auth_headers):
    body = api.get("/me", headers=auth_headers).json()
    assert body["email"] == DEMO_EMAIL


def test_no_token_is_401(api):
    assert api.get("/me").status_code == 401


def test_garbage_token_is_401(api):
    assert api.get("/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_tampered_signature_is_401(api, token):
    """Flip a bit in the signature *bytes*, not in its base64 text.

    An ES256 signature is 64 bytes, and 64 = 21*3 + 1 — so the final base64
    character carries only 2 significant bits and its low 4 bits are padding a
    decoder throws away. Editing that last character therefore decodes to the
    identical signature perhaps half the time, and the request is legitimately
    accepted. Mutating a decoded byte is deterministic.
    """
    body, sig = token.rsplit(".", 1)
    raw = bytearray(base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4)))
    raw[0] ^= 0x01
    flipped = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
    assert flipped != sig
    res = api.get("/me", headers={"Authorization": f"Bearer {body}.{flipped}"})
    assert res.status_code == 401


def test_alg_none_forgery_claiming_owner_is_401(api, claims):
    """Replay the real claims unsigned, with the engine role escalated."""
    forged_claims = {**claims, "app_metadata": {**(claims.get("app_metadata") or {}), "role": "owner"}}
    forged = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(forged_claims)}."
    assert api.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# --- gating ------------------------------------------------------------------


def test_owner_routes_require_a_token(api):
    assert api.get("/owner/dashboard").status_code == 401


def test_owner_routes_are_role_gated(api, auth_headers, user_headers, claims):
    """The demo user's trusted role decides this, and `profiles` is that truth —
    so assert against `profiles`, not against the token's metadata."""
    rows = httpx.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/profiles",
        params={"select": "role", "id": f"eq.{claims['sub']}"},
        headers=user_headers,
        timeout=20.0,
    ).json()
    trusted = rows[0]["role"] if rows else "client"
    expected = 200 if trusted == "owner" else 403
    assert api.get("/owner/dashboard", headers=auth_headers).status_code == expected


@pytest.mark.parametrize("path", ["/health", "/config", "/providers", "/services", "/slots"])
def test_public_reads_stay_public(api, path):
    assert api.get(path).status_code == 200


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/slots", {"resourceId": "x"}),
        ("post", "/bookings", {}),
        ("post", "/providers", {"name": "x"}),
        ("post", "/config/reload", None),
    ],
)
def test_writes_reject_anonymous_callers(api, method, path, body):
    res = getattr(api, method)(path, json=body) if body is not None else getattr(api, method)(path)
    assert res.status_code == 401


# --- Row Level Security is actually on ---------------------------------------


def test_rls_limits_profiles_to_the_caller(user_headers, claims):
    res = httpx.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/profiles",
        params={"select": "id,role"},
        headers=user_headers,
        timeout=20.0,
    )
    assert res.status_code == 200
    assert [r["id"] for r in res.json()] in ([], [claims["sub"]])


def test_rls_refuses_self_promotion(user_headers, claims):
    """`profiles` is the trusted role source, so a user writing their own row
    would be straight privilege escalation. No update policy exists; the write
    must affect nothing."""
    res = httpx.patch(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/profiles",
        params={"id": f"eq.{claims['sub']}"},
        headers={**user_headers, "Content-Type": "application/json", "Prefer": "return=representation"},
        json={"role": "owner"},
        timeout=20.0,
    )
    assert res.status_code != 200 or res.json() == []


def test_rls_limits_bookings_to_the_caller(user_headers, claims):
    res = httpx.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/bookings",
        params={"select": "id,client_id"},
        headers=user_headers,
        timeout=20.0,
    )
    assert res.status_code == 200
    foreign = [r for r in res.json() if r.get("client_id") != claims["sub"]]
    assert not foreign, f"{len(foreign)} booking(s) leaked to the wrong user"


def test_rls_hides_bookings_from_the_anon_key(user_headers):
    res = httpx.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/bookings",
        params={"select": "id"},
        headers={"apikey": SUPABASE_ANON_KEY},
        timeout=20.0,
    )
    assert res.status_code != 200 or res.json() == []
