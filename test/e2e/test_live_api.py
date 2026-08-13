"""Smoke tests against a *running* stack (backend + real Supabase).

These are the only tests in the repo that need network, so they are opt-in:
they are skipped unless `E2E_BASE_URL` is set. CI never sets it.

    make start
    E2E_BASE_URL=http://localhost:8000 python -m pytest test/e2e -q

Everything created here is cleaned up by cancelling the booking it makes;
resources/slots are additive (the schema has no delete endpoint), so the
suite names them with a unique marker so they are easy to spot.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not BASE_URL, reason="set E2E_BASE_URL to run live stack tests"),
]

MARKER = f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        yield client


@pytest.fixture(scope="module")
def config(api):
    response = api.get("/config")
    assert response.status_code == 200
    return response.json()


def test_health(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_config_has_the_sections_the_frontend_needs(config):
    for section in ("domain", "terms", "rules", "copy", "theme", "metaFields"):
        assert section in config


def test_full_booking_flow(api, config):
    minutes = config["rules"]["slotDurationMinutes"]
    window_hours = config["rules"]["cancellationWindowHours"]
    # Start far enough out that cancelling is allowed by the configured rule.
    starts_at = datetime.now(timezone.utc) + timedelta(hours=window_hours + 24)

    resource = api.post(
        "/resources", json={"name": f"{MARKER} resource", "metadata": {"e2e": True}}
    ).json()[0]

    slot = api.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": starts_at.isoformat(),
            "ends_at": (starts_at + timedelta(minutes=minutes)).isoformat(),
            "capacity": config["rules"]["maxBookingsPerSlot"],
            "metadata": {"e2e": True},
        },
    ).json()[0]

    occupancy = api.get("/slots/occupancy", params={"resource_id": resource["id"]}).json()
    row = next(r for r in occupancy if r["slot_id"] == slot["id"])
    assert row["booked_count"] == 0

    email = f"{MARKER}@example.com"
    booking = api.post("/bookings", json={"slot_id": slot["id"], "client_email": email}).json()[0]
    assert booking["status"] == "confirmed"

    occupancy = api.get("/slots/occupancy", params={"resource_id": resource["id"]}).json()
    row = next(r for r in occupancy if r["slot_id"] == slot["id"])
    assert row["booked_count"] == 1

    mine = api.get("/bookings", params={"client_email": email}).json()
    assert [b["id"] for b in mine] == [booking["id"]]

    cancelled = api.post(f"/bookings/{booking['id']}/cancel").json()[0]
    assert cancelled["status"] == "cancelled"
    assert [entry["status"] for entry in cancelled["history"]] == ["confirmed", "cancelled"]

    occupancy = api.get("/slots/occupancy", params={"resource_id": resource["id"]}).json()
    row = next(r for r in occupancy if r["slot_id"] == slot["id"])
    assert row["booked_count"] == 0


def test_capacity_rule_is_enforced_live(api, config):
    if config["rules"]["maxBookingsPerSlot"] != 1:
        pytest.skip("this check assumes maxBookingsPerSlot == 1")

    starts_at = datetime.now(timezone.utc) + timedelta(
        hours=config["rules"]["cancellationWindowHours"] + 24
    )
    resource = api.post("/resources", json={"name": f"{MARKER} capacity", "metadata": {}}).json()[0]
    slot = api.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": starts_at.isoformat(),
            "ends_at": (starts_at + timedelta(minutes=config["rules"]["slotDurationMinutes"])).isoformat(),
            "capacity": 1,
        },
    ).json()[0]

    first = api.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": f"{MARKER}-a@example.com"}
    )
    assert first.status_code == 200
    second = api.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": f"{MARKER}-b@example.com"}
    )
    assert second.status_code == 409

    api.post(f"/bookings/{first.json()[0]['id']}/cancel")
