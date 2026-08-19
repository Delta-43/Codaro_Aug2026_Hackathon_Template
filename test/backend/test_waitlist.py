"""/slots/{id}/waitlist — the queue for a full slot, plus auto-promotion.

`timing.waitlist` + `capabilities.waitlist` gate the whole surface (both off in
the fixture config, so every test that wants a queue turns them on explicitly —
proving the behaviour is config-driven). Promotion is exercised through the
real cancel endpoint: freeing a seat hands it to the head of the queue as a
PENDING booking (the customer never agreed to a specific booking, so it must
not auto-confirm or hold capacity).
"""

from __future__ import annotations

from helpers import DEFAULT_USER_ID, make_booking, make_catalog, make_slot

USER_A = DEFAULT_USER_ID
USER_B = "44444444-4444-4444-4444-444444444444"
USER_C = "55555555-5555-5555-5555-555555555555"

ENTRY_KEYS = {
    "id",
    "slotId",
    "serviceId",
    "resourceId",
    "partySize",
    "position",
    "status",
    "bookingId",
    "createdAtUtc",
    "peopleAhead",
}


def _detail_code(resp) -> str:
    return resp.json()["detail"]["code"]


def _waitlist_on(domain_config, *, auto_promote: bool = True, max_per_slot: int = 0):
    domain_config(
        capabilities={"waitlist": True},
        timing={"waitlist": {
            "enabled": True, "autoPromote": auto_promote, "maxPerSlot": max_per_slot,
        }},
    )


def _full_catalog(db):
    """A capacity-1 catalog whose only slot is already booked by USER_A."""
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"], user_id=USER_A)
    return cat, booking


# --- join -------------------------------------------------------------------


def test_join_requires_a_token(client, db):
    cat = make_catalog(db)
    assert client.post(f"/slots/{cat['slot']['id']}/waitlist").status_code == 401


def test_join_refused_when_the_capability_is_off(client, db, auth):
    """The fixture config leaves `capabilities.waitlist` off — the surface must
    not exist there."""
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    resp = client.post(f"/slots/{cat['slot']['id']}/waitlist")
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"


def test_join_refuses_a_slot_that_is_still_bookable(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    cat = make_catalog(db)  # nobody booked: one seat free
    auth(role="client", id=USER_B, email="b@example.com")
    resp = client.post(f"/slots/{cat['slot']['id']}/waitlist")
    assert resp.status_code == 400
    assert "available" in resp.json()["detail"]["message"]
    assert db.count("waitlist_entries") == 0


def test_join_a_past_slot_is_refused(client, db, auth, domain_config):
    """A queue place on an elapsed slot would mint a pending booking for a time
    that already happened when a cancellation frees it (regression)."""
    _waitlist_on(domain_config)
    cat = make_catalog(db)
    past = make_slot(db, cat["resource"]["id"], service_id=cat["service"]["id"], hours_ahead=-2)
    auth(role="client", id=USER_B, email="b@example.com")
    resp = client.post(f"/slots/{past['id']}/waitlist")
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"
    assert db.count("waitlist_entries") == 0


def test_join_an_unknown_slot_is_404(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    auth(role="client")
    assert client.post("/slots/ghost/waitlist").status_code == 404


def test_join_a_full_slot_takes_a_place(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    resp = client.post(f"/slots/{cat['slot']['id']}/waitlist")
    assert resp.status_code == 200
    entry = resp.json()
    assert set(entry) == ENTRY_KEYS
    assert entry["slotId"] == cat["slot"]["id"]
    assert entry["serviceId"] == cat["service"]["id"]  # denormalised at join
    assert entry["status"] == "waiting"
    assert entry["position"] == 1
    assert entry["peopleAhead"] == 0


def test_double_join_is_idempotent(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    first = client.post(f"/slots/{cat['slot']['id']}/waitlist").json()
    second = client.post(f"/slots/{cat['slot']['id']}/waitlist")
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert db.count("waitlist_entries") == 1


def test_the_queue_cap_is_enforced(client, db, auth, domain_config):
    _waitlist_on(domain_config, max_per_slot=1)
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    assert client.post(f"/slots/{cat['slot']['id']}/waitlist").status_code == 200
    auth(role="client", id=USER_C, email="c@example.com")
    resp = client.post(f"/slots/{cat['slot']['id']}/waitlist")
    assert resp.status_code == 400
    assert "full" in resp.json()["detail"]["message"]
    assert db.count("waitlist_entries") == 1


# --- leave + my place -------------------------------------------------------


def test_leave_gives_up_the_place(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")
    resp = client.delete(f"/slots/{cat['slot']['id']}/waitlist")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert db.rows("waitlist_entries")[0]["status"] == "cancelled"
    place = client.get(f"/slots/{cat['slot']['id']}/waitlist").json()
    assert place == {"entry": None, "depth": 0}


def test_my_place_counts_the_people_ahead(client, db, auth, domain_config):
    _waitlist_on(domain_config)
    cat, _booking = _full_catalog(db)
    auth(role="client", id=USER_B, email="b@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")
    auth(role="client", id=USER_C, email="c@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")
    place = client.get(f"/slots/{cat['slot']['id']}/waitlist").json()
    assert place["depth"] == 2
    assert place["entry"]["peopleAhead"] == 1
    assert place["entry"]["status"] == "waiting"


# --- promotion on cancel ----------------------------------------------------


def test_cancel_promotes_the_head_of_the_queue_as_a_pending_booking(
    client, db, auth, domain_config
):
    _waitlist_on(domain_config, auto_promote=True)
    cat, booking = _full_catalog(db)
    db.seed_auth_user(USER_B, email="b@example.com")  # promotion resolves the email
    auth(role="client", id=USER_B, email="b@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")
    auth(role="client", id=USER_C, email="c@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")

    # the seat frees: the customer holding it cancels.
    auth(role="client", id=USER_A, email="guest@example.com")
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 200

    made = [b for b in db.rows("bookings") if b.get("client_id") == USER_B]
    assert len(made) == 1
    promoted_booking = made[0]
    # pending — the customer joined a queue, they never agreed to a booking.
    assert promoted_booking["status"] == "pending"
    assert promoted_booking["client_email"] == "b@example.com"
    md = promoted_booking["metadata"]
    assert md["from_waitlist"] is True
    assert md["slot_ids"] == [cat["slot"]["id"]]
    assert md["service_id"] == cat["service"]["id"]

    entries = {e["user_id"]: e for e in db.rows("waitlist_entries")}
    assert entries[USER_B]["status"] == "promoted"  # the head, not the tail
    assert entries[USER_B]["booking_id"] == promoted_booking["id"]
    assert entries[USER_C]["status"] == "waiting"

    # pending holds no capacity: the seat stays live for whoever acts first.
    occ = next(
        r for r in client.get("/slots/occupancy").json()
        if r["slot_id"] == cat["slot"]["id"]
    )
    assert occ["booked_count"] == 0


def test_no_promotion_when_auto_promote_is_off(client, db, auth, domain_config):
    """`autoPromote: false` records the queue for the owner to work manually —
    a cancellation must not commit anyone."""
    _waitlist_on(domain_config, auto_promote=False)
    cat, booking = _full_catalog(db)
    db.seed_auth_user(USER_B, email="b@example.com")
    auth(role="client", id=USER_B, email="b@example.com")
    client.post(f"/slots/{cat['slot']['id']}/waitlist")

    auth(role="client", id=USER_A, email="guest@example.com")
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 200

    assert db.count("bookings") == 1  # only the cancelled one
    assert db.rows("waitlist_entries")[0]["status"] == "waiting"
