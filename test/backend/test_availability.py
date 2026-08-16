"""/availability and /month-density — the calendar's two public read endpoints.

Both group slots by local date (viewer tz, default UTC) and compute slot status
+ occupancy server-side. Reads are public (optional_user).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import iso_in, make_booking, make_provider, make_resource, make_service, make_slot


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
