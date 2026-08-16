"""/bookings — the reworked, auth-gated booking loop, through the real endpoints.

A booking spans one-or-more contiguous same-resource slots, carries a party
size, and is scoped to the verified user (identity from the token, never the
body). Create returns a single camelCase `Booking`; `GET /bookings` returns a
list. Capacity/contiguity/cutoff are enforced at commit and surface as the
frontend's ApiError codes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from helpers import (
    iso_in,
    make_booking,
    make_catalog,
    make_resource,
    make_service,
    make_slot,
)


def _detail_code(resp) -> str:
    return resp.json()["detail"]["code"]


def _contiguous_slots(db, cat, *, n=2, first_hours=48):
    """`n` back-to-back slots on the catalog's resource/service."""
    dur = cat["service"]["slot_duration_minutes"]
    start = datetime.fromisoformat(iso_in(hours=first_hours))
    slots = []
    for i in range(n):
        s = (start + timedelta(minutes=dur * i)).isoformat()
        e = (start + timedelta(minutes=dur * (i + 1))).isoformat()
        slots.append(
            make_slot(
                db,
                cat["resource"]["id"],
                service_id=cat["service"]["id"],
                starts_at=s,
                ends_at=e,
                capacity=cat["slot"]["capacity"],
            )
        )
    return slots


# --- create ----------------------------------------------------------------


def test_create_requires_a_token(client, db):
    cat = make_catalog(db)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 401


def test_create_returns_a_single_booking_scoped_to_the_token(client, db, auth):
    user = auth(role="client", email="ada@example.com")
    cat = make_catalog(db, price_minor_units=1000)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 200
    booking = resp.json()
    assert isinstance(booking, dict)  # single object, not a list
    assert booking["status"] == "confirmed"
    assert booking["reference"].startswith("BK-")
    assert booking["slotIds"] == [cat["slot"]["id"]]
    assert booking["userId"] == user.id  # from the token, not the body
    assert booking["priceMinorUnits"] == 1000  # price * 1 slot * party 1


def test_create_holds_capacity_in_occupancy(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, capacity=5, slot_capacity=5)
    client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 3,
        },
    )
    row = client.get("/slots/occupancy").json()[0]
    assert row["booked_count"] == 3


def test_second_booking_at_capacity_is_slot_unavailable(client, db, auth):
    cat = make_catalog(db, capacity=1, slot_capacity=1)
    body = {
        "serviceId": cat["service"]["id"],
        "resourceId": cat["resource"]["id"],
        "slotIds": [cat["slot"]["id"]],
        "partySize": 1,
    }
    auth(role="client", email="a@example.com")
    assert client.post("/bookings", json=body).status_code == 200
    auth(role="client", email="b@example.com", id="33333333-3333-3333-3333-333333333333")
    resp = client.post("/bookings", json=body)
    assert resp.status_code == 409
    assert _detail_code(resp) == "SLOT_UNAVAILABLE"


def test_party_over_capacity_is_capacity_exceeded(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 5,
        },
    )
    assert resp.status_code == 409
    assert _detail_code(resp) == "CAPACITY_EXCEEDED"


def test_unknown_slot_is_not_found(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": ["ghost-slot"],
            "partySize": 1,
        },
    )
    assert resp.status_code == 404
    assert _detail_code(resp) == "NOT_FOUND"


def test_unknown_service_is_not_found(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": "ghost-service",
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 404


def test_multi_slot_contiguous_booking(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, max_slots_per_booking=3, price_minor_units=500)
    a, b = _contiguous_slots(db, cat, n=2)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [a["id"], b["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 200
    booking = resp.json()
    assert booking["slotIds"] == [a["id"], b["id"]]
    assert booking["priceMinorUnits"] == 1000  # 500 * 2 slots * party 1


def test_non_contiguous_selection_is_invalid_range(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, max_slots_per_booking=3)
    a, b = _contiguous_slots(db, cat, n=2)
    # third slot far away -> gap between b and c
    c = make_slot(
        db,
        cat["resource"]["id"],
        service_id=cat["service"]["id"],
        hours_ahead=100,
        capacity=cat["slot"]["capacity"],
    )
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [a["id"], c["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"


# --- list ------------------------------------------------------------------


def test_list_requires_a_token(client, db):
    assert client.get("/bookings").status_code == 401


def test_list_scope_filters(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    # an upcoming (future) booking
    future_slot = make_slot(
        db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100
    )
    make_booking(db, slots=[future_slot], service=cat["service"], reference="BK-FUT")
    # a completed (past) booking
    past_slot = make_slot(
        db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-5
    )
    make_booking(db, slots=[past_slot], service=cat["service"], reference="BK-PAST")

    all_refs = {b["reference"] for b in client.get("/bookings", params={"scope": "all"}).json()}
    assert {"BK-FUT", "BK-PAST"} <= all_refs

    upcoming = client.get("/bookings", params={"scope": "upcoming"}).json()
    assert [b["reference"] for b in upcoming] == ["BK-FUT"]

    past = client.get("/bookings", params={"scope": "past"}).json()
    assert [b["reference"] for b in past] == ["BK-PAST"]


def test_get_single_booking(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"])
    got = client.get(f"/bookings/{booking['id']}").json()
    assert got["id"] == booking["id"]


def test_get_unknown_booking_is_404(client, db, auth):
    auth(role="client")
    assert client.get("/bookings/nope").status_code == 404


# --- cancel ----------------------------------------------------------------


def test_cancel_far_future_booking(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 200
    out = resp.json()
    assert out["status"] == "cancelled"
    assert out["cancelledAtUtc"] is not None
    stored = db.get_row("bookings", booking["id"])
    assert [h["status"] for h in stored["history"]] == ["confirmed", "cancelled"]


def test_cancel_is_idempotent(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    client.post(f"/bookings/{booking['id']}/cancel")
    second = client.post(f"/bookings/{booking['id']}/cancel")
    assert second.status_code == 200
    assert second.json()["status"] == "cancelled"


def test_client_cannot_cancel_inside_the_cutoff(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 409
    assert _detail_code(resp) == "CUTOFF_PASSED"


def test_owner_overrides_the_cutoff(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 200
    stored = db.get_row("bookings", booking["id"])
    assert stored["history"][-1]["actor"] == "owner"


# --- reschedule ------------------------------------------------------------


def test_reschedule_moves_the_booking(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200)
    booking = make_booking(db, slots=[old], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 200
    out = resp.json()
    assert out["slotIds"] == [new["id"]]
    assert out["status"] == "confirmed"
    assert len(out["changeHistory"]) == 1


def test_reschedule_inside_cutoff_is_blocked_for_client(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200)
    booking = make_booking(db, slots=[old], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 409
    assert _detail_code(resp) == "CUTOFF_PASSED"


def test_reschedule_to_full_slot_is_slot_unavailable(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, capacity=1, slot_capacity=1, cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100, capacity=1)
    taken = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200, capacity=1)
    booking = make_booking(db, slots=[old], service=cat["service"])
    # someone else fills `taken`
    make_booking(
        db,
        slots=[taken],
        service=cat["service"],
        user_id="99999999-9999-9999-9999-999999999999",
        reference="BK-OTHER",
    )
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [taken["id"]]})
    assert resp.status_code == 409
    assert _detail_code(resp) == "SLOT_UNAVAILABLE"


def test_reschedule_to_same_slot_credits_back_capacity(client, db, auth):
    """A capacity-1 slot the booking already holds looks full, but its own party
    is credited back — re-selecting it succeeds (the credit path)."""
    auth(role="client")
    cat = make_catalog(db, capacity=1, slot_capacity=1, cancellation_cutoff_hours=24)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100, capacity=1)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [slot["id"]]})
    assert resp.status_code == 200
    assert resp.json()["slotIds"] == [slot["id"]]


# --- review ----------------------------------------------------------------


def test_review_only_completed_bookings(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    # completed = confirmed booking whose slot end is in the past
    past = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-5)
    booking = make_booking(db, slots=[past], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/review", json={"rating": 5, "text": "Great"})
    assert resp.status_code == 200
    out = resp.json()
    assert out["review"]["rating"] == 5
    assert out["review"]["text"] == "Great"


def test_review_rejected_for_upcoming_booking(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    future = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[future], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/review", json={"rating": 4})
    assert resp.status_code == 404
