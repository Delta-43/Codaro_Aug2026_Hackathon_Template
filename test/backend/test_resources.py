"""/resources — public reads + owner-gated writes, through the real endpoints.

Reads are open; create/patch/analytics require the owner role (`require_owner`).
The `auth` fixture stubs token verification and lets a test run as anon / client
/ owner so the gating is genuinely exercised.
"""

from __future__ import annotations

from helpers import make_booking, make_catalog, make_resource, make_service, make_slot


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
