"""Frontend <-> backend contract, checked statically (no browser, no network).

`frontend/lib/api.ts` and `frontend/lib/domain.tsx` are the only places the
UI talks to the API. These tests parse those files and assert every path
they call actually exists on the FastAPI app, so a route rename in
`backend/app/routers/` can't silently break the UI. It's the part of the
"stack check" that is worth automating in CI; the network-dependent version
lives in `test/e2e/` behind `E2E_BASE_URL`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import main as app_main

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TS = REPO_ROOT / "frontend" / "lib" / "api.ts"
DOMAIN_TSX = REPO_ROOT / "frontend" / "lib" / "domain.tsx"

TEMPLATE_EXPR = re.compile(r"\$\{[^{}]*\}")
PATH_LITERAL = re.compile(r"[`\"'](/[^`\"'\n]*)")


def normalize(path: str) -> str:
    path = TEMPLATE_EXPR.sub("*", path)
    for cut in ("$", "?", "`"):
        index = path.find(cut)
        if index != -1:
            path = path[:index]
    path = path.rstrip("/")
    return path or "/"


def app_operations() -> dict[str, set[str]]:
    """{normalized path -> {"GET", "POST", ...}} for every endpoint.

    Read from the OpenAPI schema rather than `app.routes`: recent
    Starlette/FastAPI wrap `include_router()` results in an opaque
    `_IncludedRouter` whose sub-routes are not exposed on `app.routes`.
    """
    operations: dict[str, set[str]] = {}
    for path, methods in app_main.app.openapi()["paths"].items():
        key = re.sub(r"\{[^}]*\}", "*", path).rstrip("/") or "/"
        operations.setdefault(key, set()).update(m.upper() for m in methods)
    return operations


def app_paths() -> set[str]:
    return set(app_operations())


def declared_fields(type_name: str) -> list[str]:
    """Top-level keys of an exported TS object type in api.ts."""
    body = re.search(
        rf"export type {type_name} = \{{(.*?)\}};", API_TS.read_text(), re.S
    ).group(1)
    while True:  # drop nested generics/objects so only top-level keys remain
        stripped = re.sub(r"<[^<>]*>|\{[^{}]*\}", "", body)
        if stripped == body:
            break
        body = stripped
    return re.findall(r"(\w+)\??\s*:", body)


def frontend_paths() -> set[str]:
    found: set[str] = set()
    for source in (API_TS, DOMAIN_TSX):
        for raw in PATH_LITERAL.findall(source.read_text()):
            candidate = normalize(raw)
            if candidate != "/":
                found.add(candidate)
    return found


def test_frontend_sources_exist():
    assert API_TS.is_file(), f"missing {API_TS}"
    assert DOMAIN_TSX.is_file(), f"missing {DOMAIN_TSX}"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/config"),
        ("GET", "/resources"),
        ("POST", "/resources"),
        ("GET", "/slots"),
        ("GET", "/slots/occupancy"),
        ("GET", "/bookings"),
        ("POST", "/bookings"),
        ("POST", "/bookings/*/cancel"),
        ("POST", "/bookings/*/reschedule"),
    ],
)
def test_every_call_in_api_ts_has_a_route(method, path):
    """The (method, path) pairs `frontend/lib/api.ts` hard-codes."""
    operations = app_operations()
    assert path in operations, f"{path} is called by the frontend but not served by FastAPI"
    assert method in operations[path], (
        f"{path} exists but does not accept {method} (allows {sorted(operations[path])})"
    )


def test_no_frontend_path_is_unknown_to_the_backend():
    unknown = frontend_paths() - app_paths()
    assert not unknown, f"frontend calls paths the backend does not serve: {sorted(unknown)}"


def test_occupancy_response_matches_the_typescript_type(client, db):
    """`SlotOccupancy` in api.ts is keyed by slot_id (it's a view, not a row)."""
    from helpers import make_slot

    make_slot(db)
    row = client.get("/slots/occupancy").json()[0]
    for field in declared_fields("SlotOccupancy"):
        assert field in row, f"api.ts declares SlotOccupancy.{field}, API did not return it"


def test_booking_response_matches_the_typescript_type(client, db):
    from helpers import make_slot

    slot = make_slot(db)
    booking = client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "guest@example.com"}
    ).json()[0]
    for field in declared_fields("Booking"):
        assert field in booking, f"api.ts declares Booking.{field}, API did not return it"


def test_booking_status_values_match_the_typescript_union(client, db):
    """api.ts types status as "confirmed" | "cancelled" | "rescheduled"."""
    declared = re.search(r"export type Booking = \{(.*?)\};", API_TS.read_text(), re.S).group(1)
    union = set(re.findall(r'"(confirmed|cancelled|rescheduled)"', declared))
    assert union == {"confirmed", "cancelled", "rescheduled"}

    from helpers import make_slot

    slot = make_slot(db, hours_ahead=72)
    booking = client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "guest@example.com"}
    ).json()[0]
    assert booking["status"] in union
    cancelled = client.post(f"/bookings/{booking['id']}/cancel").json()[0]
    assert cancelled["status"] in union
    for entry in cancelled["history"]:
        assert entry["status"] in union


def test_repo_config_matches_the_domainconfig_typescript_type(client, use_real_config):
    """lib/domain.tsx types rules as Record<string, number> and metaFields as
    Record<string, Array<{key,label,type}>>."""
    payload = client.get("/config").json()
    assert all(isinstance(v, (int, float)) for v in payload["rules"].values())
    assert all(isinstance(v, str) for v in payload["terms"].values())
    assert all(isinstance(v, str) for v in payload["copy"].values())
    for entries in payload["metaFields"].values():
        assert isinstance(entries, list)
        for entry in entries:
            assert {"key", "label", "type"} <= set(entry)


def test_frontend_env_example_points_at_the_backend():
    example = REPO_ROOT / "frontend" / ".env.local.example"
    if not example.is_file():
        pytest.skip("frontend/.env.local.example not present")
    assert "NEXT_PUBLIC_API_BASE" in example.read_text()


def test_frontend_package_json_is_parseable():
    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text())
    assert "next" in package["dependencies"]
