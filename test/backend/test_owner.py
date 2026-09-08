# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""/owner/* — the business-mode (owner) dashboard aggregation router.

Every endpoint is owner-gated (`require_owner`) and scoped to the caller's own
providers (`providers.owner_id == auth.uid()`). Reads use the service key; the
shapes are additive owner-only envelopes (standard camelCase entities plus
`glance` / `stats` / `client` aggregates).

Time windows ('this month' / 'this week') are bucketed in the owner's timezone
(UTC fallback). To keep membership deterministic these tests place bookings
comfortably inside the current UTC month (the 15th, away from month edges) and
never assert on tz-boundary counts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import (
    DEFAULT_OWNER_ID,
    DEFAULT_USER_ID,
    make_booking,
    make_client_review,
    make_provider,
    make_resource,
    make_service,
    make_slot,
)

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"


def _mid_month_iso(offset_minutes: float = 0) -> str:
    """A UTC timestamp on the 15th of the current month (safely away from the
    month boundaries the owner router buckets on)."""
    now = datetime.now(timezone.utc)
    dt = now.replace(day=15, hour=12, minute=0, second=0, microsecond=0) + timedelta(
        minutes=offset_minutes
    )
    return dt.isoformat()


def _service_with_slot(db, provider_id, *, currency="EUR", price=1000, starts_at=None):
    """A service + resource + a single slot, wired together. Returns
    (service, slot)."""
    svc = make_service(
        db, provider_id, "S", price_minor_units=price, currency=currency
    )
    res = make_resource(db, "R", service_id=svc["id"], owner_id=DEFAULT_OWNER_ID)
    slot = make_slot(
        db,
        res["id"],
        service_id=svc["id"],
        starts_at=starts_at or _mid_month_iso(),
        duration_minutes=svc["slot_duration_minutes"],
    )
    return svc, slot


# --- gating (401 / 403 on every endpoint) ----------------------------------

ENDPOINTS = ["/owner/dashboard", "/owner/services", "/owner/requests", "/owner/calendar"]


def test_owner_endpoints_require_a_token(client, db):
    for path in ENDPOINTS:
        assert client.get(path).status_code == 401, path


def test_owner_endpoints_reject_a_client(client, db, auth):
    auth(role="client")
    for path in ENDPOINTS:
        assert client.get(path).status_code == 403, path


# --- dashboard -------------------------------------------------------------


def test_dashboard_shape(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    _service_with_slot(db, p["id"])
    body = client.get("/owner/dashboard").json()
    assert set(body) >= {
        "provider",
        "providers",
        "glance",
        "weekBookings",
        "requests",
        "pendingCount",
    }
    glance = body["glance"]
    assert set(glance) == {"upcomingBookings", "clientSatisfaction", "revenue"}
    assert set(glance["upcomingBookings"]) == {"total", "byService"}
    assert set(glance["clientSatisfaction"]) == {
        "currentRating",
        "reviewCount",
        "deltaPct",
        "basis",
    }
    assert set(glance["revenue"]) == {
        "minorUnits",
        "currency",
        "byCurrency",
        "bookingCount",
        "period",
    }


def test_dashboard_revenue_buckets_per_currency_no_cross_sum(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc_eur, slot_eur = _service_with_slot(db, p["id"], currency="EUR", price=10000)
    svc_pln, slot_pln = _service_with_slot(
        db, p["id"], currency="PLN", price=5000, starts_at=_mid_month_iso(offset_minutes=60)
    )
    make_booking(db, slots=[slot_eur], service=svc_eur, status="confirmed", reference="BK-EUR")
    make_booking(db, slots=[slot_pln], service=svc_pln, status="confirmed", reference="BK-PLN")

    revenue = client.get("/owner/dashboard").json()["glance"]["revenue"]
    by_currency = {e["currency"]: e["minorUnits"] for e in revenue["byCurrency"]}
    assert by_currency == {"EUR": 10000, "PLN": 5000}
    # Headline is the dominant currency's own total — never the 15000 cross sum.
    assert revenue["currency"] == "EUR"
    assert revenue["minorUnits"] == 10000
    assert revenue["minorUnits"] != 15000
    assert revenue["bookingCount"] == 2  # count spans currencies; only the money doesn't


def test_dashboard_satisfaction_pools_across_all_providers(client, db, auth):
    auth(role="owner")
    # Two owned providers with different seeded rating baselines. Pooling is
    # count-weighted across BOTH, not just the first (primary) provider.
    make_provider(
        db, "First", owner_id=DEFAULT_OWNER_ID, metadata={"rating": 4.0, "review_count": 10}
    )
    make_provider(
        db, "Second", owner_id=DEFAULT_OWNER_ID, metadata={"rating": 5.0, "review_count": 10}
    )
    sat = client.get("/owner/dashboard").json()["glance"]["clientSatisfaction"]
    # (4.0*10 + 5.0*10) / 20 == 4.5 ; first-provider-only would read 4.0.
    assert sat["currentRating"] == 4.5
    assert sat["reviewCount"] == 20


def test_dashboard_pending_count_and_requests(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"])
    make_booking(db, slots=[slot], service=svc, status="pending", reference="BK-REQ")
    body = client.get("/owner/dashboard").json()
    assert body["pendingCount"] == 1
    assert [r["reference"] for r in body["requests"]] == ["BK-REQ"]


def test_dashboard_scoped_to_own_providers_only(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    mine = make_provider(db, "Mine", owner_id=DEFAULT_OWNER_ID)
    _service_with_slot(db, mine["id"])
    # A provider owned by someone else must not leak into the dashboard.
    theirs = make_provider(db, "Theirs", owner_id=OTHER_OWNER_ID)
    make_service(db, theirs["id"], "Not mine")
    body = client.get("/owner/dashboard").json()
    assert [pr["name"] for pr in body["providers"]] == ["Mine"]
    assert body["provider"]["name"] == "Mine"


# --- services --------------------------------------------------------------


def test_owner_services_returns_service_with_stats(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"], price=2000)
    make_booking(db, slots=[slot], service=svc, status="confirmed")

    rows = client.get("/owner/services").json()
    assert len(rows) == 1
    row = rows[0]
    # standard serialized Service fields + the owner extras.
    assert row["id"] == svc["id"]
    assert row["providerName"] == "P"
    assert set(row["stats"]) == {
        "upcomingBookings",
        "pastBookings",
        "totalBookings",
        "pendingRequests",
        "revenueMinorUnits",
        "currency",
        "avgRating",
        "reviewCount",
    }
    assert row["stats"]["revenueMinorUnits"] == 2000
    assert row["stats"]["currency"] == "EUR"


def test_owner_services_counts_pending_requests(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"])
    make_booking(db, slots=[slot], service=svc, status="pending")
    row = client.get("/owner/services").json()[0]
    assert row["stats"]["pendingRequests"] == 1


def test_owner_services_scoped_to_own_providers(client, db, auth):
    auth(role="owner")
    mine = make_provider(db, "Mine", owner_id=DEFAULT_OWNER_ID)
    make_service(db, mine["id"], "Mine service")
    theirs = make_provider(db, "Theirs", owner_id=OTHER_OWNER_ID)
    make_service(db, theirs["id"], "Their service")
    rows = client.get("/owner/services").json()
    assert [r["name"] for r in rows] == ["Mine service"]


# --- requests --------------------------------------------------------------


def test_owner_requests_pending_only_with_client_card(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"])
    make_booking(
        db,
        slots=[slot],
        service=svc,
        status="pending",
        reference="BK-REQ",
        client_email="ada@example.com",
    )
    # a confirmed booking must NOT appear in the requests list.
    slot2 = make_slot(db, slot["resource_id"], service_id=svc["id"], hours_ahead=200)
    make_booking(db, slots=[slot2], service=svc, status="confirmed", reference="BK-OK")

    rows = client.get("/owner/requests").json()
    assert [r["reference"] for r in rows] == ["BK-REQ"]
    req = rows[0]
    assert req["serviceName"] == "S"
    assert req["providerName"] == "P"
    client_card = req["client"]
    assert set(client_card) == {
        "id",
        "displayName",
        "email",
        "avatarUrl",
        "memberSinceUtc",
        "totalBookings",
        "bookingsWithProvider",
        "cancelledWithProvider",
        "rating",
        "reviewCount",
    }
    # FakeSupabase has no auth.admin — the router degrades gracefully.
    assert client_card["memberSinceUtc"] is None
    assert client_card["displayName"] == "ada"  # falls back to email local part
    assert client_card["email"] == "ada@example.com"
    assert client_card["id"] == DEFAULT_USER_ID
    assert client_card["totalBookings"] == 2  # the request + the confirmed one
    assert client_card["bookingsWithProvider"] == 2
    assert client_card["cancelledWithProvider"] == 0
    # No client_reviews present -> reputation defaults.
    assert client_card["rating"] is None
    assert client_card["reviewCount"] == 0


def test_owner_requests_client_card_reflects_client_reviews(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"])
    make_booking(
        db,
        slots=[slot],
        service=svc,
        status="pending",
        reference="BK-REQ",
        client_email="ada@example.com",
    )
    # A past completed booking the same client had, rated by a business.
    past = make_slot(db, slot["resource_id"], service_id=svc["id"], hours_ahead=-5)
    done = make_booking(
        db,
        slots=[past],
        service=svc,
        status="confirmed",
        reference="BK-DONE",
        client_email="ada@example.com",
    )
    make_client_review(db, done, rating=4, provider_id=p["id"])

    card = client.get("/owner/requests").json()[0]["client"]
    assert card["rating"] == 4.0
    assert card["reviewCount"] == 1


def test_owner_requests_scoped_to_own_providers(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    theirs = make_provider(db, "Theirs", owner_id=OTHER_OWNER_ID)
    svc, slot = _service_with_slot(db, theirs["id"])
    make_booking(db, slots=[slot], service=svc, status="pending", reference="BK-THEIRS")
    assert client.get("/owner/requests").json() == []


# --- calendar --------------------------------------------------------------


def test_owner_calendar_confirmed_only_sorted_by_start(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    res = make_resource(db, "R", service_id=svc["id"], owner_id=DEFAULT_OWNER_ID)
    later = make_slot(db, res["id"], service_id=svc["id"], hours_ahead=200)
    earlier = make_slot(db, res["id"], service_id=svc["id"], hours_ahead=100)
    make_booking(db, slots=[later], service=svc, status="confirmed", reference="BK-LATE")
    make_booking(db, slots=[earlier], service=svc, status="confirmed", reference="BK-EARLY")
    # a pending request must be excluded from the calendar.
    pend = make_slot(db, res["id"], service_id=svc["id"], hours_ahead=150)
    make_booking(db, slots=[pend], service=svc, status="pending", reference="BK-PEND")

    rows = client.get(
        "/owner/calendar",
        params={"from": "2000-01-01T00:00:00.000Z", "to": "2100-01-01T00:00:00.000Z"},
    ).json()
    assert [r["reference"] for r in rows] == ["BK-EARLY", "BK-LATE"]


def test_owner_calendar_defaults_to_current_month(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc, slot = _service_with_slot(db, p["id"])  # slot on the 15th of this month
    make_booking(db, slots=[slot], service=svc, status="confirmed", reference="BK-THISMONTH")
    rows = client.get("/owner/calendar").json()  # no from/to -> current month
    assert "BK-THISMONTH" in {r["reference"] for r in rows}


def test_owner_calendar_scoped_to_own_providers(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    theirs = make_provider(db, "Theirs", owner_id=OTHER_OWNER_ID)
    svc, slot = _service_with_slot(db, theirs["id"])
    make_booking(db, slots=[slot], service=svc, status="confirmed", reference="BK-THEIRS")
    rows = client.get(
        "/owner/calendar",
        params={"from": "2000-01-01T00:00:00.000Z", "to": "2100-01-01T00:00:00.000Z"},
    ).json()
    assert rows == []


# --- fake fidelity: jsonb arrow-path filter columns ------------------------


def test_fake_in_filter_accepts_jsonb_arrow_path_column(db):
    """owner.py filters `.in_("metadata->>provider_id", ids)` server-side, as
    real PostgREST allows; the fake must resolve the arrow path into the
    jsonb column instead of returning nothing."""
    db.insert_row("bookings", slot_id="s1", client_email="a@x.io", metadata={"provider_id": "p-1"})
    db.insert_row("bookings", slot_id="s2", client_email="b@x.io", metadata={"provider_id": "p-2"})
    db.insert_row("bookings", slot_id="s3", client_email="c@x.io", metadata={})  # no key
    rows = (
        db.table("bookings")
        .select("*")
        .in_("metadata->>provider_id", ["p-1", "p-3"])
        .execute()
        .data
    )
    assert [r["slot_id"] for r in rows] == ["s1"]
