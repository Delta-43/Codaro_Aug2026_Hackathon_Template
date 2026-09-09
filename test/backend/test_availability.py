# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""/availability and /month-density, the calendar's two public read endpoints.

Both group slots by local date (viewer tz, default UTC) and compute slot status
+ occupancy server-side. Reads are public (optional_user).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import make_booking, make_provider, make_resource, make_service, make_slot


def _catalog(db, *, capacity=3):
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S", slot_duration_minutes=60)
    res = make_resource(db, "R", service_id=svc["id"], capacity=capacity)
    return p, svc, res


def test_availability_groups_slots_by_day(client, db):
    _, svc, res = _catalog(db)
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    make_slot(
        db,
        res["id"],
        service_id=svc["id"],
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(hours=1)).isoformat(),
        capacity=3,
    )
    frm = datetime.now(timezone.utc).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    days = client.get(
        "/availability", params={"service_id": svc["id"], "from": frm, "to": to}
    ).json()
    assert len(days) == 1
    day = days[0]
    assert set(day) == {"date", "slots", "totalCapacity", "totalBooked"}
    assert day["date"] == start.strftime("%Y-%m-%d")
    assert day["totalCapacity"] == 3
    assert day["slots"][0]["status"] == "available"


def test_availability_reflects_bookings(client, db):
    _, svc, res = _catalog(db, capacity=3)
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    slot = make_slot(
        db,
        res["id"],
        service_id=svc["id"],
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(hours=1)).isoformat(),
        capacity=3,
    )
    make_booking(db, slots=[slot], service=svc, party_size=2)
    frm = datetime.now(timezone.utc).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    day = client.get(
        "/availability", params={"service_id": svc["id"], "from": frm, "to": to}
    ).json()[0]
    assert day["totalBooked"] == 2
    assert day["slots"][0]["status"] == "partially_booked"


def test_availability_unknown_service_is_empty(client, db):
    frm = datetime.now(timezone.utc).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    days = client.get(
        "/availability", params={"service_id": "ghost", "from": frm, "to": to}
    ).json()
    assert days == []


def test_month_density_returns_a_cell_per_day(client, db):
    _, svc, res = _catalog(db, capacity=3)
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    make_slot(
        db,
        res["id"],
        service_id=svc["id"],
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(hours=1)).isoformat(),
        capacity=3,
    )
    month = start.strftime("%Y-%m")
    cells = client.get("/month-density", params={"service_id": svc["id"], "month": month}).json()
    # one cell per calendar day of the month
    import calendar

    days_in = calendar.monthrange(start.year, start.month)[1]
    assert len(cells) == days_in
    assert all(set(c) == {"date", "density"} for c in cells)
    target = next(c for c in cells if c["date"] == start.strftime("%Y-%m-%d"))
    assert target["density"] >= 1  # the day with an open slot is not empty


# ----------------------------------------------------------------------
# viewer timezone: ?tz= -> user timezone -> BUSINESS timezone -> UTC
#
# The business step is new in config v2. Without it an anonymous visitor always
# saw days grouped in UTC, which silently shifts every evening slot into the
# next day for a business east of Greenwich, the calendar looked wrong to
# exactly the people who had not logged in yet.
# ----------------------------------------------------------------------

# 23:00 UTC is already "tomorrow" in Tokyo (+09:00) and still "today" in UTC.
_LATE_UTC_HOUR = 23


def _late_evening_slot(db):
    """One slot at 23:00 UTC on a fixed future day, plus the two local dates it
    lands on in UTC and in Asia/Tokyo."""
    _, svc, res = _catalog(db)
    day = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
        hour=_LATE_UTC_HOUR, minute=0, second=0, microsecond=0
    )
    make_slot(
        db,
        res["id"],
        service_id=svc["id"],
        starts_at=day.isoformat(),
        ends_at=(day + timedelta(minutes=30)).isoformat(),
        capacity=3,
    )
    tokyo_date = (day + timedelta(hours=9)).strftime("%Y-%m-%d")
    return svc, day.strftime("%Y-%m-%d"), tokyo_date


def _days(client, svc):
    frm = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return client.get(
        "/availability", params={"service_id": svc["id"], "from": frm, "to": to}
    ).json()


def test_availability_falls_back_to_the_business_timezone_for_an_anonymous_viewer(
    client, db, auth, domain_config
):
    auth(anon=True)
    domain_config(location={"timezone": "Asia/Tokyo"})
    svc, utc_date, tokyo_date = _late_evening_slot(db)
    assert utc_date != tokyo_date  # the fixture is only meaningful if they differ

    days = _days(client, svc)
    assert [d["date"] for d in days] == [tokyo_date]


def test_availability_uses_this_services_own_timezone_not_the_global_block(
    client, db, auth, domain_config
):
    """The business-timezone fallback resolves PER SERVICE (`location` is in
    OVERRIDABLE_BLOCKS), but every other test here sets the GLOBAL block, where
    passing the service and passing None merge to the same answer, so they pass
    whether or not the lookup fires at all. Two services differing ONLY by
    `metadata.location.timezone`, same anonymous viewer, same instant: if the
    per-service lookup regresses to the global block, both group the same and
    this fails."""
    auth(anon=True)
    domain_config(location={"timezone": "UTC"})

    provider = make_provider(db, "P")
    day = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
        hour=_LATE_UTC_HOUR, minute=0, second=0, microsecond=0
    )
    utc_date = day.strftime("%Y-%m-%d")
    tokyo_date = (day + timedelta(hours=9)).strftime("%Y-%m-%d")
    assert utc_date != tokyo_date  # the fixture is only meaningful if they differ

    def _service_with(name: str, metadata: dict) -> dict:
        svc = make_service(db, provider["id"], name, slot_duration_minutes=60, metadata=metadata)
        res = make_resource(db, f"R-{name}", service_id=svc["id"], capacity=3)
        make_slot(
            db,
            res["id"],
            service_id=svc["id"],
            starts_at=day.isoformat(),
            ends_at=(day + timedelta(minutes=30)).isoformat(),
            capacity=3,
        )
        return svc

    tokyo = _service_with("Tokyo", {"location": {"timezone": "Asia/Tokyo"}})
    plain = _service_with("Plain", {})

    assert [d["date"] for d in _days(client, tokyo)] == [tokyo_date]
    assert [d["date"] for d in _days(client, plain)] == [utc_date]


def test_availability_groups_in_utc_when_the_config_declares_no_timezone(
    client, db, auth, domain_config
):
    """The v1 fixture config has no `location` block at all; normalization
    supplies `UTC`, so the old behaviour is unchanged."""
    auth(anon=True)
    domain_config()
    svc, utc_date, tokyo_date = _late_evening_slot(db)

    days = _days(client, svc)
    assert [d["date"] for d in days] == [utc_date]


def test_an_explicit_tz_query_param_beats_the_business_timezone(client, db, auth, domain_config):
    auth(anon=True)
    domain_config(location={"timezone": "Asia/Tokyo"})
    svc, utc_date, _ = _late_evening_slot(db)

    frm = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    days = client.get(
        "/availability",
        params={"service_id": svc["id"], "from": frm, "to": to, "tz": "UTC"},
    ).json()
    assert [d["date"] for d in days] == [utc_date]


def test_a_signed_in_users_timezone_beats_the_business_timezone(client, db, auth, domain_config):
    auth(role="client", metadata={"timezone": "UTC"})
    domain_config(location={"timezone": "Asia/Tokyo"})
    svc, utc_date, tokyo_date = _late_evening_slot(db)

    days = _days(client, svc)
    assert [d["date"] for d in days] == [utc_date]


def test_month_density_uses_the_business_timezone_too(client, db, auth, domain_config):
    auth(anon=True)
    domain_config(location={"timezone": "Asia/Tokyo"})
    svc, utc_date, tokyo_date = _late_evening_slot(db)

    month = tokyo_date[:7]
    cells = client.get(
        "/month-density", params={"service_id": svc["id"], "month": month}
    ).json()
    dense = {c["date"] for c in cells if c["density"] > 0}
    assert tokyo_date in dense
    if utc_date[:7] == month:
        assert utc_date not in dense


def test_a_bogus_business_timezone_cannot_even_be_loaded(domain_config, client):
    """`validate()` rejects a non-IANA `location.timezone` at load, so the
    calendar can never be grouped by a zone that does not exist. (The viewer's
    own `?tz=` is unvalidated user input, that path is covered below.)"""
    import pytest as _pytest

    from app.config_schema import ConfigError

    domain_config(location={"timezone": "Mars/Olympus"})
    with _pytest.raises(ConfigError) as excinfo:
        client.get("/config")
    assert "location.timezone" in str(excinfo.value)


def test_an_unparseable_tz_query_param_degrades_to_utc_rather_than_500(
    client, db, auth, domain_config
):
    """`?tz=` is raw user input and never validated, so `_tz` has to be
    defensive, the calendar must not be the thing that goes down."""
    auth(anon=True)
    domain_config()
    svc, utc_date, _ = _late_evening_slot(db)

    frm = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    to = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    response = client.get(
        "/availability",
        params={"service_id": svc["id"], "from": frm, "to": to, "tz": "Mars/Olympus"},
    )
    assert response.status_code == 200
    assert [d["date"] for d in response.json()] == [utc_date]
