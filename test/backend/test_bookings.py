"""/bookings — create, cancel, reschedule, list.

Covers the Track B checklist items "Booking and Confirmation", "Change and
Cancellation" and "Status and History", plus the two config-driven rules the
routers enforce (maxBookingsPerSlot, cancellationWindowHours).
"""

from datetime import datetime

import pytest

from helpers import iso_in, make_booking, make_resource, make_slot, occupancy_for


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --------------------------------------------------------------------
# POST /bookings
# --------------------------------------------------------------------


def test_create_booking_confirms_and_starts_the_history(client, db):
    slot = make_slot(db, hours_ahead=48)

    response = client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "guest@example.com"}
    )
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list) and len(body) == 1
    booking = body[0]
    assert booking["slot_id"] == slot["id"]
    assert booking["client_email"] == "guest@example.com"
    assert booking["status"] == "confirmed"
    assert len(booking["history"]) == 1
    assert booking["history"][0]["status"] == "confirmed"
    assert parse_iso(booking["history"][0]["at"]).tzinfo is not None

    assert db.count("bookings") == 1


def test_create_booking_keeps_extra_payload_fields(client, db):
    slot = make_slot(db)
    booking = client.post(
        "/bookings",
        json={
            "slot_id": slot["id"],
            "client_email": "guest@example.com",
            "client_id": "guest-42",
            "metadata": {"note": "window seat"},
        },
    ).json()[0]
    assert booking["client_id"] == "guest-42"
    assert booking["metadata"] == {"note": "window seat"}


def test_create_booking_consumes_capacity(client, db):
    slot = make_slot(db, capacity=1)
    client.post("/bookings", json={"slot_id": slot["id"], "client_email": "a@example.com"})
    assert occupancy_for(db, slot["id"])["available_count"] == 0


def test_create_booking_on_a_full_slot_returns_409(client, db, domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    slot = make_slot(db, capacity=1)
    make_booking(db, slot["id"], client_email="first@example.com")

    response = client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "second@example.com"}
    )
    assert response.status_code == 409
    assert "fully booked" in response.json()["detail"]
    assert db.count("bookings") == 1  # nothing written


def test_capacity_limit_is_config_driven(client, db, domain_config):
    """Same slot row, different maxBookingsPerSlot -> different verdict."""
    domain_config(rules={"maxBookingsPerSlot": 2})
    slot = make_slot(db, capacity=5)

    first = client.post("/bookings", json={"slot_id": slot["id"], "client_email": "a@example.com"})
    second = client.post("/bookings", json={"slot_id": slot["id"], "client_email": "b@example.com"})
    assert first.status_code == 200
    assert second.status_code == 200

    third = client.post("/bookings", json={"slot_id": slot["id"], "client_email": "c@example.com"})
    assert third.status_code == 409  # min(capacity=5, maxBookingsPerSlot=2)

    domain_config(rules={"maxBookingsPerSlot": 3})
    assert client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "c@example.com"}
    ).status_code == 200


def test_row_capacity_binds_when_it_is_lower_than_the_config(client, db, domain_config):
    domain_config(rules={"maxBookingsPerSlot": 10})
    slot = make_slot(db, capacity=1)

    assert client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "a@example.com"}
    ).status_code == 200
    assert client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "b@example.com"}
    ).status_code == 409


def test_cancelled_booking_frees_the_slot_again(client, db, domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    slot = make_slot(db, capacity=1)
    make_booking(db, slot["id"], status="cancelled")

    response = client.post(
        "/bookings", json={"slot_id": slot["id"], "client_email": "new@example.com"}
    )
    assert response.status_code == 200


def test_create_booking_unknown_slot_returns_404(client):
    response = client.post(
        "/bookings",
        json={"slot_id": "00000000-0000-0000-0000-000000000000", "client_email": "a@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Slot not found"


@pytest.mark.xfail(
    reason="Against real PostgREST, .single() on zero rows raises APIError "
    "(PGRST116) rather than returning None, so the `if slot is None -> 404` "
    "branch in create_booking() is unreachable and the request 500s. Needs "
    "maybe_single() or an APIError guard.",
)
def test_create_booking_unknown_slot_404_against_real_postgrest(strict_client):
    response = strict_client.post(
        "/bookings",
        json={"slot_id": "00000000-0000-0000-0000-000000000000", "client_email": "a@example.com"},
    )
    assert response.status_code == 404


@pytest.mark.xfail(
    reason="POST /bookings takes a raw dict (no Pydantic model), so a payload "
    "without slot_id raises KeyError -> 500 instead of a 422.",
)
def test_create_booking_missing_slot_id_should_422(raw_client):
    response = raw_client.post("/bookings", json={"client_email": "a@example.com"})
    assert response.status_code == 422


def test_create_booking_missing_slot_id_current_behaviour(raw_client):
    assert raw_client.post("/bookings", json={"client_email": "a@example.com"}).status_code == 500


@pytest.mark.xfail(
    reason="client_email is only enforced by the DB NOT NULL constraint; the "
    "endpoint should reject the payload with 422 before writing.",
)
def test_create_booking_missing_client_email_should_422(raw_client, db):
    slot = make_slot(db)
    response = raw_client.post("/bookings", json={"slot_id": slot["id"]})
    assert response.status_code == 422


# --------------------------------------------------------------------
# GET /bookings
# --------------------------------------------------------------------


def test_list_bookings_empty(client):
    response = client.get("/bookings")
    assert response.status_code == 200
    assert response.json() == []


def test_list_bookings_returns_every_row(client, db):
    slot = make_slot(db)
    make_booking(db, slot["id"], client_email="a@example.com")
    make_booking(db, slot["id"], client_email="b@example.com")

    assert len(client.get("/bookings").json()) == 2


def test_list_bookings_filters_by_client_email(client, db):
    slot = make_slot(db, capacity=5)
    mine = make_booking(db, slot["id"], client_email="me@example.com")
    make_booking(db, slot["id"], client_email="someone@example.com")

    rows = client.get("/bookings", params={"client_email": "me@example.com"}).json()
    assert [row["id"] for row in rows] == [mine["id"]]


def test_list_bookings_unknown_email_returns_empty(client, db):
    slot = make_slot(db)
    make_booking(db, slot["id"], client_email="a@example.com")
    assert client.get("/bookings", params={"client_email": "nope@example.com"}).json() == []


def test_list_bookings_includes_status_and_history(client, db):
    slot = make_slot(db)
    make_booking(db, slot["id"])
    row = client.get("/bookings").json()[0]
    assert row["status"] == "confirmed"
    assert isinstance(row["history"], list) and row["history"]


# --------------------------------------------------------------------
# POST /bookings/{id}/cancel
# --------------------------------------------------------------------


def test_cancel_sets_status_and_appends_to_history(client, db, domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    original_entry = booking["history"][0]

    response = client.post(f"/bookings/{booking['id']}/cancel")
    assert response.status_code == 200

    cancelled = response.json()[0]
    assert cancelled["status"] == "cancelled"
    # append-only: the original entry survives untouched, in order
    assert len(cancelled["history"]) == 2
    assert cancelled["history"][0] == original_entry
    assert cancelled["history"][1]["status"] == "cancelled"
    assert parse_iso(cancelled["history"][1]["at"]).tzinfo is not None

    stored = db.get_row("bookings", booking["id"])
    assert stored["status"] == "cancelled"
    assert len(stored["history"]) == 2


def test_cancel_frees_the_slot_in_the_occupancy_view(client, db):
    slot = make_slot(db, capacity=1, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    assert occupancy_for(db, slot["id"])["available_count"] == 0

    client.post(f"/bookings/{booking['id']}/cancel")
    assert occupancy_for(db, slot["id"])["available_count"] == 1


def test_cancel_inside_the_window_returns_409(client, db, domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    slot = make_slot(db, hours_ahead=2)
    booking = make_booking(db, slot["id"])

    response = client.post(f"/bookings/{booking['id']}/cancel")
    assert response.status_code == 409
    assert "24h" in response.json()["detail"]
    assert db.get_row("bookings", booking["id"])["status"] == "confirmed"
    assert len(db.get_row("bookings", booking["id"])["history"]) == 1  # nothing appended


def test_cancellation_window_is_config_driven(client, db, domain_config):
    slot = make_slot(db, hours_ahead=5)
    booking = make_booking(db, slot["id"])

    domain_config(rules={"cancellationWindowHours": 24})
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 409

    domain_config(rules={"cancellationWindowHours": 2})
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 200


def test_cancel_unknown_booking_returns_404(client):
    response = client.post("/bookings/00000000-0000-0000-0000-000000000000/cancel")
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


@pytest.mark.xfail(
    reason="Real PostgREST raises PGRST116 from .single() on zero rows, so the "
    "`if booking is None -> 404` branch never runs against a live Supabase.",
)
def test_cancel_unknown_booking_404_against_real_postgrest(strict_client):
    response = strict_client.post("/bookings/00000000-0000-0000-0000-000000000000/cancel")
    assert response.status_code == 404


def test_cancel_twice_current_behaviour(client, db):
    """No status guard today: a second cancel succeeds and appends again."""
    slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    client.post(f"/bookings/{booking['id']}/cancel")

    second = client.post(f"/bookings/{booking['id']}/cancel")
    assert second.status_code == 200
    assert len(second.json()[0]["history"]) == 3


@pytest.mark.xfail(
    reason="cancel_booking() never checks the current status, so an already "
    "cancelled booking can be cancelled again; it should be a 409.",
)
def test_cancel_twice_should_409(client, db):
    slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    client.post(f"/bookings/{booking['id']}/cancel")
    assert client.post(f"/bookings/{booking['id']}/cancel").status_code == 409


@pytest.mark.xfail(
    reason="cancel_booking() does datetime.fromisoformat(slot['starts_at']) and "
    "subtracts an aware now(); a stored timestamp without an offset yields a "
    "naive datetime -> TypeError -> 500 instead of a clean response.",
)
def test_cancel_handles_a_naive_slot_timestamp(raw_client, db):
    slot = make_slot(db, starts_at="2099-01-01T10:00:00", ends_at="2099-01-01T10:30:00")
    booking = make_booking(db, slot["id"])
    response = raw_client.post(f"/bookings/{booking['id']}/cancel")
    assert response.status_code == 200


# --------------------------------------------------------------------
# POST /bookings/{id}/reschedule
# --------------------------------------------------------------------


def test_reschedule_moves_the_slot_and_appends_history(client, db, domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    resource = make_resource(db)
    old_slot = make_slot(db, resource["id"], hours_ahead=72)
    new_slot = make_slot(db, resource["id"], hours_ahead=96)
    booking = make_booking(db, old_slot["id"])
    original_entry = booking["history"][0]

    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": new_slot["id"]}
    )
    assert response.status_code == 200

    updated = response.json()[0]
    assert updated["slot_id"] == new_slot["id"]
    assert updated["status"] == "confirmed"
    assert len(updated["history"]) == 2
    assert updated["history"][0] == original_entry  # append-only
    assert updated["history"][1]["status"] == "rescheduled"

    assert db.get_row("bookings", booking["id"])["slot_id"] == new_slot["id"]


def test_reschedule_moves_occupancy_between_slots(client, db):
    resource = make_resource(db)
    old_slot = make_slot(db, resource["id"], hours_ahead=72, capacity=1)
    new_slot = make_slot(db, resource["id"], hours_ahead=96, capacity=1)
    booking = make_booking(db, old_slot["id"])

    client.post(f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": new_slot["id"]})

    assert occupancy_for(db, old_slot["id"])["booked_count"] == 0
    assert occupancy_for(db, new_slot["id"])["booked_count"] == 1


def test_reschedule_inside_the_window_returns_409(client, db, domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    old_slot = make_slot(db, hours_ahead=3)
    new_slot = make_slot(db, hours_ahead=96)
    booking = make_booking(db, old_slot["id"])

    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": new_slot["id"]}
    )
    assert response.status_code == 409
    assert "24h" in response.json()["detail"]
    stored = db.get_row("bookings", booking["id"])
    assert stored["slot_id"] == old_slot["id"]
    assert len(stored["history"]) == 1


def test_reschedule_to_a_full_slot_returns_409(client, db, domain_config):
    domain_config(rules={"cancellationWindowHours": 24, "maxBookingsPerSlot": 1})
    old_slot = make_slot(db, hours_ahead=72)
    full_slot = make_slot(db, hours_ahead=96, capacity=1)
    make_booking(db, full_slot["id"], client_email="other@example.com")
    booking = make_booking(db, old_slot["id"])

    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": full_slot["id"]}
    )
    assert response.status_code == 409
    assert "fully booked" in response.json()["detail"]
    assert db.get_row("bookings", booking["id"])["slot_id"] == old_slot["id"]


def test_reschedule_to_unknown_slot_returns_404(client, db):
    old_slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, old_slot["id"])

    response = client.post(
        f"/bookings/{booking['id']}/reschedule",
        json={"new_slot_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "New slot not found"


def test_reschedule_unknown_booking_returns_404(client, db):
    slot = make_slot(db, hours_ahead=72)
    response = client.post(
        "/bookings/00000000-0000-0000-0000-000000000000/reschedule",
        json={"new_slot_id": slot["id"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"


def test_reschedule_onto_the_same_slot_current_behaviour(client, db, domain_config):
    """The booking counts against its own target slot, so a capacity-1
    self-reschedule is rejected as "fully booked"."""
    domain_config(rules={"maxBookingsPerSlot": 1})
    slot = make_slot(db, hours_ahead=72, capacity=1)
    booking = make_booking(db, slot["id"])

    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": slot["id"]}
    )
    assert response.status_code == 409


@pytest.mark.xfail(
    reason="reschedule_booking() counts the booking being moved against the "
    "target slot's occupancy, so moving a booking onto its own slot is "
    "reported as full.",
)
def test_reschedule_onto_the_same_slot_should_succeed(client, db, domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    slot = make_slot(db, hours_ahead=72, capacity=1)
    booking = make_booking(db, slot["id"])
    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": slot["id"]}
    )
    assert response.status_code == 200


@pytest.mark.xfail(
    reason="reschedule payload is a raw dict; a missing new_slot_id raises "
    "KeyError -> 500 instead of 422.",
)
def test_reschedule_missing_new_slot_id_should_422(raw_client, db):
    slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    response = raw_client.post(f"/bookings/{booking['id']}/reschedule", json={})
    assert response.status_code == 422


def test_reschedule_missing_new_slot_id_current_behaviour(raw_client, db):
    slot = make_slot(db, hours_ahead=72)
    booking = make_booking(db, slot["id"])
    assert raw_client.post(f"/bookings/{booking['id']}/reschedule", json={}).status_code == 500


def test_reschedule_keeps_history_append_only_across_several_moves(client, db):
    resource = make_resource(db)
    slot_a = make_slot(db, resource["id"], hours_ahead=72)
    slot_b = make_slot(db, resource["id"], hours_ahead=96)
    slot_c = make_slot(db, resource["id"], hours_ahead=120)
    booking = make_booking(db, slot_a["id"])

    client.post(f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": slot_b["id"]})
    client.post(f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": slot_c["id"]})
    final = client.post(f"/bookings/{booking['id']}/cancel").json()[0]

    assert [entry["status"] for entry in final["history"]] == [
        "confirmed",
        "rescheduled",
        "rescheduled",
        "cancelled",
    ]
    timestamps = [parse_iso(entry["at"]) for entry in final["history"]]
    assert timestamps == sorted(timestamps)


def test_reschedule_of_a_cancelled_booking_current_behaviour(client, db):
    """No status guard: cancelling then rescheduling re-confirms the booking."""
    resource = make_resource(db)
    slot_a = make_slot(db, resource["id"], hours_ahead=72)
    slot_b = make_slot(db, resource["id"], hours_ahead=96)
    booking = make_booking(db, slot_a["id"])
    client.post(f"/bookings/{booking['id']}/cancel")

    response = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": slot_b["id"]}
    )
    assert response.status_code == 200
    assert response.json()[0]["status"] == "confirmed"


def test_booking_flow_end_to_end(client, db, domain_config):
    """config -> resource -> slot -> book -> occupancy -> reschedule -> cancel."""
    domain_config(rules={"cancellationWindowHours": 24, "maxBookingsPerSlot": 1})
    rules = client.get("/config").json()["rules"]
    assert rules["maxBookingsPerSlot"] == 1

    resource = client.post("/resources", json={"name": "Widget 1", "metadata": {}}).json()[0]
    first = client.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": iso_in(hours=72),
            "ends_at": iso_in(hours=72.5),
            "capacity": 1,
        },
    ).json()[0]
    second = client.post(
        "/slots",
        json={
            "resource_id": resource["id"],
            "starts_at": iso_in(hours=96),
            "ends_at": iso_in(hours=96.5),
            "capacity": 1,
        },
    ).json()[0]

    booking = client.post(
        "/bookings", json={"slot_id": first["id"], "client_email": "guest@example.com"}
    ).json()[0]

    occupancy = {row["slot_id"]: row for row in client.get("/slots/occupancy").json()}
    assert occupancy[first["id"]]["available_count"] == 0
    assert occupancy[second["id"]]["available_count"] == 1

    assert client.post(
        "/bookings", json={"slot_id": first["id"], "client_email": "other@example.com"}
    ).status_code == 409

    moved = client.post(
        f"/bookings/{booking['id']}/reschedule", json={"new_slot_id": second["id"]}
    ).json()[0]
    assert moved["slot_id"] == second["id"]

    cancelled = client.post(f"/bookings/{booking['id']}/cancel").json()[0]
    assert cancelled["status"] == "cancelled"

    mine = client.get("/bookings", params={"client_email": "guest@example.com"}).json()
    assert len(mine) == 1
    assert [entry["status"] for entry in mine[0]["history"]] == [
        "confirmed",
        "rescheduled",
        "cancelled",
    ]

    occupancy = {row["slot_id"]: row for row in client.get("/slots/occupancy").json()}
    assert occupancy[second["id"]]["available_count"] == 1
