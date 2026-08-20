"""End-to-end verification of `app/auth.py` — the real thing, not the stub.

Every other module in this suite installs the `auth` fixture, which overrides
the `require_user` / `optional_user` FastAPI dependencies so a test can run "as"
a chosen user. That is the right trade for router tests, but it means the token
verification itself — signature, expiry, audience, algorithm selection, JWKS
rotation — and the trusted-role resolution were never executed by a test.

This module deliberately does NOT use the `auth` fixture. It mints real JWTs
locally, signed with a generated EC keypair served through a stubbed JWKS
endpoint — the same shape the live Supabase project issues (ES256 with a `kid`)
— and drives `app.auth` directly, plus a handful of requests through
`TestClient` with a genuine `Authorization` header.

The legacy symmetric HS256 scheme has been removed; `TestRetiredHs256Scheme`
below is the regression guard that it stays removed.

Nothing here touches the network: the JWKS client is replaced with a fake, and
`profiles` lives in the in-memory `FakeSupabase` from the `db` fixture.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

import app.auth as auth_mod
from app.auth import (
    CLIENT_ROLE,
    OWNER_ROLE,
    AuthUser,
    _engine_role,
    _resolve_role,
    enforce_rls_write,
    optional_user,
    require_owner,
    require_user,
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

AUDIENCE = "authenticated"
SUB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
EMAIL = "person@example.com"
KID = "test-signing-key"

# The real factory, captured before any test swaps in a fake, so the
# missing-SUPABASE_URL test can exercise the genuine one.
_REAL_JWKS_FACTORY = auth_mod._jwks_client


# --- signing keys -----------------------------------------------------------


@pytest.fixture(scope="session")
def ec_key():
    """One P-256 keypair for the whole session — this is what Supabase uses."""
    private = ec.generate_private_key(ec.SECP256R1())
    return private, private.public_key()


@pytest.fixture(scope="session")
def rsa_key():
    """RSA is the other shape a Supabase signing key can take (RS256)."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


# --- fake JWKS --------------------------------------------------------------


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKSClient:
    """Stands in for `PyJWKClient` — no network. `fail_times` makes the first N
    lookups raise, to exercise the rotate-and-retry path."""

    def __init__(self, key, *, fail_times: int = 0, error=None):
        self.key = key
        self.fail_times = fail_times
        self.error = error or jwt.PyJWKClientError("no signing key for kid")
        self.lookups = 0

    def get_signing_key_from_jwt(self, token):
        self.lookups += 1
        if self.lookups <= self.fail_times:
            raise self.error
        return _FakeSigningKey(self.key)


def install_jwks(monkeypatch, jwks_client) -> dict:
    """Replace `_jwks_client` (an lru_cache'd factory) with a fake that records
    how often the cache was cleared, so the rotation retry is observable."""
    state = {"builds": 0, "cleared": 0}

    def factory():
        state["builds"] += 1
        return jwks_client

    factory.cache_clear = lambda: state.__setitem__("cleared", state["cleared"] + 1)
    monkeypatch.setattr(auth_mod, "_jwks_client", factory)
    return state


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch, ec_key):
    """Serve the session public key from a stubbed JWKS, and keep the module's
    process-global state clean — `_role_cache` and the JWKS `lru_cache` would
    otherwise leak a cached role or key set between tests.

    `SUPABASE_JWT_SECRET` is deliberately set to a plausible value: nothing may
    read it any more, and several tests below prove it.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "legacy-secret-that-must-be-ignored")
    auth_mod._role_cache.clear()
    getattr(auth_mod._jwks_client, "cache_clear", lambda: None)()
    _, public = ec_key
    install_jwks(monkeypatch, _FakeJWKSClient(public))
    yield
    auth_mod._role_cache.clear()
    getattr(auth_mod._jwks_client, "cache_clear", lambda: None)()


# --- token helpers ----------------------------------------------------------


def claims_for(
    *,
    sub: str | None = SUB,
    email: str | None = EMAIL,
    aud: str | None = AUDIENCE,
    exp_delta: int = 3600,
    iat_delta: int = 0,
    user_role: str | None = None,
    app_role: str | None = None,
) -> dict:
    """A Supabase-shaped claim set. `role: "authenticated"` at the top level is
    Postgres' role, exactly as Supabase stamps it — the engine role lives in the
    metadata objects."""
    now = int(time.time())
    payload: dict = {"iat": now + iat_delta, "exp": now + exp_delta, "role": "authenticated"}
    if sub is not None:
        payload["sub"] = sub
    if email is not None:
        payload["email"] = email
    if aud is not None:
        payload["aud"] = aud
    if user_role is not None:
        payload["user_metadata"] = {"role": user_role}
    if app_role is not None:
        payload["app_metadata"] = {"role": app_role}
    return payload


def make_token(ec_key, *, key=None, alg: str = "ES256", kid: str = KID, **claim_kwargs) -> str:
    """An access token in the project's real shape: asymmetric, with a `kid`."""
    private, _ = ec_key
    return jwt.encode(
        claims_for(**claim_kwargs),
        key if key is not None else private,
        algorithm=alg,
        headers={"kid": kid},
    )


def creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64json(obj: dict) -> str:
    return _b64(json.dumps(obj, separators=(",", ":")).encode())


def unsigned_token(alg: str = "none") -> str:
    """A hand-built token with no signature — the classic `alg: none` forgery."""
    header = _b64json({"alg": alg, "typ": "JWT"})
    payload = _b64json(claims_for(app_role="owner"))
    return f"{header}.{payload}."


def hs256_signed_with(key: bytes | str, claims: dict | None = None) -> str:
    """An HS256 token signed with an arbitrary key, built by hand because PyJWT
    refuses to encode some of these — the attacker is not using PyJWT."""
    if isinstance(key, str):
        key = key.encode()
    header = _b64json({"alg": "HS256", "typ": "JWT"})
    payload = _b64json(claims if claims is not None else claims_for())
    signing_input = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_b64(hmac.new(key, signing_input, hashlib.sha256).digest())}"


# --- the asymmetric path (the only one) -------------------------------------


class TestAsymmetricTokens:
    def test_valid_es256_token_yields_the_user(self, db, ec_key):
        user = require_user(creds(make_token(ec_key)))
        assert isinstance(user, AuthUser)
        assert user.id == SUB
        assert user.email == EMAIL
        assert user.token  # kept for building an RLS-scoped client

    def test_rs256_is_also_accepted(self, monkeypatch, db, rsa_key):
        """A Supabase project whose signing key is RSA rather than ECC."""
        private, public = rsa_key
        install_jwks(monkeypatch, _FakeJWKSClient(public))
        token = jwt.encode(claims_for(), private, algorithm="RS256", headers={"kid": KID})
        assert require_user(creds(token)).id == SUB

    def test_missing_header_is_401(self):
        with pytest.raises(HTTPException) as exc:
            require_user(None)
        assert exc.value.status_code == 401

    def test_empty_credentials_are_401(self):
        with pytest.raises(HTTPException) as exc:
            require_user(creds(""))
        assert exc.value.status_code == 401

    def test_garbage_token_is_401(self):
        with pytest.raises(HTTPException) as exc:
            require_user(creds("not-a-jwt"))
        assert exc.value.status_code == 401

    def test_foreign_signing_key_is_rejected(self, db, ec_key):
        attacker = ec.generate_private_key(ec.SECP256R1())
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, key=attacker)))
        assert exc.value.status_code == 401

    def test_expired_token_is_rejected(self, db, ec_key):
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, exp_delta=-3600, iat_delta=-7200)))
        assert exc.value.status_code == 401

    def test_wrong_audience_is_rejected(self, db, ec_key):
        """A token minted for another audience must not authenticate here."""
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, aud="some-other-app")))
        assert exc.value.status_code == 401

    def test_token_without_sub_is_rejected(self, db, ec_key):
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, sub=None)))
        assert exc.value.status_code == 401
        assert "sub" in exc.value.detail

    def test_clock_skew_within_leeway_is_accepted(self, db, ec_key):
        """Supabase stamps `iat` from its own clock; a token issued a few seconds
        "in the future" is the login-then-/me sequence, not an attack."""
        assert require_user(creds(make_token(ec_key, iat_delta=30))).id == SUB

    def test_clock_skew_beyond_leeway_is_rejected(self, db, ec_key):
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, iat_delta=600, exp_delta=7200)))
        assert exc.value.status_code == 401

    def test_email_is_optional(self, db, ec_key):
        assert require_user(creds(make_token(ec_key, email=None))).email is None

    def test_unset_supabase_url_is_a_500_not_an_open_door(self, monkeypatch, db, ec_key):
        """SUPABASE_URL is now the single auth-critical env var — it locates the
        JWKS. A misconfigured deployment must fail loud, never let a request
        through unverified."""
        monkeypatch.setattr(auth_mod, "_jwks_client", _REAL_JWKS_FACTORY)
        _REAL_JWKS_FACTORY.cache_clear()
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        try:
            with pytest.raises(HTTPException) as exc:
                require_user(creds(make_token(ec_key)))
            assert exc.value.status_code == 500
        finally:
            # Unconditional: this is the one test that reaches the real, module
            # global lru_cache. Leaving a client cached from a failed run would
            # follow every later test into a cascade of unrelated failures.
            _REAL_JWKS_FACTORY.cache_clear()


# --- the retired HS256 scheme ------------------------------------------------


class TestRetiredHs256Scheme:
    """The legacy symmetric scheme is gone. Supporting it alongside JWKS meant
    the *token header* chose which scheme verified it, so a forger could always
    name the weaker one and reduce the problem to guessing a static secret.
    These are the regression guards that it does not come back."""

    def test_a_token_signed_with_the_old_secret_is_rejected(self, db):
        secret = "legacy-secret-that-must-be-ignored"  # the value _auth_env sets
        with pytest.raises(HTTPException) as exc:
            require_user(creds(hs256_signed_with(secret)))
        assert exc.value.status_code == 401

    def test_the_old_env_var_is_not_read_at_all(self, monkeypatch, db, ec_key):
        """Removing the var must change nothing: a good ES256 token still works
        and an HS256 one still fails."""
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        assert require_user(creds(make_token(ec_key))).id == SUB
        with pytest.raises(HTTPException) as exc:
            require_user(creds(hs256_signed_with("legacy-secret-that-must-be-ignored")))
        assert exc.value.status_code == 401

    def test_hs256_never_reaches_the_jwks(self, monkeypatch, db, ec_key):
        """An unsupported algorithm is refused before spending a JWKS lookup."""
        _, public = ec_key
        jwks = _FakeJWKSClient(public)
        install_jwks(monkeypatch, jwks)
        with pytest.raises(HTTPException):
            require_user(creds(hs256_signed_with("anything")))
        assert jwks.lookups == 0

    def test_public_key_cannot_be_used_as_an_hmac_secret(self, db, ec_key):
        """Algorithm confusion: take the public key the JWKS hands out and sign
        an HS256 token with it. With no symmetric path left there is nothing for
        this to land on."""
        _, public = ec_key
        pem = public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        forged = hs256_signed_with(pem, claims_for(app_role="owner"))
        with pytest.raises(HTTPException) as exc:
            require_user(creds(forged))
        assert exc.value.status_code == 401


class TestAlgorithmAllowList:
    def test_alg_none_is_rejected(self, db):
        """An unsigned token claiming `app_metadata.role: owner` must not
        authenticate, let alone gain owner access."""
        with pytest.raises(HTTPException) as exc:
            require_user(creds(unsigned_token()))
        assert exc.value.status_code == 401

    def test_a_missing_alg_header_is_rejected(self, db):
        header = _b64json({"typ": "JWT"})
        payload = _b64json(claims_for())
        with pytest.raises(HTTPException) as exc:
            require_user(creds(f"{header}.{payload}.x"))
        assert exc.value.status_code == 401

    @pytest.mark.parametrize("alg", ["HS384", "HS512", "none", "NONE", "ES256K"])
    def test_unsupported_algorithms_are_rejected(self, db, alg):
        header = _b64json({"alg": alg, "typ": "JWT"})
        payload = _b64json(claims_for(app_role="owner"))
        with pytest.raises(HTTPException) as exc:
            require_user(creds(f"{header}.{payload}.x"))
        assert exc.value.status_code == 401

    def test_the_allow_list_is_the_asymmetric_pair(self):
        assert auth_mod._ALLOWED_ALGS == ("ES256", "RS256")


class TestJwksRotation:
    def test_stale_jwks_is_refetched_once_after_rotation(self, monkeypatch, db, ec_key):
        """A rotated signing key must not 401 valid tokens until restart: the
        first lookup fails, the cache is dropped, the retry succeeds."""
        _, public = ec_key
        jwks = _FakeJWKSClient(public, fail_times=1)
        state = install_jwks(monkeypatch, jwks)
        assert require_user(creds(make_token(ec_key))).id == SUB
        assert state["cleared"] == 1
        assert jwks.lookups == 2

    def test_retry_is_bounded_to_one_attempt(self, monkeypatch, db, ec_key):
        """A genuinely unknown `kid` must give up, not loop refetching."""
        _, public = ec_key
        jwks = _FakeJWKSClient(public, fail_times=99)
        state = install_jwks(monkeypatch, jwks)
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key, kid="unknown")))
        assert exc.value.status_code == 401
        assert jwks.lookups == 2
        assert state["cleared"] == 1

    def test_an_unresolvable_key_is_401_not_500(self, monkeypatch, db, ec_key):
        _, public = ec_key
        install_jwks(monkeypatch, _FakeJWKSClient(public, fail_times=99))
        with pytest.raises(HTTPException) as exc:
            require_user(creds(make_token(ec_key)))
        assert exc.value.status_code == 401


# --- the engine role carried by the token ----------------------------------


class TestEngineRole:
    def test_app_metadata_role_wins(self):
        claims = {"app_metadata": {"role": "owner"}, "user_metadata": {"role": "client"}}
        assert _engine_role(claims) == OWNER_ROLE

    def test_user_metadata_is_the_fallback(self):
        assert _engine_role({"user_metadata": {"role": "owner"}}) == OWNER_ROLE

    def test_no_role_is_a_client(self):
        assert _engine_role({}) == CLIENT_ROLE
        assert _engine_role({"app_metadata": None, "user_metadata": None}) == CLIENT_ROLE

    def test_unknown_role_is_a_client(self):
        assert _engine_role({"app_metadata": {"role": "superuser"}}) == CLIENT_ROLE

    def test_postgres_role_claim_is_not_the_engine_role(self):
        """The top-level `role` claim is Postgres' "authenticated"; reading it as
        the engine role would make every signed-in user something other than a
        client. It must be ignored."""
        assert _engine_role({"role": "owner"}) == CLIENT_ROLE


# --- the trusted role, resolved from `profiles` ----------------------------


class TestTrustedRoleResolution:
    def test_profiles_row_overrides_a_self_asserted_owner_claim(self, db):
        """The escalation gap: `user_metadata` is user-writable, so a client can
        put `role: owner` in their own token. `profiles` is the trusted source
        and must win."""
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        assert _resolve_role(SUB, EMAIL, OWNER_ROLE) == CLIENT_ROLE

    def test_admin_promotion_in_profiles_is_honoured(self, db):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == OWNER_ROLE

    def test_first_sight_seeds_the_profile_from_the_token(self, db):
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == CLIENT_ROLE
        rows = db.rows("profiles")
        assert [(r["id"], r["role"]) for r in rows] == [(SUB, CLIENT_ROLE)]

    def test_seeding_never_clobbers_an_existing_role(self, db):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        _resolve_role(SUB, EMAIL, CLIENT_ROLE)
        assert db.rows("profiles")[0]["role"] == "owner"

    def test_db_outage_falls_back_to_the_token_role(self, monkeypatch):
        import app.db as app_db

        def _boom():
            raise RuntimeError("supabase unreachable")

        monkeypatch.setattr(app_db, "get_supabase", _boom)
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == CLIENT_ROLE

    def test_the_outage_fallback_is_never_cached(self, monkeypatch, db):
        """A transient outage must not pin a self-asserted role: the very next
        request has to re-check `profiles`."""
        import app.db as app_db

        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        real = app_db.get_supabase

        def _boom():
            raise RuntimeError("supabase unreachable")

        monkeypatch.setattr(app_db, "get_supabase", _boom)
        assert _resolve_role(SUB, EMAIL, OWNER_ROLE) == OWNER_ROLE  # self-asserted
        monkeypatch.setattr(app_db, "get_supabase", real)
        assert _resolve_role(SUB, EMAIL, OWNER_ROLE) == CLIENT_ROLE  # re-checked


class TestRoleCache:
    @pytest.fixture
    def clock(self, monkeypatch):
        state = {"t": 1000.0}
        monkeypatch.setattr(auth_mod.time, "monotonic", lambda: state["t"])
        return state

    def test_repeat_lookups_inside_the_ttl_are_served_from_cache(self, db, clock):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == CLIENT_ROLE
        db.rows("profiles")[0]["role"] = "owner"
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == CLIENT_ROLE

    def test_the_ttl_expires_so_a_demotion_takes_effect(self, db, clock):
        """Owner gating trusts this value, so the window in which a revoked owner
        keeps access must actually close."""
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == OWNER_ROLE
        db.rows("profiles")[0]["role"] = "client"
        clock["t"] += auth_mod._ROLE_TTL_SECONDS + 0.1
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == CLIENT_ROLE

    def test_users_do_not_share_a_cache_entry(self, db, clock):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        db.insert_row("profiles", id=OTHER_SUB, email="other@example.com", role="client")
        assert _resolve_role(SUB, EMAIL, CLIENT_ROLE) == OWNER_ROLE
        assert _resolve_role(OTHER_SUB, "other@example.com", OWNER_ROLE) == CLIENT_ROLE

    def test_the_cache_stays_bounded(self, clock):
        for i in range(auth_mod._ROLE_CACHE_MAX + 500):
            auth_mod._cache_role(f"sub-{i}", CLIENT_ROLE, clock["t"])
        assert len(auth_mod._role_cache) <= auth_mod._ROLE_CACHE_MAX


# --- gating ----------------------------------------------------------------


class TestGating:
    def test_owner_passes_require_owner(self, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        user = require_user(creds(make_token(ec_key, app_role="owner")))
        assert require_owner(user) is user

    def test_client_is_403_labelled_from_config(self, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        user = require_user(creds(make_token(ec_key)))
        with pytest.raises(HTTPException) as exc:
            require_owner(user)
        assert exc.value.status_code == 403
        assert "Manager" in exc.value.detail  # terms.admin from the fixture config

    def test_optional_user_is_none_without_a_header(self):
        assert optional_user(None) is None

    def test_optional_user_swallows_a_bad_token(self, db, ec_key):
        attacker = ec.generate_private_key(ec.SECP256R1())
        assert optional_user(creds("not-a-jwt")) is None
        assert optional_user(creds(make_token(ec_key, key=attacker))) is None
        assert optional_user(creds(hs256_signed_with("legacy-secret"))) is None

    def test_optional_user_returns_a_valid_user(self, db, ec_key):
        assert optional_user(creds(make_token(ec_key))).id == SUB


class TestEnforceRlsWrite:
    def test_empty_result_is_a_403(self):
        with pytest.raises(HTTPException) as exc:
            enforce_rls_write([], entity="booking")
        assert exc.value.status_code == 403
        assert "booking" in exc.value.detail

    def test_none_is_a_403(self):
        with pytest.raises(HTTPException) as exc:
            enforce_rls_write(None)
        assert exc.value.status_code == 403

    def test_rows_pass_through(self):
        rows = [{"id": "1"}]
        assert enforce_rls_write(rows) is rows


# --- through the app, with a real Authorization header ---------------------


class TestThroughTheApp:
    def test_protected_route_needs_a_token(self, client):
        assert client.get("/me").status_code == 401

    def test_protected_route_rejects_a_foreign_key(self, client, ec_key):
        attacker = ec.generate_private_key(ec.SECP256R1())
        forged = make_token(ec_key, key=attacker, app_role="owner")
        assert client.get("/me", headers=bearer(forged)).status_code == 401

    def test_protected_route_rejects_a_legacy_hs256_token(self, client):
        forged = hs256_signed_with("legacy-secret-that-must-be-ignored", claims_for(app_role="owner"))
        assert client.get("/me", headers=bearer(forged)).status_code == 401

    def test_protected_route_rejects_an_expired_token(self, client, ec_key):
        stale = make_token(ec_key, exp_delta=-60, iat_delta=-3600)
        assert client.get("/me", headers=bearer(stale)).status_code == 401

    def test_identity_comes_from_the_token(self, client, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        res = client.get("/me", headers=bearer(make_token(ec_key)))
        assert res.status_code == 200
        assert res.json()["email"] == EMAIL

    def test_a_self_asserted_owner_token_cannot_reach_owner_routes(self, client, db, ec_key):
        """The whole point of resolving the role from `profiles`: a client who
        writes `role: owner` into their own user_metadata still gets a 403."""
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        res = client.get("/owner/dashboard", headers=bearer(make_token(ec_key, user_role="owner")))
        assert res.status_code == 403

    def test_a_real_owner_reaches_owner_routes(self, client, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        res = client.get("/owner/dashboard", headers=bearer(make_token(ec_key, app_role="owner")))
        assert res.status_code == 200

    def test_me_role_reports_the_trusted_role(self, client, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        res = client.get("/me/role", headers=bearer(make_token(ec_key)))
        assert res.status_code == 200
        assert res.json() == {"role": "client"}

    def test_me_role_reports_owner_for_an_owner(self, client, db, ec_key):
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        res = client.get("/me/role", headers=bearer(make_token(ec_key, app_role="owner")))
        assert res.json() == {"role": "owner"}

    def test_me_role_follows_profiles_not_the_token(self, client, db, ec_key):
        """The endpoint exists so the frontend stops deriving the role from the
        JWT. A self-asserted `user_metadata.role: owner` must report `client`
        here — otherwise the UI would open business mode on a token claim the
        API then refuses, which is the exact divergence this closes."""
        db.insert_row("profiles", id=SUB, email=EMAIL, role="client")
        token = make_token(ec_key, user_role="owner")
        assert client.get("/me/role", headers=bearer(token)).json() == {"role": "client"}
        # ...and the two agree: the owner route refuses the same token.
        assert client.get("/owner/dashboard", headers=bearer(token)).status_code == 403

    def test_me_role_agrees_with_owner_gating(self, client, db, ec_key):
        """An admin promotion in `profiles` (the documented path) must show up
        here, so the UI grants business mode exactly when the API does."""
        db.insert_row("profiles", id=SUB, email=EMAIL, role="owner")
        token = make_token(ec_key)  # token carries NO owner claim at all
        assert client.get("/me/role", headers=bearer(token)).json() == {"role": "owner"}
        assert client.get("/owner/dashboard", headers=bearer(token)).status_code == 200

    def test_me_role_needs_a_token(self, client):
        assert client.get("/me/role").status_code == 401

    def test_anonymous_route_stays_public(self, client):
        assert client.get("/config").status_code == 200
        assert client.get("/health").status_code == 200
