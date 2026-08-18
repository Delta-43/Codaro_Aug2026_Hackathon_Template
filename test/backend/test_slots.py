"""/slots — public reads (+ /slots/occupancy) and owner-gated writes.

`POST /slots` derives `ends_at` from `rules.slotDurationMinutes` and defaults
`capacity` from `rules.maxBookingsPerSlot` (no magic literals), runs the
`slot.create` buffer rule, and validates metadata. Occupancy is the derived view
that sums party size across confirmed bookings via `booking_slots`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import iso_in, make_booking, make_catalog, make_resource, make_service, make_slot


# --- reads -----------------------------------------------------------------


def test_list_slots_public(client, db):
    res = make_resource(db)
    make_slot(db, res["id"])
    rows = client.get("/slots").json()
    assert len(rows) == 1
    assert rows[0]["resource_id"] == res["id"]


def test_list_slots_filtered_by_resource(client, db):
    a = make_resource(db, "A")
    b = make_resource(db, "B")
    make_slot(db, a["id"])
    make_slot(db, b["id"])
    rows = client.get("/slots", params={"resource_id": a["id"]}).json()
    assert [r["resource_id"] for r in rows] == [a["id"]]


def test_occupancy_reflects_party_size(client, db):
    cat = make_catalog(db, capacity=5, slot_capacity=5)
    make_booking(db, slots=[cat["slot"]], service=cat["service"], party_size=3)
    rows = client.get("/slots/occupancy", params={"resource_id": cat["resource"]["id"]}).json()
    row = next(r for r in rows if r["slot_id"] == cat["slot"]["id"])
    assert row["booked_count"] == 3
    assert row["available_count"] == 2


def test_occupancy_excludes_cancelled(client, db):
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    make_booking(db, slots=[cat["slot"]], service=cat["service"], status="cancelled")
    row = client.get("/slots/occupancy").json()[0]
    assert row["booked_count"] == 0


# --- owner-gated create ----------------------------------------------------


def test_create_requires_owner(client, db, auth):
    res = make_resource(db)
    auth(role="client")
    resp = client.post("/slots", json={"resource_id": res["id"], "starts_at": iso_in(hours=48)})
    assert resp.status_code == 403


def test_create_derives_end_and_capacity_from_config(client, db, auth):
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    resp = client.post("/slots", json={"resource_id": res["id"], "starts_at": start})
    assert resp.status_code == 200
    slot = resp.json()[0]
    # fixture config: slotDurationMinutes=30, maxBookingsPerSlot=1
    expected_end = (datetime.fromisoformat(start) + timedelta(minutes=30)).isoformat()
    assert slot["ends_at"] == expected_end
    assert slot["capacity"] == 1


def test_create_honours_explicit_end_and_capacity(client, db, auth):
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    end = iso_in(hours=50)
    resp = client.post(
        "/slots",
        json={"resource_id": res["id"], "starts_at": start, "ends_at": end, "capacity": 7},
    )
    slot = resp.json()[0]
    assert slot["ends_at"] == end
    assert slot["capacity"] == 7


def test_create_enforces_buffer_rule(client, db, auth, domain_config):
    domain_config(rules={"bufferMinutes": 60})
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    make_slot(db, res["id"], starts_at=start, duration_minutes=30)
    # A new slot 10 min after the first ends still overlaps once padded by 60 min.
    clash = (datetime.fromisoformat(start) + timedelta(minutes=40)).isoformat()
    resp = client.post("/slots", json={"resource_id": res["id"], "starts_at": clash})
    assert resp.status_code == 409


def test_create_validates_metadata(client, db, auth, domain_config):
    domain_config(metaFields={"slots": [{"key": "bay", "label": "Bay", "type": "text"}]})
    auth(role="owner")
    res = make_resource(db)
    resp = client.post(
        "/slots", json={"resource_id": res["id"], "starts_at": iso_in(hours=48), "metadata": {"bay": 3}}
    )
    assert resp.status_code == 422


# --- owner-gated patch / delete -------------------------------------------


def test_patch_slot(client, db, auth):
    auth(role="owner")
    slot = make_slot(db)
    resp = client.patch(f"/slots/{slot['id']}", json={"capacity": 9})
    assert resp.status_code == 200
    assert db.get_row("slots", slot["id"])["capacity"] == 9


def test_patch_unknown_slot_is_404(client, db, auth):
    auth(role="owner")
    assert client.patch("/slots/nope", json={"capacity": 2}).status_code == 404


def test_delete_slot_is_204_and_cascades_bookings(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db)
    booking = make_booking(db, slots=[cat["slot"]], service=cat["service"])
    resp = client.delete(f"/slots/{cat['slot']['id']}")
    assert resp.status_code == 204
    assert db.get_row("slots", cat["slot"]["id"]) is None
    # cascade removed the booking and its join rows
    assert db.get_row("bookings", booking["id"]) is None
    assert db.count("booking_slots") == 0


def test_delete_unknown_slot_is_404(client, db, auth):
    auth(role="owner")
    assert client.delete("/slots/nope").status_code == 404


def test_delete_requires_owner(client, db, auth):
    auth(role="client")
    slot = make_slot(db)
    assert client.delete(f"/slots/{slot['id']}").status_code == 403


# --- config v2: slots.py reads `timing`, not `rules` -----------------------
#
# `slots.py` now resolves its defaults from `get_config()["timing"]`. Because
# `config_schema.normalize` mirrors the five legacy keys in BOTH directions, a
# v1 file declaring only `rules` and a v2 file declaring only `timing` must
# produce identical slots — that back-compat guarantee is what these pin.


def test_slot_defaults_can_be_declared_on_the_v2_timing_path(client, db, auth, domain_config):
    domain_config(timing={"slotDurationMinutes": 90, "maxBookingsPerSlot": 4})
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    slot = client.post("/slots", json={"resource_id": res["id"], "starts_at": start}).json()[0]
    assert slot["ends_at"] == (datetime.fromisoformat(start) + timedelta(minutes=90)).isoformat()
    assert slot["capacity"] == 4


def test_slot_defaults_declared_on_the_v1_rules_path_still_work(client, db, auth, domain_config):
    domain_config(rules={"slotDurationMinutes": 90, "maxBookingsPerSlot": 4})
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    slot = client.post("/slots", json={"resource_id": res["id"], "starts_at": start}).json()[0]
    assert slot["ends_at"] == (datetime.fromisoformat(start) + timedelta(minutes=90)).isoformat()
    assert slot["capacity"] == 4


def test_the_buffer_rule_can_also_be_declared_on_the_timing_path(client, db, auth, domain_config):
    domain_config(timing={"bufferMinutes": 60})
    auth(role="owner")
    res = make_resource(db)
    start = iso_in(hours=48)
    make_slot(db, res["id"], starts_at=start, duration_minutes=30)
    clash = (datetime.fromisoformat(start) + timedelta(minutes=40)).isoformat()
    assert client.post("/slots", json={"resource_id": res["id"], "starts_at": clash}).status_code == 409
