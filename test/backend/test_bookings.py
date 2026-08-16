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


def test_create_on_auto_approve_service_is_confirmed(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, metadata={"auto_approve": True})
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
    assert resp.json()["status"] == "confirmed"


def test_create_on_manual_approve_service_is_pending(client, db, auth):
    auth(role="client")
    # autoApprove=false -> new bookings land as a pending request, not confirmed.
    cat = make_catalog(db, metadata={"auto_approve": False})
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
    assert booking["status"] == "pending"
    # pending holds no capacity — slot_occupancy counts only confirmed.
    occ = client.get("/slots/occupancy").json()[0]
    assert occ["booked_count"] == 0


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


def test_rejected_future_booking_is_excluded_from_upcoming(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    future_slot = make_slot(
        db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100
    )
    make_booking(
        db,
        slots=[future_slot],
        service=cat["service"],
        status="rejected",
        reference="BK-REJ",
    )
    # A rejected request with a future end is NOT an upcoming booking...
    upcoming = client.get("/bookings", params={"scope": "upcoming"}).json()
    assert "BK-REJ" not in {b["reference"] for b in upcoming}
    # ...but it still shows in the full history.
    all_refs = {b["reference"] for b in client.get("/bookings", params={"scope": "all"}).json()}
    assert "BK-REJ" in all_refs


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


# --- owner approve / reject (request decisions) ----------------------------

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"


def _pending(db, cat, *, hours_ahead=100):
    slot = make_slot(
        db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=hours_ahead
    )
    return make_booking(db, slots=[slot], service=cat["service"], status="pending")


def test_approve_pending_becomes_confirmed(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID owns the catalog provider
    cat = make_catalog(db)
    booking = _pending(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    stored = db.get_row("bookings", booking["id"])
    assert stored["status"] == "confirmed"
    assert stored["history"][-1] == {**stored["history"][-1], "status": "confirmed", "actor": "owner"}


def test_approve_rechecks_capacity_and_can_fail(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db, capacity=1, slot_capacity=1)
    slot = make_slot(
        db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100, capacity=1
    )
    pending = make_booking(db, slots=[slot], service=cat["service"], status="pending")
    # Someone else confirms and fills the slot while the request waited.
    make_booking(
        db,
        slots=[slot],
        service=cat["service"],
        user_id=OTHER_OWNER_ID,
        reference="BK-FILL",
        status="confirmed",
    )
    resp = client.post(f"/bookings/{pending['id']}/approve")
    assert resp.status_code == 409
    assert _detail_code(resp) == "SLOT_UNAVAILABLE"
    # left pending — not confirmed.
    assert db.get_row("bookings", pending["id"])["status"] == "pending"


def test_approve_non_pending_is_invalid_range(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"], status="confirmed")
    resp = client.post(f"/bookings/{booking['id']}/approve")
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"


def test_approve_requires_a_token(client, db):
    cat = make_catalog(db)
    booking = _pending(db, cat)
    assert client.post(f"/bookings/{booking['id']}/approve").status_code == 401


def test_approve_as_client_is_403(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    booking = _pending(db, cat)
    assert client.post(f"/bookings/{booking['id']}/approve").status_code == 403


def test_approve_by_other_owner_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    cat = make_catalog(db, owner_id=OTHER_OWNER_ID)  # provider owned by someone else
    booking = _pending(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/approve")
    assert resp.status_code == 403
    assert db.get_row("bookings", booking["id"])["status"] == "pending"


def test_reject_pending_becomes_rejected(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    booking = _pending(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    stored = db.get_row("bookings", booking["id"])
    assert stored["status"] == "rejected"
    assert stored["history"][-1]["actor"] == "owner"


def test_reject_is_idempotent(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    booking = _pending(db, cat)
    client.post(f"/bookings/{booking['id']}/reject")
    second = client.post(f"/bookings/{booking['id']}/reject")
    assert second.status_code == 200
    assert second.json()["status"] == "rejected"


def test_reject_confirmed_is_invalid_range(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"], status="confirmed")
    resp = client.post(f"/bookings/{booking['id']}/reject")
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"


def test_reject_requires_a_token(client, db):
    cat = make_catalog(db)
    booking = _pending(db, cat)
    assert client.post(f"/bookings/{booking['id']}/reject").status_code == 401


def test_reject_as_client_is_403(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    booking = _pending(db, cat)
    assert client.post(f"/bookings/{booking['id']}/reject").status_code == 403


def test_reject_by_other_owner_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    cat = make_catalog(db, owner_id=OTHER_OWNER_ID)
    booking = _pending(db, cat)
    assert client.post(f"/bookings/{booking['id']}/reject").status_code == 403
