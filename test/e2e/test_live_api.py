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
    """The demo user opens the app on a real history, not an empty list.

    Deliberately a floor, not an exact count. `seed._seed_bookings` documents
    itself as "the 5-6 lifecycle bookings" — the number depends on where the
    slot grid falls relative to now — and `scope=all` also counts anything an
    earlier test in this suite created and cancelled, since cancelling is not
    deleting. Pinning it to one number made a green suite go red for two
    reasons that are both correct behaviour."""
    bookings = api.get("/bookings", params={"scope": "all"}).json()
    assert isinstance(bookings, list)
    if vertical == "fleet":
        assert len(bookings) >= 5
        assert all(b["reference"] for b in bookings)


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


def _find_contiguous_run(api, service_id, *, min_start_hours, count):
    """`count` back-to-back available slots on ONE resource, or None.

    A multi-slot booking is a contiguous span on a single resource — that is what
    `_resolve_selection` enforces — so picking any two available slots is not
    enough on a deployment whose `booking.duration` demands more than one. Which
    is most of the interesting ones: `minUnits: 2` alone made this test book a
    single slot and be told "select between 2 and 12".
    """
    slots = _find_available_slots(api, service_id, min_start_hours=min_start_hours, count=500)
    by_resource: dict[str, list[dict]] = {}
    for slot in slots:
        by_resource.setdefault(slot["resourceId"], []).append(slot)
    for run in by_resource.values():
        run.sort(key=lambda s: s["startUtc"])
        for i in range(len(run) - count + 1):
            window = run[i : i + count]
            if all(a["endUtc"] == b["startUtc"] for a, b in zip(window, window[1:])):
                return window
    return None


def _sample_value(field: dict):
    """A plausible value for one config-declared field descriptor.

    The live config decides what a booking must carry — `booking.subject.fields`
    and `metaFields.bookings` are both pivot-owned — so a smoke test cannot hard
    code a body. It fills what the deployment asks for and lets the engine judge
    it, which is the only version of this test that survives a pivot.
    """
    kind = field.get("type")
    if kind == "select":
        options = field.get("options") or []
        return options[0] if options else "e2e"
    if kind == "number":
        return 1
    if kind == "boolean":
        return True
    if kind == "date":
        return datetime.now(timezone.utc).date().isoformat()
    return "E2E smoke test"


def _required_shape(svc: dict, config: dict) -> dict:
    """The parts of a booking body THIS deployment makes mandatory."""
    body: dict = {}
    subject = svc.get("subject") or {}
    if subject.get("enabled"):
        required = [f for f in subject.get("fields") or [] if f.get("required")]
        if required:
            body["subject"] = {f["key"]: _sample_value(f) for f in required}
    bands = (svc.get("party") or {}).get("composition") or []
    if bands:
        # Bands must add up to the party size, and every call below books one.
        body["partyBands"] = {bands[0]["key"]: 1}
    declared = (config.get("metaFields") or {}).get("bookings") or []
    required_meta = [f for f in declared if f.get("required")]
    if required_meta:
        body["metadata"] = {f["key"]: _sample_value(f) for f in required_meta}
    return body


def _expected_status(svc: dict) -> str:
    """What the engine will do with a fresh booking for this service.

    Three config-driven reasons hold a booking at `pending`: manual approval
    (`timing.confirmation`), an unmet blocking prerequisite, and a price that
    does not exist yet (`pricing.model: "quote"`). Asserting "confirmed" flatly
    only ever passed because the demo config used none of them.
    """
    caps = svc.get("capabilities") or {}
    blocking = [
        p for p in svc.get("prerequisites") or []
        if p.get("blocksConfirmation")
    ] if caps.get("prerequisites", True) else []
    by_quote = svc.get("pricingModel") == "quote" and caps.get("quotes", True)
    return "confirmed" if svc["autoApprove"] and not blocking and not by_quote else "pending"


def test_create_reschedule_cancel_lifecycle(api, config):
    services = api.get("/services").json()
    # Pick a service with enough far-future availability for TWO bookings of
    # whatever size it demands: one to make, one to move to. The size comes from
    # the service (`booking.duration` resolves to minSlotsPerBooking), never from
    # this test — a deployment selling two-hour blocks does not sell one.
    chosen = None
    for svc in services:
        span = max(1, svc["minSlotsPerBooking"])
        run = _find_contiguous_run(
            api, svc["id"], min_start_hours=svc["cancellationCutoffHours"] + 48, count=span * 2
        )
        if run:
            chosen = (svc, span, run)
            break
    if chosen is None:
        pytest.skip("no service with a long enough far-future run to exercise the lifecycle")

    svc, span, run = chosen
    booked, target = run[:span], run[span:]

    created = api.post(
        "/bookings",
        json={
            "serviceId": svc["id"],
            "resourceId": booked[0]["resourceId"],
            "slotIds": [s["id"] for s in booked],
            "partySize": 1,
            **_required_shape(svc, config),
        },
    )
    assert created.status_code == 200, created.text
    booking = created.json()
    assert booking["status"] == _expected_status(svc)
    assert booking["slotIds"] == [s["id"] for s in booked]

    try:
        moved = api.post(
            f"/bookings/{booking['id']}/reschedule",
            json={"newSlotIds": [s["id"] for s in target]},
        )
        if booking["status"] == "confirmed":
            assert moved.status_code == 200, moved.text
            assert moved.json()["slotIds"] == [s["id"] for s in target]
            assert moved.json()["changeHistory"]
        else:
            # A booking the deployment holds for approval is not movable, by
            # design (`reschedule_booking` requires `confirmed`): the slot it
            # would move to is not held for it yet. Asserting the refusal keeps
            # this test meaningful on a `request_approve` pivot instead of
            # failing on one.
            assert moved.status_code == 409, moved.text
            assert moved.json()["detail"]["code"] == "CUTOFF_PASSED"
    finally:
        cancelled = api.post(f"/bookings/{booking['id']}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
