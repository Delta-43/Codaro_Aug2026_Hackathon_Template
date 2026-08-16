"""Smoke tests against a *running* stack (backend + real Supabase Auth).

These are the only tests that need network + credentials, so they are opt-in and
skip cleanly otherwise. They sign the seeded demo user in through Supabase to get
a real JWT, then drive the live API exactly as the frontend would.

Run:

    make start
    export SUPABASE_URL=... SUPABASE_ANON_KEY=...
    E2E_BASE_URL=http://localhost:8000 python -m pytest test/e2e -q

Skips unless BOTH `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set (the backend
base URL defaults to http://localhost:8000). Everything created is cleaned up by
cancelling the booking it makes.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

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


@pytest.fixture(scope="module")
def token() -> str:
    """Sign the demo user in via Supabase Auth and return their access token."""
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
def api(token) -> httpx.Client:
    with httpx.Client(
        base_url=BASE_URL, timeout=20.0, headers={"Authorization": f"Bearer {token}"}
    ) as client:
        # fail fast (skip) if the backend isn't up
        try:
            client.get("/health")
        except httpx.HTTPError as exc:  # pragma: no cover - env dependent
            pytest.skip(f"backend not reachable at {BASE_URL}: {exc}")
        yield client


@pytest.fixture(scope="module")
def config(api) -> dict:
    return api.get("/config").json()


@pytest.fixture(scope="module")
def vertical(api) -> str:
    return api.get("/demo/vertical").json().get("verticalId")


# --- discovery -------------------------------------------------------------


def test_health(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_providers_discovery(api, vertical):
    providers = api.get("/providers").json()
    assert isinstance(providers, list) and providers
    if vertical == "fleet":
        # The default (fleet) seed ships 7 providers, incl. VISTULA-4471.
        assert len(providers) == 7
        by_code = api.get("/providers/by-code/VISTULA-4471")
        assert by_code.status_code == 200
        assert by_code.json()["publicCode"] == "VISTULA-4471"


def test_services_and_resources(api):
    providers = api.get("/providers").json()
    pid = providers[0]["id"]
    services = api.get("/services", params={"provider_id": pid}).json()
    assert services, "expected the provider to have at least one service"
    svc = services[0]
    assert svc["providerId"] == pid
    resources = api.get("/resources", params={"service_id": svc["id"]}).json()
    assert isinstance(resources, list)


def test_availability_returns_days(api):
    svc = api.get("/services").json()[0]
    frm = datetime.now(timezone.utc).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    days = api.get(
        "/availability", params={"service_id": svc["id"], "from": frm, "to": to}
    ).json()
    assert isinstance(days, list)


# --- identity --------------------------------------------------------------


def test_me_is_the_demo_user(api):
    me = api.get("/me").json()
    assert me["email"] == DEMO_EMAIL
    assert set(me) >= {"id", "displayName", "email", "followedProviderIds"}


def test_demo_user_has_seeded_bookings(api, vertical):
    bookings = api.get("/bookings", params={"scope": "all"}).json()
    assert isinstance(bookings, list)
    if vertical == "fleet":
        assert len(bookings) == 6


# --- follow / unfollow -----------------------------------------------------


def test_follow_then_unfollow(api):
    pid = api.get("/providers").json()[0]["id"]
    followed = api.post(f"/providers/{pid}/follow").json()
    assert pid in followed["followedProviderIds"]
    unfollowed = api.post(f"/providers/{pid}/unfollow").json()
    assert pid not in unfollowed["followedProviderIds"]


# --- full booking lifecycle ------------------------------------------------


def _find_available_slots(api, service_id, *, min_start_hours, count=1):
    """Return up to `count` available slot ids starting at least
    `min_start_hours` from now (so the cancellation cutoff doesn't block us)."""
    frm = (datetime.now(timezone.utc) + timedelta(hours=min_start_hours)).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    days = api.get(
        "/availability", params={"service_id": service_id, "from": frm, "to": to}
    ).json()
    out = []
    for day in days:
        for slot in day["slots"]:
            if slot["status"] == "available":
                out.append(slot)
                if len(out) >= count:
                    return out
    return out


def test_create_reschedule_cancel_lifecycle(api, config):
    cutoff = 0
    services = api.get("/services").json()
    # pick a service that has resources + far-future availability
    chosen = None
    for svc in services:
        cutoff = svc["cancellationCutoffHours"]
        slots = _find_available_slots(api, svc["id"], min_start_hours=cutoff + 48, count=2)
        if len(slots) >= 2 and slots[0]["resourceId"] == slots[1]["resourceId"]:
            chosen = (svc, slots)
            break
    if chosen is None:
        pytest.skip("no service with two far-future available slots to exercise the lifecycle")

    svc, slots = chosen
    first, second = slots[0], slots[1]

    created = api.post(
        "/bookings",
        json={
            "serviceId": svc["id"],
            "resourceId": first["resourceId"],
            "slotIds": [first["id"]],
            "partySize": 1,
        },
    )
    assert created.status_code == 200, created.text
    booking = created.json()
    assert booking["status"] == "confirmed"
    assert booking["slotIds"] == [first["id"]]

    try:
        moved = api.post(
            f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [second["id"]]}
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["slotIds"] == [second["id"]]
        assert moved.json()["changeHistory"]
    finally:
        cancelled = api.post(f"/bookings/{booking['id']}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
