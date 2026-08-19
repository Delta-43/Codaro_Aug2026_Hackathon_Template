"""Frontend <-> backend contract, checked statically (no browser, no network).

`frontend/src/api/index.ts` is the only place the UI talks to the API and
`frontend/src/api/errors.ts` / `frontend/src/types/domain.ts` define the shapes
it expects. These tests parse those files and assert:

* every path the client calls exists on the FastAPI app (a route rename can't
  silently break the UI);
* the ApiError code union matches the backend's `app.errors`;
* `GET /config` still exposes the sections `DomainConfig` consumes.

This is the CI-friendly half of the stack check; the network version lives in
`test/e2e/` behind `SUPABASE_URL`/`SUPABASE_ANON_KEY`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import errors as app_errors
from app import main as app_main

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TS = REPO_ROOT / "frontend" / "src" / "api" / "index.ts"
ERRORS_TS = REPO_ROOT / "frontend" / "src" / "api" / "errors.ts"
DOMAIN_TS = REPO_ROOT / "frontend" / "src" / "types" / "domain.ts"

TEMPLATE_EXPR = re.compile(r"\$\{[^{}]*\}")
PATH_LITERAL = re.compile(r"[`\"'](/(?:config|providers|services|resources|slots|bookings|availability|month-density|me|demo|conversations|owner)[^`\"'\n]*)")


def normalize(path: str) -> str:
    path = TEMPLATE_EXPR.sub("*", path)
    for cut in ("$", "?", "`"):
        index = path.find(cut)
        if index != -1:
            path = path[:index]
    path = path.rstrip("/")
    return path or "/"


def app_paths() -> set[str]:
    paths: set[str] = set()
    for path in app_main.app.openapi()["paths"]:
        paths.add(re.sub(r"\{[^}]*\}", "*", path).rstrip("/") or "/")
    return paths


def frontend_paths() -> set[str]:
    found: set[str] = set()
    for raw in PATH_LITERAL.findall(API_TS.read_text()):
        candidate = normalize(raw)
        if candidate != "/":
            found.add(candidate)
    return found


def test_frontend_sources_exist():
    assert API_TS.is_file(), f"missing {API_TS}"
    assert ERRORS_TS.is_file(), f"missing {ERRORS_TS}"
    assert DOMAIN_TS.is_file(), f"missing {DOMAIN_TS}"


def test_frontend_calls_at_least_the_core_paths():
    """The api seam must reference these routes (sanity that the parser works)."""
    found = frontend_paths()
    for expected in ("/providers", "/services", "/resources", "/bookings", "/availability", "/me"):
        assert expected in found, f"api/index.ts no longer calls {expected}?"


def test_no_frontend_path_is_unknown_to_the_backend():
    unknown = frontend_paths() - app_paths()
    assert not unknown, f"frontend calls paths the backend does not serve: {sorted(unknown)}"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/config"),
        ("GET", "/providers"),
        ("GET", "/providers/*"),
        ("GET", "/providers/by-code/*"),
        ("POST", "/providers/*/follow"),
        ("POST", "/providers/*/unfollow"),
        ("GET", "/services"),
        ("GET", "/services/*"),
        ("GET", "/resources"),
        ("GET", "/availability"),
        ("GET", "/month-density"),
        ("GET", "/bookings"),
        ("POST", "/bookings"),
        ("GET", "/bookings/*"),
        ("POST", "/bookings/*/cancel"),
        ("POST", "/bookings/*/reschedule"),
        ("POST", "/bookings/*/review"),
        ("GET", "/me"),
        ("PATCH", "/me"),
        ("GET", "/vertical"),
        ("GET", "/conversations"),
        ("POST", "/conversations"),
        ("POST", "/conversations/*/messages"),
        ("POST", "/conversations/*/read"),
        ("DELETE", "/conversations/*/messages/*"),
        ("GET", "/owner/dashboard"),
        ("GET", "/owner/requests"),
        ("GET", "/owner/calendar"),
    ],
)
def test_each_expected_route_exists_with_method(method, path):
    ops: dict[str, set[str]] = {}
    for p, methods in app_main.app.openapi()["paths"].items():
        key = re.sub(r"\{[^}]*\}", "*", p).rstrip("/") or "/"
        ops.setdefault(key, set()).update(m.upper() for m in methods)
    assert path in ops, f"{path} is called by the frontend but not served by FastAPI"
    assert method in ops[path], f"{path} exists but does not accept {method} (allows {sorted(ops[path])})"


def test_api_error_codes_match_the_backend():
    """The ApiErrorCode union in errors.ts must line up with app.errors."""
    union = set(re.findall(r'"([A-Z_]+)"', ERRORS_TS.read_text()))
    backend = {
        app_errors.NOT_FOUND,
        app_errors.SLOT_UNAVAILABLE,
        app_errors.CAPACITY_EXCEEDED,
        app_errors.CUTOFF_PASSED,
        app_errors.INVALID_RANGE,
        app_errors.VALIDATION_ERROR,
        app_errors.NETWORK,
    }
    assert union == backend, f"frontend {sorted(union)} != backend {sorted(backend)}"


def test_config_exposes_every_section_the_domainconfig_type_needs(client, use_real_config):
    payload = client.get("/config").json()
    for section in ("domain", "terms", "rules", "copy", "metaFields"):
        assert section in payload, f"missing config section: {section}"
