"""Fixtures for the backend API suite.

Everything here is offline: no Supabase project, no network, no real
`domain.config.json` dependency. Three things get neutralised for every
test:

1. `app.db.get_supabase` (and the already-imported copies inside each
   router module — the routers do `from app.db import get_supabase`, so
   patching only `app.db` would be a no-op) -> an in-memory `FakeSupabase`.
2. The FastAPI startup hooks (`create_tables_if_configured`, `seed_if_empty`)
   -> no-ops, so `TestClient`'s lifespan never tries to reach Postgres.
3. `DOMAIN_CONFIG_PATH` -> a per-test copy of
   `test/fixtures/domain.config.test.json`, so rule values can be varied
   without touching the repo's real pivot file.

Both `lru_cache`s (`get_config`, `get_supabase`) are cleared around every
test so nothing leaks between them.
"""

from __future__ import annotations

import copy as _copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.config as app_config
import app.db as app_db
import app.schema_setup as app_schema_setup
import seed as seed_module
from app import main as app_main
from app.routers import bookings as bookings_router
from app.routers import resources as resources_router
from app.routers import slots as slots_router
from fakes import FakeSupabase

TEST_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TEST_DIR.parent
FIXTURE_CONFIG_PATH = TEST_DIR / "fixtures" / "domain.config.test.json"
REAL_CONFIG_PATH = REPO_ROOT / "domain.config.json"

ROUTER_MODULES = (bookings_router, resources_router, slots_router)


def _clear_caches() -> None:
    """Drop both lru_caches.

    Guarded with getattr: `_isolated_env` is autouse, so it is set up before
    the `db` fixture and torn down *after* it — at teardown time
    `app.db.get_supabase` may still be the monkeypatched plain function,
    which has no `cache_clear`.
    """
    for module, name in ((app_config, "get_config"), (app_db, "get_supabase")):
        getattr(getattr(module, name), "cache_clear", lambda: None)()


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Dummy credentials + clean caches around every test."""
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture(autouse=True)
def domain_config(tmp_path, monkeypatch):
    """Point DOMAIN_CONFIG_PATH at a writable fixture config.

    Returns a setter so a test can pivot the config mid-flight::

        domain_config(rules={"cancellationWindowHours": 2})
        domain_config(terms={"resource": "Doctor"}, domain="medical")
    """
    base = json.loads(FIXTURE_CONFIG_PATH.read_text())
    path = tmp_path / "domain.config.json"

    def _set(**sections) -> dict:
        config = _copy.deepcopy(base)
        for section, value in sections.items():
            if isinstance(value, dict) and isinstance(config.get(section), dict):
                config[section] = {**config[section], **value}
            else:
                config[section] = value
        path.write_text(json.dumps(config, indent=2))
        monkeypatch.setenv("DOMAIN_CONFIG_PATH", str(path))
        app_config.get_config.cache_clear()
        return config

    _set()  # default: the untouched fixture config
    return _set


@pytest.fixture
def use_real_config(monkeypatch):
    """Drop the fixture override so the repo's own domain.config.json loads."""
    monkeypatch.delenv("DOMAIN_CONFIG_PATH", raising=False)
    app_config.get_config.cache_clear()
    return REAL_CONFIG_PATH


@pytest.fixture
def db(monkeypatch) -> FakeSupabase:
    """In-memory Supabase, wired into `app.db` *and* every router module."""
    fake = FakeSupabase()
    _patch_supabase(monkeypatch, fake)
    return fake


@pytest.fixture
def strict_db(monkeypatch) -> FakeSupabase:
    """Same, but `.single()` on zero rows raises like real PostgREST."""
    fake = FakeSupabase(strict_single=True)
    _patch_supabase(monkeypatch, fake)
    return fake


def _patch_supabase(monkeypatch, fake: FakeSupabase) -> None:
    def _get_supabase():
        return fake

    # Keep the lru_cache surface so anything calling .cache_clear() on the
    # patched function (see _clear_caches) still works.
    _get_supabase.cache_clear = lambda: None

    monkeypatch.setattr(app_db, "get_supabase", _get_supabase)
    monkeypatch.setattr(seed_module, "get_supabase", _get_supabase)
    for module in ROUTER_MODULES:
        monkeypatch.setattr(module, "get_supabase", _get_supabase)


@pytest.fixture(autouse=True)
def _no_startup_io(monkeypatch):
    """Startup must never touch Postgres or seed demo data during tests."""
    monkeypatch.setattr(app_schema_setup, "create_tables_if_configured", lambda: None)
    monkeypatch.setattr(seed_module, "seed_if_empty", lambda: None)
    # main.py imported both names into its own namespace at import time.
    monkeypatch.setattr(app_main, "create_tables_if_configured", lambda: None)
    monkeypatch.setattr(app_main, "seed_if_empty", lambda: None)


@pytest.fixture
def client(db):
    """TestClient with lifespan run (proves the startup hooks are inert)."""
    with TestClient(app_main.app) as test_client:
        yield test_client


@pytest.fixture
def strict_client(strict_db):
    with TestClient(app_main.app) as test_client:
        yield test_client


@pytest.fixture
def raw_client(db):
    """TestClient that converts unhandled server exceptions into 500s
    instead of re-raising them — used to pin current crash behaviour."""
    with TestClient(app_main.app, raise_server_exceptions=False) as test_client:
        yield test_client
