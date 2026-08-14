"""/resources — list, create, get by id, patch, analytics."""

from helpers import make_booking, make_resource, make_slot


def test_list_resources_empty(client):
    response = client.get("/resources")
    assert response.status_code == 200
    assert response.json() == []


def test_list_resources_returns_every_row(client, db):
    make_resource(db, name="Widget 1")
    make_resource(db, name="Widget 2", description="second")

    response = client.get("/resources")
    assert response.status_code == 200
    names = sorted(row["name"] for row in response.json())
    assert names == ["Widget 1", "Widget 2"]


def test_create_resource_persists_and_echoes_the_row(client, db):
    response = client.post(
        "/resources",
        json={"name": "Widget 3", "description": "created via API", "metadata": {"room": "A1"}},
    )
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list) and len(body) == 1  # PostgREST returns a list
    created = body[0]
    assert created["name"] == "Widget 3"
    assert created["description"] == "created via API"
    assert created["metadata"] == {"room": "A1"}
    assert created["id"]

    assert db.count("resources") == 1
    assert client.get("/resources").json()[0]["id"] == created["id"]


def test_create_resource_defaults_metadata_to_an_empty_object(client):
    created = client.post("/resources", json={"name": "Bare"}).json()[0]
    assert created["metadata"] == {}
    assert created["description"] is None


def test_create_resource_keeps_arbitrary_metadata_for_the_pivot(client):
    """New domain fields go in metadata jsonb — never a new column."""
    metadata = {"speciality": "cardiology", "tags": ["a", "b"], "rooms": 3}
    created = client.post("/resources", json={"name": "Doctor 1", "metadata": metadata}).json()[0]
    assert created["metadata"] == metadata

    fetched = client.get(f"/resources/{created['id']}").json()
    assert fetched["metadata"] == metadata


def test_get_resource_by_id(client, db):
    resource = make_resource(db, name="Widget 7")
    response = client.get(f"/resources/{resource['id']}")
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, dict)  # .single() -> one object, not a list
    assert body["id"] == resource["id"]
    assert body["name"] == "Widget 7"


def test_get_resource_unknown_id_should_404(client):
    response = client.get("/resources/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_resource_unknown_id_404_against_real_postgrest(strict_client):
    """Real PostgREST raises PGRST116 from .single() on zero rows; maybe_row
    swallows it so the 404 branch is reachable in production too."""
    response = strict_client.get("/resources/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_create_resource_missing_name_should_422(raw_client):
    response = raw_client.post("/resources", json={"description": "no name"})
    assert response.status_code == 422


def test_create_resource_validates_configured_meta_fields(client, domain_config):
    """A declared metaField present with the wrong type is a 422 (type map:
    number -> int|float)."""
    domain_config(metaFields={"resources": [{"key": "rooms", "label": "Rooms", "type": "number"}]})
    response = client.post("/resources", json={"name": "Bad meta", "metadata": {"rooms": "three"}})
    assert response.status_code == 422


def test_create_resource_accepts_correctly_typed_meta_field(client, domain_config):
    domain_config(metaFields={"resources": [{"key": "rooms", "label": "Rooms", "type": "number"}]})
    response = client.post("/resources", json={"name": "Good meta", "metadata": {"rooms": 3}})
    assert response.status_code == 200
    assert response.json()[0]["metadata"]["rooms"] == 3


def test_create_resource_optional_meta_field_may_be_omitted(client, domain_config):
    """Declared fields are optional by default: absence is fine."""
    domain_config(metaFields={"resources": [{"key": "rooms", "label": "Rooms", "type": "number"}]})
    response = client.post("/resources", json={"name": "No meta", "metadata": {}})
    assert response.status_code == 200


def test_create_resource_required_meta_field_missing_is_422(client, domain_config):
    domain_config(
        metaFields={
            "resources": [{"key": "room", "label": "Room", "type": "text", "required": True}]
        }
    )
    response = client.post("/resources", json={"name": "No room", "metadata": {}})
    assert response.status_code == 422


def test_create_resource_undeclared_meta_keys_pass_through(client, domain_config):
    """The metadata jsonb column is the extension point — keys the config
    never declares are stored untouched."""
    domain_config(metaFields={"resources": [{"key": "room", "label": "Room", "type": "text"}]})
    metadata = {"room": "A1", "speciality": "cardiology", "tags": ["x", "y"]}
    created = client.post("/resources", json={"name": "Doctor", "metadata": metadata}).json()[0]
    assert created["metadata"] == metadata


# --------------------------------------------------------------------
# PATCH /resources/{id}
# --------------------------------------------------------------------


def test_patch_resource_partial_update(client, db):
    resource = make_resource(db, name="Widget 1", description="old")
    response = client.patch(f"/resources/{resource['id']}", json={"description": "new"})
    assert response.status_code == 200
    updated = response.json()[0]
    assert updated["name"] == "Widget 1"  # untouched
    assert updated["description"] == "new"
    assert db.get_row("resources", resource["id"])["description"] == "new"


def test_patch_resource_unknown_id_returns_404(client):
    response = client.patch(
        "/resources/00000000-0000-0000-0000-000000000000", json={"name": "x"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"


def test_patch_resource_validates_metadata(client, db, domain_config):
    domain_config(metaFields={"resources": [{"key": "rooms", "label": "Rooms", "type": "number"}]})
    resource = make_resource(db, name="Widget 1")
    response = client.patch(
        f"/resources/{resource['id']}", json={"metadata": {"rooms": "three"}}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------
# GET /resources/{id}/analytics
# --------------------------------------------------------------------


def test_resource_analytics_shape_and_counts(client, db):
    resource = make_resource(db, name="Widget 1")
    slot_a = make_slot(db, resource["id"], capacity=2)
    slot_b = make_slot(db, resource["id"], capacity=3)
    make_booking(db, slot_a["id"], client_email="a@example.com")
    make_booking(db, slot_a["id"], client_email="b@example.com")
    make_booking(db, slot_b["id"], client_email="c@example.com", status="cancelled")

    body = client.get(f"/resources/{resource['id']}/analytics").json()
    assert set(body) == {
        "total_slots",
        "total_capacity",
        "booked_count",
        "available_count",
        "occupancy_rate",
        "bookings_by_status",
    }
    assert body["total_slots"] == 2
    assert body["total_capacity"] == 5
    assert body["booked_count"] == 2  # only confirmed hold capacity
    assert body["available_count"] == 3
    assert body["occupancy_rate"] == 2 / 5
    # bookings_by_status is aggregated from the rows, not a fixed list
    assert body["bookings_by_status"] == {"confirmed": 2, "cancelled": 1}


def test_resource_analytics_empty_resource(client, db):
    resource = make_resource(db, name="Empty")
    body = client.get(f"/resources/{resource['id']}/analytics").json()
    assert body["total_slots"] == 0
    assert body["total_capacity"] == 0
    assert body["occupancy_rate"] == 0.0
    assert body["bookings_by_status"] == {}


def test_resource_analytics_unknown_id_returns_404(client):
    response = client.get(
        "/resources/00000000-0000-0000-0000-000000000000/analytics"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"
