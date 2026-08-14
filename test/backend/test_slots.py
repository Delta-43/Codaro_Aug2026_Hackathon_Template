"""/slots, /slots/occupancy — the availability view."""

from datetime import datetime, timedelta

import pytest

from helpers import iso_in, make_booking, make_resource, make_slot


def test_list_slots_empty(client):
    response = client.get("/slots")
    assert response.status_code == 200
    assert response.json() == []


def test_list_slots_returns_every_row(client, db):
    resource = make_resource(db)
    make_slot(db, resource["id"], hours_ahead=48)
    make_slot(db, resource["id"], hours_ahead=72)

    response = client.get("/slots")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_slots_filters_by_resource_id(client, db):
    first = make_resource(db, name="Widget 1")
    second = make_resource(db, name="Widget 2")
    mine = make_slot(db, first["id"])
    make_slot(db, second["id"])
    make_slot(db, second["id"])

    response = client.get("/slots", params={"resource_id": first["id"]})
    assert response.status_code == 200
    body = response.json()
    assert [row["id"] for row in body] == [mine["id"]]
    assert all(row["resource_id"] == first["id"] for row in body)


def test_list_slots_unknown_resource_returns_empty(client, db):
    make_slot(db)
    response = client.get("/slots", params={"resource_id": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 200
    assert response.json() == []


def test_create_slot_persists_and_shows_up_in_listings(client, db):
    resource = make_resource(db)
    starts_at = iso_in(hours=48)
    ends_at = (datetime.fromisoformat(starts_at) + timedelta(minutes=30)).isoformat()

    response = client.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": starts_at,
            "ends_at": ends_at,
            "capacity": 2,
            "metadata": {"room": "A1"},
        },
    )
    assert response.status_code == 200
    created = response.json()[0]
    assert created["resource_id"] == resource["id"]
    assert created["capacity"] == 2
    assert created["metadata"] == {"room": "A1"}

    assert [row["id"] for row in client.get("/slots").json()] == [created["id"]]
    occupancy = client.get("/slots/occupancy").json()
    assert [row["slot_id"] for row in occupancy] == [created["id"]]


def test_create_slot_defaults_capacity_to_one(client, db):
    resource = make_resource(db)
    created = client.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": iso_in(hours=48),
            "ends_at": iso_in(hours=48.5),
        },
    ).json()[0]
    assert created["capacity"] == 1


# --------------------------------------------------------------------
# /slots/occupancy — the availability grid the frontend renders
# --------------------------------------------------------------------


def test_occupancy_shape_matches_the_sql_view(client, db):
    slot = make_slot(db, capacity=3)
    row = client.get("/slots/occupancy").json()[0]
    assert set(row) == {
        "slot_id",
        "resource_id",
        "starts_at",
        "ends_at",
        "capacity",
        "booked_count",
        "available_count",
    }
    assert row["slot_id"] == slot["id"]
    assert row["capacity"] == 3
    assert row["booked_count"] == 0
    assert row["available_count"] == 3


def test_occupancy_counts_confirmed_bookings(client, db):
    slot = make_slot(db, capacity=3)
    make_booking(db, slot["id"], client_email="a@example.com")
    make_booking(db, slot["id"], client_email="b@example.com")

    row = client.get("/slots/occupancy").json()[0]
    assert row["booked_count"] == 2
    assert row["available_count"] == 1


def test_occupancy_ignores_cancelled_bookings(client, db):
    slot = make_slot(db, capacity=1)
    make_booking(db, slot["id"], status="cancelled")

    row = client.get("/slots/occupancy").json()[0]
    assert row["booked_count"] == 0
    assert row["available_count"] == 1


def test_occupancy_filters_by_resource_id(client, db):
    first = make_resource(db, name="Widget 1")
    second = make_resource(db, name="Widget 2")
    mine = make_slot(db, first["id"])
    make_slot(db, second["id"])

    rows = client.get("/slots/occupancy", params={"resource_id": first["id"]}).json()
    assert [row["slot_id"] for row in rows] == [mine["id"]]


def test_occupancy_route_is_not_shadowed_by_the_list_route(client, db):
    """`/slots/occupancy` must resolve to the view, not to the slot list."""
    make_slot(db)
    rows = client.get("/slots/occupancy").json()
    assert rows and "booked_count" in rows[0]


def test_occupancy_updates_after_booking_through_the_api(client, db):
    slot = make_slot(db, capacity=2)
    client.post("/bookings", json={"slot_id": slot["id"], "client_email": "a@example.com"})

    row = client.get("/slots/occupancy").json()[0]
    assert row["booked_count"] == 1
    assert row["available_count"] == 1


def test_create_slot_derives_ends_at_from_slot_duration(client, db, domain_config):
    domain_config(rules={"slotDurationMinutes": 45})
    resource = make_resource(db)
    starts_at = iso_in(hours=48)

    response = client.post(
        "/slots", json={"resource_id": resource["id"], "starts_at": starts_at}
    )
    assert response.status_code == 200
    created = response.json()[0]
    expected = datetime.fromisoformat(starts_at) + timedelta(minutes=45)
    assert datetime.fromisoformat(created["ends_at"]) == expected


def test_create_slot_defaults_capacity_from_max_bookings_per_slot(client, db, domain_config):
    """When capacity is omitted, POST /slots falls back to
    rules.maxBookingsPerSlot (no magic literal)."""
    domain_config(rules={"maxBookingsPerSlot": 4})
    resource = make_resource(db)
    created = client.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": iso_in(hours=48),
            "ends_at": iso_in(hours=48.5),
        },
    ).json()[0]
    assert created["capacity"] == 4


def test_create_slot_missing_resource_id_returns_422(raw_client):
    response = raw_client.post("/slots", json={"starts_at": iso_in(hours=48)})
    assert response.status_code == 422


# --------------------------------------------------------------------
# PATCH /slots/{id}, DELETE /slots/{id}
# --------------------------------------------------------------------


def test_patch_slot_partial_update(client, db):
    slot = make_slot(db, capacity=1)
    response = client.patch(f"/slots/{slot['id']}", json={"capacity": 5})
    assert response.status_code == 200
    updated = response.json()[0]
    assert updated["capacity"] == 5
    assert updated["starts_at"] == slot["starts_at"]  # untouched
    assert db.get_row("slots", slot["id"])["capacity"] == 5


def test_patch_slot_unknown_id_returns_404(client):
    response = client.patch(
        "/slots/00000000-0000-0000-0000-000000000000", json={"capacity": 2}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Slot not found"


def test_delete_slot_returns_204_and_removes_it(client, db):
    slot = make_slot(db)
    response = client.delete(f"/slots/{slot['id']}")
    assert response.status_code == 204
    assert not response.content
    assert db.get_row("slots", slot["id"]) is None
    assert client.get("/slots").json() == []


def test_delete_slot_cascade_removes_dependent_bookings(client, db):
    slot = make_slot(db)
    make_booking(db, slot["id"], client_email="a@example.com")
    make_booking(db, slot["id"], client_email="b@example.com")
    assert db.count("bookings") == 2

    client.delete(f"/slots/{slot['id']}")
    assert db.count("bookings") == 0


def test_delete_slot_unknown_id_returns_404(client):
    response = client.delete("/slots/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Slot not found"
