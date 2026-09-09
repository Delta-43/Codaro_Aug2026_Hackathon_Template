# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

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
    DEFAULT_OWNER_ID,
    iso_in,
    make_booking,
    make_catalog,
    make_entitlement,
    make_provider,
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


# --- owner client-review (client reputation) -------------------------------


def _completed(db, cat, *, client_email="guest@example.com"):
    """A confirmed booking whose slot end is in the past — the router treats this
    as `completed`, the only state that can be rated."""
    past = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-5)
    return make_booking(
        db, slots=[past], service=cat["service"], status="confirmed", client_email=client_email
    )


def test_client_review_on_completed_booking_persists(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID owns the catalog provider
    cat = make_catalog(db)
    booking = _completed(db, cat)
    resp = client.post(
        f"/bookings/{booking['id']}/client-review", json={"rating": 4, "text": "Great customer"}
    )
    assert resp.status_code == 200
    out = resp.json()
    assert set(out) == {"rating", "text", "createdAtUtc"}
    assert out["rating"] == 4
    assert out["text"] == "Great customer"
    # exactly one row persisted, linked to the booking + client + provider.
    rows = [r for r in db.rows("client_reviews") if r["booking_id"] == booking["id"]]
    assert len(rows) == 1
    assert rows[0]["rating"] == 4
    assert rows[0]["client_id"] == booking["client_id"]
    assert rows[0]["provider_id"] == cat["provider"]["id"]


def test_client_review_clamps_rating(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    booking = _completed(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 9})
    assert resp.status_code == 200
    assert resp.json()["rating"] == 5
    assert db.rows("client_reviews")[0]["rating"] == 5


def test_client_review_upcoming_booking_is_404(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"], status="confirmed")
    resp = client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 5})
    assert resp.status_code == 404
    assert db.count("client_reviews") == 0


def test_client_review_requires_a_token(client, db):
    cat = make_catalog(db)
    booking = _completed(db, cat)
    assert client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 5}).status_code == 401


def test_client_review_as_client_is_403(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)
    booking = _completed(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 5})
    assert resp.status_code == 403
    assert db.count("client_reviews") == 0


def test_client_review_by_other_owner_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    cat = make_catalog(db, owner_id=OTHER_OWNER_ID)  # provider owned by someone else
    booking = _completed(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 5})
    assert resp.status_code == 403
    assert db.count("client_reviews") == 0


def test_client_review_replaces_prior_one(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    booking = _completed(db, cat)
    client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 2, "text": "meh"})
    second = client.post(
        f"/bookings/{booking['id']}/client-review", json={"rating": 5, "text": "improved"}
    )
    assert second.status_code == 200
    assert second.json()["rating"] == 5
    # still a single row for the booking — the prior review was replaced.
    rows = [r for r in db.rows("client_reviews") if r["booking_id"] == booking["id"]]
    assert len(rows) == 1
    assert rows[0]["rating"] == 5
    assert rows[0]["text"] == "improved"


# --- pricing (config v2) ---------------------------------------------------
#
# v1 priced inline: `priceMinorUnits * len(rows) * party`. The booking router now
# calls `app.pricing.quote` with the service's resolved `pricing` block, and
# stamps `price_breakdown` + `deposit_minor_units` into booking metadata
# alongside the price. The default block must reproduce the v1 number exactly;
# `services.metadata.pricing` is what buys the new models.


def _book(client, cat, slot_ids=None, party=1):
    return client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": slot_ids or [cat["slot"]["id"]],
            "partySize": party,
        },
    )


def test_create_stamps_a_price_breakdown_and_deposit_into_metadata(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, capacity=4, slot_capacity=4, price_minor_units=1000)
    booking = _book(client, cat, party=2).json()

    md = db.get_row("bookings", booking["id"])["metadata"]
    assert md["price_minor_units"] == 2000 == booking["priceMinorUnits"]
    assert md["deposit_minor_units"] == 0
    assert isinstance(md["price_breakdown"], list)
    assert md["price_breakdown"] == [
        {"key": "base", "label": "Per slot", "amountMinorUnits": 2000}
    ]


def test_default_pricing_still_matches_the_v1_formula_end_to_end(client, db, auth):
    """price x slots x party, straight through the real endpoint."""
    auth(role="client")
    cat = make_catalog(db, capacity=5, slot_capacity=5, max_slots_per_booking=3,
                       price_minor_units=500)
    a, b = _contiguous_slots(db, cat, n=2)
    booking = _book(client, cat, slot_ids=[a["id"], b["id"]], party=3).json()
    assert booking["priceMinorUnits"] == 500 * 2 * 3


def test_a_service_can_price_per_night_via_metadata_pricing(client, db, auth):
    """The pivot reach v1 could not express: the same slot machinery billing by
    started night instead of by slot."""
    auth(role="client")
    cat = make_catalog(
        db,
        price_minor_units=1000,
        metadata={"pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}}},
    )
    booking = _book(client, cat).json()
    assert booking["priceMinorUnits"] == 9900


def test_charge_per_person_false_stops_the_party_multiplying(client, db, auth):
    """A shared unit — the court costs the same for two players or four."""
    auth(role="client")
    cat = make_catalog(
        db,
        capacity=4,
        slot_capacity=4,
        price_minor_units=4000,
        metadata={"pricing": {"chargePerPerson": False}},
    )
    assert _book(client, cat, party=1).json()["priceMinorUnits"] == 4000
    assert _book(client, cat, party=3).json()["priceMinorUnits"] == 4000


def test_a_service_tier_applies_through_the_real_endpoint(client, db, auth):
    auth(role="client")
    cat = make_catalog(
        db,
        capacity=6,
        slot_capacity=6,
        price_minor_units=1000,
        metadata={
            "pricing": {
                "tiers": [
                    {
                        "key": "group",
                        "label": "Group rate",
                        "amountMinorUnits": 600,
                        "appliesWhen": {"partySize": {"min": 4}},
                    }
                ]
            }
        },
    )
    assert _book(client, cat, party=2).json()["priceMinorUnits"] == 2000  # base
    booking = _book(client, cat, party=4).json()
    assert booking["priceMinorUnits"] == 2400  # 600 x 4 heads
    md = db.get_row("bookings", booking["id"])["metadata"]
    assert md["price_breakdown"][0]["key"] == "group"


def test_a_global_deposit_lands_on_the_booking(client, db, auth, domain_config):
    auth(role="client")
    domain_config(
        pricing={"deposit": {"enabled": True, "kind": "percent", "value": 20, "refundable": True}}
    )
    cat = make_catalog(db, price_minor_units=10000)
    booking = _book(client, cat).json()
    md = db.get_row("bookings", booking["id"])["metadata"]
    assert md["price_minor_units"] == 10000
    assert md["deposit_minor_units"] == 2000


def test_the_global_pricing_block_applies_when_the_service_has_no_columns(
    client, db, auth, domain_config
):
    """A service with null price/currency columns prices from
    `domain.config.json` — v1 had no global default for either."""
    auth(role="client")
    domain_config(
        pricing={"currency": "PLN", "rate": {"per": "booking", "amountMinorUnits": 7500}}
    )
    cat = make_catalog(db, max_slots_per_booking=3, price_minor_units=None, currency=None)
    a, b = _contiguous_slots(db, cat, n=2)
    booking = _book(client, cat, slot_ids=[a["id"], b["id"]]).json()
    assert booking["priceMinorUnits"] == 7500  # per booking, not per slot
    assert booking["currency"] == "PLN"


def test_a_service_fee_is_itemised_in_the_breakdown(client, db, auth):
    auth(role="client")
    cat = make_catalog(
        db,
        price_minor_units=5000,
        metadata={
            "pricing": {
                "fees": [
                    {"key": "clean", "label": "Cleaning", "kind": "flat", "amountMinorUnits": 1500}
                ]
            }
        },
    )
    booking = _book(client, cat).json()
    assert booking["priceMinorUnits"] == 6500
    md = db.get_row("bookings", booking["id"])["metadata"]
    assert [line["key"] for line in md["price_breakdown"]] == ["base", "clean"]


def test_reschedule_reprices_and_rewrites_the_pricing_metadata(client, db, auth):
    """Moving a booking has to re-quote it: a 1-slot booking moved onto 2 slots
    costs twice as much, and the stale breakdown/currency must be replaced."""
    auth(role="client")
    cat = make_catalog(
        db,
        max_slots_per_booking=3,
        price_minor_units=500,
        currency="PLN",
        cancellation_cutoff_hours=24,
    )
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    a, b = _contiguous_slots(db, cat, n=2, first_hours=200)
    booking = make_booking(
        db,
        slots=[old],
        service=cat["service"],
        metadata={"currency": "XXX", "price_breakdown": [{"key": "stale"}]},
    )

    resp = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [a["id"], b["id"]]}
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out["priceMinorUnits"] == 1000  # 500 x 2 slots x party 1
    assert out["currency"] == "PLN"  # the stale "XXX" was rewritten

    md = db.get_row("bookings", booking["id"])["metadata"]
    assert md["price_breakdown"] == [
        {"key": "base", "label": "Per slot", "amountMinorUnits": 1000}
    ]
    assert md["deposit_minor_units"] == 0


def test_reschedule_recomputes_the_deposit_too(client, db, auth, domain_config):
    auth(role="client")
    domain_config(
        pricing={"deposit": {"enabled": True, "kind": "percent", "value": 50, "refundable": True}}
    )
    cat = make_catalog(db, max_slots_per_booking=3, price_minor_units=1000,
                       cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    a, b = _contiguous_slots(db, cat, n=2, first_hours=200)
    booking = make_booking(db, slots=[old], service=cat["service"])

    client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [a["id"], b["id"]]})
    md = db.get_row("bookings", booking["id"])["metadata"]
    assert md["price_minor_units"] == 2000
    assert md["deposit_minor_units"] == 1000


# --- auto-approve driven by timing.confirmation ----------------------------


def test_request_approve_confirmation_makes_every_new_booking_pending(
    client, db, auth, domain_config
):
    """A niche whose whole model is request-then-approve sets it once in the
    pivot file instead of toggling every service."""
    auth(role="client")
    domain_config(timing={"confirmation": "request_approve"})
    cat = make_catalog(db)
    assert _book(client, cat).json()["status"] == "pending"


def test_a_service_toggle_still_overrides_request_approve_confirmation(
    client, db, auth, domain_config
):
    auth(role="client")
    domain_config(timing={"confirmation": "request_approve"})
    cat = make_catalog(db, metadata={"auto_approve": True})
    assert _book(client, cat).json()["status"] == "confirmed"


# ---------------------------------------------------------------------------
# timing.leadTimeMinutes — minimum notice, enforced on POST /bookings
# ---------------------------------------------------------------------------
#
# `create_booking` dispatches `apply_rules("booking.create", ...)` right after
# the selection resolves, mapping a RuleViolation to INVALID_RANGE (400). These
# go through the real endpoint so the dispatch, not just the validator, is what
# is being tested.


def _book_body(cat, slot, party=1):
    return {
        "serviceId": cat["service"]["id"],
        "resourceId": cat["resource"]["id"],
        "slotIds": [slot["id"]],
        "partySize": party,
    }


def test_a_soon_slot_books_fine_on_the_default_config(client, db, auth, domain_config):
    """The shipped default is `leadTimeMinutes: 0` — off. A slot ten minutes out
    must still be bookable, or the rule would be a silent behaviour change for
    every existing deployment."""
    domain_config()
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=1 / 6)  # 10 minutes out
    resp = client.post("/bookings", json=_book_body(cat, cat["slot"]))
    assert resp.status_code == 200


def test_a_booking_inside_the_lead_time_is_rejected(client, db, auth, domain_config):
    domain_config(timing={"leadTimeMinutes": 120})
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=1)
    resp = client.post("/bookings", json=_book_body(cat, cat["slot"]))
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"
    assert "120" in resp.json()["detail"]["message"]


def test_a_booking_outside_the_lead_time_is_accepted(client, db, auth, domain_config):
    domain_config(timing={"leadTimeMinutes": 120})
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=4)
    resp = client.post("/bookings", json=_book_body(cat, cat["slot"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_a_rejected_lead_time_booking_persists_nothing(client, db, auth, domain_config):
    """The gate runs before the insert, so a refused booking must leave no row
    and no capacity hold behind."""
    domain_config(timing={"leadTimeMinutes": 240})
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=0.5, capacity=2, slot_capacity=2)
    assert client.post("/bookings", json=_book_body(cat, cat["slot"])).status_code == 400
    assert db.rows("bookings") == []
    assert db.rows("booking_slots") == []
    assert client.get("/slots/occupancy").json()[0]["booked_count"] == 0


def test_the_lead_time_window_moves_with_the_config(client, db, auth, domain_config):
    """Same slot, two configs: the verdict comes from the pivot file, not code."""
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=3)

    domain_config(timing={"leadTimeMinutes": 600})  # 10h notice -> too soon
    assert client.post("/bookings", json=_book_body(cat, cat["slot"])).status_code == 400

    domain_config(timing={"leadTimeMinutes": 60})  # 1h notice -> fine
    assert client.post("/bookings", json=_book_body(cat, cat["slot"])).status_code == 200


def test_lead_time_does_not_gate_a_reschedule_onto_a_soon_slot(client, db, auth, domain_config):
    """`leadTimeMinutes` is registered on `booking.create` only; changing an
    existing booking is governed by `cancellationWindowHours`. Pinned so the
    two events stay distinct."""
    domain_config(timing={"leadTimeMinutes": 600})
    auth(role="client")
    cat = make_catalog(db, slot_hours_ahead=48, cancellation_cutoff_hours=24)
    booking = client.post("/bookings", json=_book_body(cat, cat["slot"])).json()
    soon = make_slot(
        db,
        cat["resource"]["id"],
        service_id=cat["service"]["id"],
        hours_ahead=2,
        capacity=cat["slot"]["capacity"],
    )
    resp = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [soon["id"]]}
    )
    assert resp.status_code == 200
    assert resp.json()["slotIds"] == [soon["id"]]


# ---------------------------------------------------------------------------
# maxBookingsPerSlot must NOT gate booking.create (group-booking regression)
# ---------------------------------------------------------------------------
#
# The config default is `maxBookingsPerSlot: 1`. If `rules._capacity` were
# dispatched on `booking.create`, it would apply `min(slot.capacity, 1)` and cap
# every shared-capacity slot at one head. Capacity belongs to `_resolve_selection`
# + the `slot_occupancy` view, which know about party size and multi-slot holds.


def test_a_group_books_a_shared_slot_while_the_config_caps_at_one(client, db, auth, domain_config):
    config = domain_config(rules={"maxBookingsPerSlot": 1})
    assert config["rules"]["maxBookingsPerSlot"] == 1  # the shipped default
    auth(role="client")
    cat = make_catalog(db, capacity=8, slot_capacity=8)
    resp = client.post("/bookings", json=_book_body(cat, cat["slot"], party=5))
    assert resp.status_code == 200
    assert client.get("/slots/occupancy").json()[0]["booked_count"] == 5


def test_two_customers_share_one_slot_while_the_config_caps_at_one(client, db, auth, domain_config):
    """The test that actually protects the exclusion: with `_capacity`
    dispatched, the *second* booking on the same slot fails (booked_count 4 >=
    min(8, 1)) even though six seats are free."""
    domain_config(rules={"maxBookingsPerSlot": 1})
    cat = make_catalog(db, capacity=8, slot_capacity=8)

    auth(role="client", email="a@example.com")
    assert client.post("/bookings", json=_book_body(cat, cat["slot"], party=4)).status_code == 200
    auth(role="client", email="b@example.com", id="33333333-3333-3333-3333-333333333333")
    assert client.post("/bookings", json=_book_body(cat, cat["slot"], party=3)).status_code == 200

    assert client.get("/slots/occupancy").json()[0]["booked_count"] == 7


def test_the_slot_capacity_and_not_the_config_number_is_the_ceiling(client, db, auth, domain_config):
    """The row's own capacity still binds: an eighth head into a 7-seat slot is
    CAPACITY_EXCEEDED regardless of `maxBookingsPerSlot`."""
    domain_config(rules={"maxBookingsPerSlot": 20})
    auth(role="client")
    cat = make_catalog(db, capacity=7, slot_capacity=7)
    resp = client.post("/bookings", json=_book_body(cat, cat["slot"], party=8))
    assert resp.status_code == 409
    assert _detail_code(resp) == "CAPACITY_EXCEEDED"


# --- capabilities.reviews gates BOTH review directions ----------------------
#
# The block's contract is that a false capability hides the surface AND refuses
# the write. It shipped gating only the customer-facing review, so an owner
# could still write `client_reviews` — rows that feed the customer's public
# reputation — on a deployment with reviews turned off.


def test_customer_review_refused_when_reviews_capability_is_off(
    client, db, auth, domain_config
):
    domain_config(capabilities={"reviews": False})
    auth(role="client")
    cat = make_catalog(db)
    past = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-5)
    booking = make_booking(db, slots=[past], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/review", json={"rating": 5})
    assert resp.status_code == 404
    assert not [r for r in db.rows("reviews") if r["booking_id"] == booking["id"]]


def test_client_review_refused_when_reviews_capability_is_off(
    client, db, auth, domain_config
):
    domain_config(capabilities={"reviews": False})
    auth(role="owner")
    cat = make_catalog(db)
    booking = _completed(db, cat)
    resp = client.post(f"/bookings/{booking['id']}/client-review", json={"rating": 4})
    assert resp.status_code == 404
    assert not [r for r in db.rows("client_reviews") if r["booking_id"] == booking["id"]]


def test_both_review_directions_work_when_the_capability_is_on(client, db, auth, domain_config):
    """Guard against the gate being written so tightly it refuses everything."""
    domain_config(capabilities={"reviews": True})
    cat = make_catalog(db)

    auth(role="client")
    past = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-5)
    booking = make_booking(db, slots=[past], service=cat["service"])
    assert client.post(f"/bookings/{booking['id']}/review", json={"rating": 5}).status_code == 200

    auth(role="owner")
    owned = _completed(db, cat)
    assert (
        client.post(f"/bookings/{owned['id']}/client-review", json={"rating": 4}).status_code == 200
    )


# ---------------------------------------------------------------------------
# ownership narrowing on cancel / reschedule (regression)
# ---------------------------------------------------------------------------
#
# RLS's is_owner() lets ANY owner update any booking on the platform, so the
# routes narrow owner powers with `_assert_owns_booking`. Cancel and reschedule
# skipped that check for a while: any signed-in owner could cancel or move any
# customer's booking anywhere on the marketplace — with the cutoff waived.


def test_cancel_by_an_unrelated_owner_is_403(client, db, auth):
    auth(role="owner", id=OTHER_OWNER_ID)  # owns nothing in this catalog
    cat = make_catalog(db)  # provider owned by DEFAULT_OWNER_ID
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 403
    assert db.get_row("bookings", booking["id"])["status"] == "confirmed"


def test_reschedule_by_an_unrelated_owner_is_403(client, db, auth):
    auth(role="owner", id=OTHER_OWNER_ID)
    cat = make_catalog(db)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200)
    booking = make_booking(db, slots=[old], service=cat["service"])
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 403
    # nothing moved: the join rows still point at the original slot.
    held = [r["slot_id"] for r in db.rows("booking_slots") if r["booking_id"] == booking["id"]]
    assert held == [old["id"]]


def test_owner_reschedules_own_providers_booking_inside_the_cutoff(client, db, auth):
    """The cutoff waiver still applies to an owner acting on THEIR OWN
    provider's booking (the same override cancel has always had)."""
    auth(role="owner")  # DEFAULT_OWNER_ID owns the catalog provider
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200)
    booking = make_booking(db, slots=[old], service=cat["service"])  # made by a client
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 200
    assert resp.json()["slotIds"] == [new["id"]]


def test_an_owner_booking_on_anothers_business_acts_as_a_client(client, db, auth):
    """Owner powers hinge on owning the booking's PROVIDER, not on the role bit.
    An owner cancelling a booking they made as a customer of somebody else's
    business hits the cutoff like any client."""
    auth(role="owner")  # DEFAULT_OWNER_ID, but the catalog below isn't theirs
    cat = make_catalog(db, cancellation_cutoff_hours=24, owner_id=OTHER_OWNER_ID)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    booking = make_booking(db, slots=[slot], service=cat["service"], user_id=DEFAULT_OWNER_ID)
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 409
    assert _detail_code(resp) == "CUTOFF_PASSED"


def test_owner_cancels_their_own_walk_in_booking_inside_the_cutoff(client, db, auth):
    """A booking the owner recorded under their OWN account on their OWN
    provider (walk-in/phone entry) gets the owner cutoff waiver."""
    auth(role="owner")  # DEFAULT_OWNER_ID owns the catalog provider
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=2)
    booking = make_booking(db, slots=[slot], service=cat["service"], user_id=DEFAULT_OWNER_ID)
    resp = client.post(f"/bookings/{booking['id']}/cancel")
    assert resp.status_code == 200
    assert db.get_row("bookings", booking["id"])["status"] == "cancelled"


# ---------------------------------------------------------------------------
# reschedule repricing keeps the booking's shape (regression)
# ---------------------------------------------------------------------------


def test_reschedule_keeps_the_add_on_lines_in_the_price(client, db, auth, domain_config):
    """A pure time move must not silently drop paid add-ons: reschedule
    reprices with the STORED `options` lines, so the total still includes them."""
    domain_config(
        booking={"options": [
            {"key": "kit", "label": "Kit hire", "type": "boolean", "priceMinorUnits": 900},
        ]},
    )
    auth(role="client")
    cat = make_catalog(db, price_minor_units=1000)
    created = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
            "options": {"kit": True},
        },
    ).json()
    assert created["priceMinorUnits"] == 1900  # 1000 base + 900 add-on

    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=200)
    moved = client.post(
        f"/bookings/{created['id']}/reschedule", json={"newSlotIds": [new["id"]]}
    )
    assert moved.status_code == 200
    assert moved.json()["priceMinorUnits"] == 1900
    md = db.get_row("bookings", created["id"])["metadata"]
    assert any(line.get("key") == "option:kit" for line in md["price_breakdown"])


# ---------------------------------------------------------------------------
# reschedule honours the calendar closures (regression)
# ---------------------------------------------------------------------------


def test_reschedule_into_a_blackout_is_refused(client, db, auth, domain_config):
    """Book-then-reschedule must not be a two-step bypass into a closed day:
    the create-time blackout gate now runs on the NEW date too."""
    auth(role="client")
    cat = make_catalog(db, cancellation_cutoff_hours=24)
    old = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=300)
    booking = make_booking(db, slots=[old], service=cat["service"])
    closed_day = new["starts_at"][:10]
    domain_config(timing={"blackouts": [
        {"key": "closed", "label": "Stocktake", "startDate": closed_day, "endDate": closed_day},
    ]})
    resp = client.post(f"/bookings/{booking['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"
    assert "Stocktake" in resp.json()["detail"]["message"]
    # the booking still holds its original slot.
    held = [r["slot_id"] for r in db.rows("booking_slots") if r["booking_id"] == booking["id"]]
    assert held == [old["id"]]


# ---------------------------------------------------------------------------
# entitlement credits: consumed at create, refunded on reject / cancel
# ---------------------------------------------------------------------------
#
# Consumption happens at create even for `pending` requests, so before the fix
# a rejection (or a cancel) quietly burned a pass credit for a booking that
# never happened. The refund is stamped `credit_refunded`, so it can only ever
# happen once per booking.


def _credits_config(domain_config):
    domain_config(
        capabilities={"entitlements": True},
        entitlements={
            "enabled": True,
            "kind": "credits",
            "plans": [{"key": "ten-pass", "label": "10-pass", "kind": "credits",
                       "discountBps": 0}],
        },
    )


def test_reject_refunds_the_credit_a_pending_request_consumed(client, db, auth, domain_config):
    _credits_config(domain_config)
    cat = make_catalog(db, metadata={"auto_approve": False}, price_minor_units=1000)
    ent = make_entitlement(db, plan_key="ten-pass", credits_total=10)

    auth(role="client")
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
    assert resp.json()["status"] == "pending"
    bid = resp.json()["id"]
    # the pending request already consumed a credit...
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 1
    assert db.get_row("bookings", bid)["metadata"]["entitlement_id"] == ent["id"]

    # ...and the owner's rejection gives it back, exactly once.
    auth(role="owner")
    assert client.post(f"/bookings/{bid}/reject").status_code == 200
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 0
    assert db.get_row("bookings", bid)["metadata"]["credit_refunded"] is True

    assert client.post(f"/bookings/{bid}/reject").status_code == 200  # idempotent
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 0


def test_cancel_refunds_the_credit_exactly_once(client, db, auth, domain_config):
    _credits_config(domain_config)
    cat = make_catalog(db, price_minor_units=1000)
    ent = make_entitlement(db, plan_key="ten-pass", credits_total=10)

    auth(role="client")
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
    bid = resp.json()["id"]
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 1

    assert client.post(f"/bookings/{bid}/cancel").status_code == 200
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 0
    assert db.get_row("bookings", bid)["metadata"]["credit_refunded"] is True

    assert client.post(f"/bookings/{bid}/cancel").status_code == 200  # idempotent
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 0


# ---------------------------------------------------------------------------
# payment.currency falls back to the service's effective pricing (regression)
# ---------------------------------------------------------------------------


def test_payment_currency_falls_back_to_the_service_pricing(client, db, auth):
    """A seeded/legacy booking whose metadata never stored a currency must be
    reported in the service's effective currency, not a hard-coded EUR."""
    auth(role="client")
    cat = make_catalog(db, currency="USD", price_minor_units=1000)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(
        db, slots=[slot], service=cat["service"], metadata={"currency": None}
    )
    out = client.get(f"/bookings/{booking['id']}").json()
    assert out["payment"]["currency"] == "USD"


# ---------------------------------------------------------------------------
# the additive Booking keys: payment.payer / providerAvatarUrl / metadata
# ---------------------------------------------------------------------------


def test_payment_payer_reaches_the_wire_from_the_config(client, db, auth, domain_config):
    """`payments.payer` says WHO settles the bill — the customer, or a third
    party (an estate, an insurer, an employer). It is display-only, but the
    client cannot address an invoice without it, so it has to survive the whole
    create -> read path, not just `payment_state`."""
    domain_config(payments={"flow": "prepay", "payer": "third_party"})
    auth(role="client")
    cat = make_catalog(db, price_minor_units=5000)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    created = client.post("/bookings", json={
        "serviceId": cat["service"]["id"],
        "resourceId": cat["resource"]["id"],
        "slotIds": [slot["id"]],
        "partySize": 1,
    })
    assert created.status_code == 200, created.text
    assert created.json()["payment"]["payer"] == "third_party"
    # ...and on the read path too (a different serializer call site).
    fetched = client.get(f"/bookings/{created.json()['id']}").json()
    assert fetched["payment"]["payer"] == "third_party"


def test_payment_payer_defaults_to_customer(client, db, auth):
    auth(role="client")
    cat = make_catalog(db, price_minor_units=5000)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    assert client.get(f"/bookings/{booking['id']}").json()["payment"]["payer"] == "customer"


def test_payment_payer_is_resolved_per_service(client, db, auth, domain_config):
    """`payments` is an overridable block, so a marketplace can host a business
    billing an estate next to one billing the customer."""
    domain_config(payments={"flow": "prepay", "payer": "customer"})
    auth(role="client")
    cat = make_catalog(db, metadata={"payments": {"payer": "third_party"}})
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service=cat["service"])
    assert client.get(f"/bookings/{booking['id']}").json()["payment"]["payer"] == "third_party"


def test_bookings_list_embeds_the_provider_avatar(client, db, auth):
    """The list path resolves it in ONE batched query (`_provider_avatar_map`),
    which is the reason it is embedded at all — a bookings list must not fetch
    each provider by id to show a face."""
    auth(role="client")
    provider = make_provider(db, "Acme Fleet", metadata={"avatar_url": "http://img/acme.png"})
    svc = make_service(db, provider["id"], "S", price_minor_units=1000)
    res = make_resource(db, service_id=svc["id"])
    slot = make_slot(db, res["id"], service_id=svc["id"], hours_ahead=100)
    booking = make_booking(db, slots=[slot], service={**svc, "provider_id": provider["id"]})

    listed = client.get("/bookings?scope=all").json()
    assert [b["providerAvatarUrl"] for b in listed] == ["http://img/acme.png"]
    # Same value on the single-booking read and on a mutation response.
    assert client.get(f"/bookings/{booking['id']}").json()["providerAvatarUrl"] == \
        "http://img/acme.png"
    cancelled = client.post(f"/bookings/{booking['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["providerAvatarUrl"] == "http://img/acme.png"


def test_bookings_provider_without_an_avatar_serves_empty_string(client, db, auth):
    auth(role="client")
    cat = make_catalog(db)  # provider metadata carries no avatar_url
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    make_booking(db, slots=[slot], service=cat["service"])
    assert client.get("/bookings?scope=all").json()[0]["providerAvatarUrl"] == ""


def test_a_declared_meta_field_written_at_create_is_readable_back(
    client, db, auth, domain_config
):
    """The round trip the `metadata` key exists for: a pivot's custom booking
    field was writable (`meta.merged_metadata`) but not readable, so the app
    could collect it and never show it again. Engine-owned keys stay out of the
    echo — they have their own serialized shapes."""
    domain_config(metaFields={"bookings": [
        {"key": "subjectName", "label": "Name of the subject", "type": "text"},
    ]})
    auth(role="client")
    cat = make_catalog(db, price_minor_units=1000)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    created = client.post("/bookings", json={
        "serviceId": cat["service"]["id"],
        "resourceId": cat["resource"]["id"],
        "slotIds": [slot["id"]],
        "partySize": 1,
        "metadata": {"subjectName": "A. Kowalska"},
    })
    assert created.status_code == 200, created.text
    assert created.json()["metadata"] == {"subjectName": "A. Kowalska"}
    assert client.get(f"/bookings/{created.json()['id']}").json()["metadata"] == \
        {"subjectName": "A. Kowalska"}
    # The column really does hold the engine's own keys alongside it...
    stored = db.get_row("bookings", created.json()["id"])["metadata"]
    assert stored["subjectName"] == "A. Kowalska"
    assert stored["price_minor_units"] == 1000
    # ...and none of them leak into the echo.
    assert "price_minor_units" not in created.json()["metadata"]


def test_bookings_metadata_echoes_the_declared_key_and_drops_the_rest(client, db, auth):
    """Present on every booking regardless of the pivot, so the wire shape does
    not change between deployments — and filtered to what the config declares.
    The fixture config declares exactly one booking field, `note`."""
    auth(role="client")
    cat = make_catalog(db)
    slot = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=100)
    make_booking(
        db, slots=[slot], service=cat["service"],
        metadata={"note": "declared", "internalScore": 7},
    )
    listed = client.get("/bookings?scope=all").json()[0]
    assert listed["metadata"] == {"note": "declared"}


# ---------------------------------------------------------------------------
# review-fix regression pins (August 2026)
# ---------------------------------------------------------------------------


def test_reschedule_keeps_the_credit_receipt_and_the_plan_discount(
    client, db, auth, domain_config
):
    """The entitlement that priced a booking keeps pricing it across a move.

    Regression: reschedule re-resolved the customer's entitlements from
    scratch. A booking that consumed the pass's LAST credit then resolved to
    nothing — the `entitlement_id` receipt was nulled (so cancel could never
    refund the credit) and the booking was silently repriced at list price.
    """
    domain_config(
        capabilities={"entitlements": True},
        entitlements={
            "enabled": True,
            "kind": "credits",
            "plans": [{"key": "ten-pass", "label": "10-pass", "kind": "credits",
                       "discountBps": 10000}],  # 100% covered by the pass
        },
    )
    cat = make_catalog(db, price_minor_units=1000)
    ent = make_entitlement(db, plan_key="ten-pass", credits_total=1)  # the LAST credit

    auth(role="client")
    made = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
        },
    ).json()
    assert made["priceMinorUnits"] == 0  # fully discounted
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 1  # pass exhausted
    assert db.get_row("bookings", made["id"])["metadata"]["entitlement_id"] == ent["id"]

    new = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=72)
    resp = client.post(f"/bookings/{made['id']}/reschedule", json={"newSlotIds": [new["id"]]})
    assert resp.status_code == 200
    assert resp.json()["priceMinorUnits"] == 0  # still the plan price, not list 1000

    md = db.get_row("bookings", made["id"])["metadata"]
    assert md["entitlement_id"] == ent["id"]  # the consume receipt is immutable
    assert md["price_minor_units"] == 0

    # ...so the refund path still works after the move.
    assert client.post(f"/bookings/{made['id']}/cancel").status_code == 200
    assert db.get_row("entitlements", ent["id"])["credits_used"] == 0
    assert db.get_row("bookings", made["id"])["metadata"]["credit_refunded"] is True


def test_approve_a_cancelled_booking_is_invalid_range_not_403(client, db, auth):
    """Approving a booking that is no longer pending answers for the STATE
    (400 INVALID_RANGE), not a security-framed 403."""
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"], status="cancelled")
    auth(role="owner")
    resp = client.post(f"/bookings/{booking['id']}/approve")
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"
    assert resp.json()["detail"]["message"] == "Only pending requests can be approved."


def test_partial_payments_accumulate_and_settle(client, db, auth):
    """`/pay` preconditions on the PRIOR paid amount, so sequential payments
    each match: a part-payment then a "pay the rest" both commit, and a third
    attempt is refused because nothing is outstanding."""
    cat = make_catalog(db, price_minor_units=1000)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"])
    auth(role="owner")

    first = client.post(f"/bookings/{booking['id']}/pay", params={"amount": 400})
    assert first.status_code == 200
    assert first.json()["payment"]["paidMinorUnits"] == 400
    assert first.json()["payment"]["state"] == "due"

    second = client.post(f"/bookings/{booking['id']}/pay")  # defaults to the rest
    assert second.status_code == 200
    assert second.json()["payment"]["paidMinorUnits"] == 1000
    assert second.json()["payment"]["state"] == "paid"

    row = db.get_row("bookings", booking["id"])
    assert row["metadata"]["amount_paid_minor_units"] == 1000
    recorded = [h for h in row["history"] if h.get("status") == "payment_recorded"]
    assert [h["amount"] for h in recorded] == [400, 600]

    third = client.post(f"/bookings/{booking['id']}/pay")
    assert third.status_code == 400
    assert "nothing outstanding" in third.json()["detail"]["message"]


def test_return_twice_is_refused_not_restamped(client, db, auth, domain_config):
    """A second `/return` is a 400, and the original timestamp survives —
    re-stamping it would shrink a computed overdue fee."""
    domain_config(capabilities={"inventory": True}, inventory={"returnRequired": True})
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"])
    auth(role="owner")

    assert client.post(f"/bookings/{booking['id']}/return").status_code == 200
    stamp = db.get_row("bookings", booking["id"])["metadata"]["returned_at_utc"]
    assert stamp

    second = client.post(f"/bookings/{booking['id']}/return")
    assert second.status_code == 400
    assert "already marked returned" in second.json()["detail"]["message"]

    row = db.get_row("bookings", booking["id"])
    assert row["metadata"]["returned_at_utc"] == stamp  # not silently re-stamped
    assert sum(1 for h in row["history"] if h.get("status") == "returned") == 1


def test_list_bookings_includes_a_legacy_metadata_keyed_row(client, db, auth):
    """A row with `client_id` NULL and only `metadata.user_id` (pre-auth legacy)
    still shows up in the caller's GET /bookings — and nobody else's."""
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"])
    db.table("bookings").update({"client_id": None}).eq("id", booking["id"]).execute()
    assert db.get_row("bookings", booking["id"])["client_id"] is None

    auth(role="client")  # DEFAULT_USER_ID == the row's metadata.user_id
    listed = client.get("/bookings").json()
    assert [b["id"] for b in listed] == [booking["id"]]

    auth(role="client", id="66666666-6666-6666-6666-666666666666", email="x@example.com")
    assert client.get("/bookings").json() == []
