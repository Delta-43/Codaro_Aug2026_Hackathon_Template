"""/resources — public reads + owner-gated writes, through the real endpoints.

Reads are open; create/patch/analytics require the owner role (`require_owner`).
The `auth` fixture stubs token verification and lets a test run as anon / client
/ owner so the gating is genuinely exercised.
"""

from __future__ import annotations

from helpers import (
    DEFAULT_OWNER_ID,
    make_booking,
    make_catalog,
    make_resource,
    make_slot,
)

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"


# --- public reads ----------------------------------------------------------


def test_list_resources_is_public_and_camelcase(client, db):
    make_resource(db, "Unit 1", service_id="svc-1", capacity=2)
    rows = client.get("/resources").json()
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == {
        "id",
        "serviceId",
        "name",
        "description",
        "imageUrl",
        "capacity",
        "attributes",
        "active",
    }
    assert r["serviceId"] == "svc-1"
    assert r["capacity"] == 2


def test_list_filtered_by_service_returns_only_active(client, db):
    make_resource(db, "Active", service_id="svc-1", active=True)
    make_resource(db, "Inactive", service_id="svc-1", active=False)
    make_resource(db, "Other", service_id="svc-2", active=True)
    rows = client.get("/resources", params={"service_id": "svc-1"}).json()
    assert [r["name"] for r in rows] == ["Active"]


def test_get_resource_by_id(client, db):
    res = make_resource(db, "Unit X", service_id="svc-1")
    got = client.get(f"/resources/{res['id']}").json()
    assert got["id"] == res["id"]
    assert got["name"] == "Unit X"


def test_get_unknown_resource_is_404(client, db):
    assert client.get("/resources/does-not-exist").status_code == 404


# --- owner-gated create ----------------------------------------------------


def test_create_without_a_token_is_401(client, db):
    resp = client.post("/resources", json={"name": "New", "metadata": {}})
    assert resp.status_code == 401


def test_create_as_client_is_403(client, db, auth):
    auth(role="client")
    resp = client.post("/resources", json={"name": "New", "metadata": {}})
    assert resp.status_code == 403


def test_create_as_owner_returns_serialized_resource(client, db, auth):
    owner = auth(role="owner")
    resp = client.post(
        "/resources", json={"name": "New Unit", "metadata": {"room": "A"}}
    )
    assert resp.status_code == 200
    body = resp.json()
    # create now returns a single serialized Resource (camelCase), not a raw
    # PostgREST row list.
    assert isinstance(body, dict)
    assert set(body) == {
        "id",
        "serviceId",
        "name",
        "description",
        "imageUrl",
        "capacity",
        "attributes",
        "active",
    }
    assert body["name"] == "New Unit"
    # serialize_resource intentionally does NOT expose owner_id; assert the
    # ownership stamp via the stored row's metadata instead.
    stored = db.get_row("resources", body["id"])
    assert stored["metadata"]["owner_id"] == owner.id
    assert stored["metadata"]["room"] == "A"


def test_create_rejects_bad_metadata_type(client, db, auth):
    auth(role="owner")
    # metaFields.resources declares `room` as text; a number is a 422.
    resp = client.post("/resources", json={"name": "Bad", "metadata": {"room": 5}})
    assert resp.status_code == 422


def test_date_metafield_rejects_trailing_junk(client, db, auth, domain_config):
    """A `date` field validated only its first 10 characters, so anything that
    merely STARTED with a date was accepted and stored verbatim."""
    domain_config(metaFields={"resources": [{"key": "seenOn", "label": "Seen", "type": "date"}]})
    auth(role="owner")

    for good in ("2026-08-18", "2026-08-18T14:00:00Z"):
        resp = client.post("/resources", json={"name": "Ok", "metadata": {"seenOn": good}})
        assert resp.status_code == 200, good

    for bad in ("2026-08-18 or whenever", "2026-08-18garbage", "not-a-date"):
        resp = client.post("/resources", json={"name": "Bad", "metadata": {"seenOn": bad}})
        assert resp.status_code == 422, bad


# --- owner-gated patch -----------------------------------------------------


def test_patch_updates_fields(client, db, auth):
    auth(role="owner")
    res = make_resource(db, "Before")
    resp = client.patch(f"/resources/{res['id']}", json={"name": "After"})
    assert resp.status_code == 200
    # patch returns a single serialized Resource, not a raw row list.
    body = resp.json()
    assert isinstance(body, dict)
    assert body["id"] == res["id"]
    assert body["name"] == "After"
    assert db.get_row("resources", res["id"])["name"] == "After"


def test_patch_empty_body_returns_serialized_existing(client, db, auth):
    auth(role="owner")
    res = make_resource(db, "Unchanged", service_id="svc-1", capacity=3)
    resp = client.patch(f"/resources/{res['id']}", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert body["id"] == res["id"]
    assert body["name"] == "Unchanged"
    assert body["serviceId"] == "svc-1"
    assert body["capacity"] == 3


def test_patch_unknown_resource_is_404(client, db, auth):
    auth(role="owner")
    assert client.patch("/resources/nope", json={"name": "x"}).status_code == 404


def test_patch_validates_metadata(client, db, auth):
    auth(role="owner")
    res = make_resource(db, "R")
    resp = client.patch(f"/resources/{res['id']}", json={"metadata": {"room": 9}})
    assert resp.status_code == 422


def test_patch_requires_owner(client, db, auth):
    auth(role="client")
    res = make_resource(db, "R")
    assert client.patch(f"/resources/{res['id']}", json={"name": "x"}).status_code == 403


# --- metadata merge on PATCH -----------------------------------------------


def test_patch_metadata_merges_over_existing(client, db, auth):
    # A partial metadata edit (e.g. {"capacity": 4}) must MERGE over the stored
    # metadata rather than replace it, so owner_id/service_id survive the edit.
    auth(role="owner")
    res = make_resource(
        db, "Van", service_id="svc-7", capacity=2, owner_id=DEFAULT_OWNER_ID
    )
    resp = client.patch(f"/resources/{res['id']}", json={"metadata": {"capacity": 4}})
    assert resp.status_code == 200
    assert resp.json()["capacity"] == 4
    stored = db.get_row("resources", res["id"])["metadata"]
    # merged: the new value is applied...
    assert stored["capacity"] == 4
    # ...and the pre-existing keys are preserved (not dropped by a replace).
    assert stored["owner_id"] == DEFAULT_OWNER_ID
    assert stored["service_id"] == "svc-7"
    assert stored["active"] is True


def test_patch_metadata_merge_can_add_a_new_key(client, db, auth):
    auth(role="owner")
    res = make_resource(db, "Van", service_id="svc-7", owner_id=DEFAULT_OWNER_ID)
    resp = client.patch(
        f"/resources/{res['id']}", json={"metadata": {"room": "B"}}
    )
    assert resp.status_code == 200
    stored = db.get_row("resources", res["id"])["metadata"]
    assert stored["room"] == "B"
    assert stored["service_id"] == "svc-7"
    assert stored["owner_id"] == DEFAULT_OWNER_ID


# --- owner-gated delete (DELETE /resources/{id}) ---------------------------


def test_delete_resource_without_a_token_is_401(client, db):
    res = make_resource(db, "R", owner_id=DEFAULT_OWNER_ID)
    assert client.delete(f"/resources/{res['id']}").status_code == 401


def test_delete_resource_as_client_is_403(client, db, auth):
    auth(role="client")
    res = make_resource(db, "R", owner_id=DEFAULT_OWNER_ID)
    assert client.delete(f"/resources/{res['id']}").status_code == 403


def test_delete_unknown_resource_is_404(client, db, auth):
    auth(role="owner")
    assert client.delete("/resources/nope").status_code == 404


def test_delete_another_owners_resource_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    res = make_resource(db, "Not mine", owner_id=OTHER_OWNER_ID)
    assert client.delete(f"/resources/{res['id']}").status_code == 403
    # the row must survive a rejected delete.
    assert db.get_row("resources", res["id"]) is not None


def test_delete_resource_happy_path_removes_row(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    res = make_resource(db, "Gone soon", owner_id=DEFAULT_OWNER_ID)
    resp = client.delete(f"/resources/{res['id']}")
    assert resp.status_code == 204
    assert resp.content == b""
    assert db.get_row("resources", res["id"]) is None


def test_delete_resource_cascades_to_slots_and_bookings(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID; make_catalog stamps the same owner_id
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    make_booking(db, slots=[cat["slot"]], service=cat["service"], party_size=1)
    resource_id = cat["resource"]["id"]
    slot_id = cat["slot"]["id"]
    assert db.count("slots") == 1
    assert db.count("bookings") == 1
    assert db.count("booking_slots") == 1

    resp = client.delete(f"/resources/{resource_id}")
    assert resp.status_code == 204
    # the DB FK cascade (modelled in the fake) removes slots -> bookings ->
    # booking_slots under the deleted resource.
    assert db.get_row("resources", resource_id) is None
    assert db.get_row("slots", slot_id) is None
    assert db.count("slots") == 0
    assert db.count("bookings") == 0
    assert db.count("booking_slots") == 0


# --- owner-gated analytics -------------------------------------------------


def test_analytics_shape_and_counts(client, db, auth):
    auth(role="owner")
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    # one confirmed booking (party 1) against the slot
    make_booking(db, slots=[cat["slot"]], service=cat["service"], party_size=1)

    data = client.get(f"/resources/{cat['resource']['id']}/analytics").json()
    assert set(data) == {
        "total_slots",
        "total_capacity",
        "booked_count",
        "available_count",
        "occupancy_rate",
        "bookings_by_status",
    }
    assert data["total_slots"] == 1
    assert data["total_capacity"] == 2
    assert data["booked_count"] == 1
    assert data["available_count"] == 1
    assert data["occupancy_rate"] == 0.5
    assert data["bookings_by_status"] == {"confirmed": 1}


def test_analytics_unknown_resource_is_404(client, db, auth):
    auth(role="owner")
    assert client.get("/resources/nope/analytics").status_code == 404


def test_analytics_requires_owner(client, db, auth):
    auth(role="client")
    res = make_resource(db, "R")
    assert client.get(f"/resources/{res['id']}/analytics").status_code == 403


def test_analytics_of_another_owners_resource_is_403(client, db, auth):
    # Tightened: analytics now goes through _owned_resource, so an owner can no
    # longer view a resource stamped with a different owner_id.
    auth(role="owner")  # DEFAULT_OWNER_ID
    res = make_resource(db, "Not mine", owner_id="99999999-9999-9999-9999-999999999999")
    assert client.get(f"/resources/{res['id']}/analytics").status_code == 403


# --- owner-gated resource bookings (GET /resources/{id}/bookings) ----------


def test_resource_bookings_without_a_token_is_401(client, db):
    res = make_resource(db, "R")
    assert client.get(f"/resources/{res['id']}/bookings").status_code == 401


def test_resource_bookings_as_client_is_403(client, db, auth):
    auth(role="client")
    res = make_resource(db, "R")
    assert client.get(f"/resources/{res['id']}/bookings").status_code == 403


def test_resource_bookings_of_another_owners_resource_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    res = make_resource(db, "Not mine", owner_id="99999999-9999-9999-9999-999999999999")
    assert client.get(f"/resources/{res['id']}/bookings").status_code == 403


def test_resource_bookings_unknown_resource_is_404(client, db, auth):
    auth(role="owner")
    assert client.get("/resources/nope/bookings").status_code == 404


def test_resource_bookings_empty_when_no_slots(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    # An owned resource with no slots/bookings returns [].
    res = make_resource(db, "Idle", owner_id="22222222-2222-2222-2222-222222222222")
    resp = client.get(f"/resources/{res['id']}/bookings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resource_bookings_returns_bookings_with_client_email(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID; make_catalog stamps the same owner_id
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    make_booking(
        db,
        slots=[cat["slot"]],
        service=cat["service"],
        party_size=1,
        client_email="rider@example.com",
        reference="BK-OWN001",
    )

    resp = client.get(f"/resources/{cat['resource']['id']}/bookings")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    booking = rows[0]
    # A full serialized Booking shape plus the additive clientEmail field.
    assert {"id", "reference", "userId", "slotIds", "startUtc", "status"} <= set(booking)
    assert "clientEmail" in booking
    assert booking["clientEmail"] == "rider@example.com"
    assert booking["reference"] == "BK-OWN001"
    assert booking["slotIds"] == [cat["slot"]["id"]]


def test_resource_bookings_sorted_by_start_desc(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    cat = make_catalog(db, capacity=2, slot_capacity=2)
    resource_id = cat["resource"]["id"]
    # A second, later slot on the same owned resource.
    later_slot = make_slot(
        db,
        resource_id,
        service_id=cat["service"]["id"],
        hours_ahead=96,
        capacity=2,
    )
    make_booking(
        db, slots=[cat["slot"]], service=cat["service"], reference="BK-EARLY", client_email="a@x.com"
    )
    make_booking(
        db, slots=[later_slot], service=cat["service"], reference="BK-LATE", client_email="b@x.com"
    )

    rows = client.get(f"/resources/{resource_id}/bookings").json()
    # startUtc descending: the later slot's booking comes first.
    assert [r["reference"] for r in rows] == ["BK-LATE", "BK-EARLY"]


# --- metaFields errors carry the ApiError envelope (regression) -------------


def test_bad_metadata_type_carries_the_api_error_envelope(client, db, auth):
    """The 422's `detail` must be the frontend ApiError envelope — the seam
    reads `detail.code`, and a bare detail string rendered as a raw NETWORK
    error instead of the field-level message."""
    auth(role="owner")
    # metaFields.resources declares `room` as text; a number is the violation.
    resp = client.post("/resources", json={"name": "Bad", "metadata": {"room": 5}})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert "Room" in detail["message"]
    assert detail["details"] == {"field": "room", "label": "Room", "expected": "text"}
