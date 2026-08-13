"""/resources — list, create, get by id."""

import pytest

from helpers import make_resource


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


def test_get_resource_unknown_id_current_behaviour(client):
    """Documents today's contract: 200 + null body, not a 404.

    See the xfail below — this is the behaviour the frontend has to cope
    with right now (`api.ts` only throws on !res.ok).
    """
    response = client.get("/resources/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.xfail(
    reason="GET /resources/{id} has no not-found handling: it returns 200/null "
    "with a lenient client and, against real PostgREST, .single() raises "
    "PGRST116 -> unhandled 500. It should return 404.",
)
def test_get_resource_unknown_id_should_404(client):
    response = client.get("/resources/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.xfail(
    reason="POST /resources takes a raw dict with no Pydantic model, so a "
    "payload missing the NOT NULL `name` column is only rejected by the "
    "database (500) instead of 422 at the edge.",
)
def test_create_resource_missing_name_should_422(raw_client):
    response = raw_client.post("/resources", json={"description": "no name"})
    assert response.status_code == 422


def test_create_resource_missing_name_current_behaviour(raw_client):
    """Today the DB constraint is the only guard -> 500, not 422."""
    response = raw_client.post("/resources", json={"description": "no name"})
    assert response.status_code == 500


@pytest.mark.xfail(
    reason="metaFields.resources from domain.config.json is not validated "
    "against the payload yet (TODO in routers/resources.py).",
)
def test_create_resource_validates_configured_meta_fields(client, domain_config):
    domain_config(metaFields={"resources": [{"key": "room", "label": "Room", "type": "text"}]})
    response = client.post("/resources", json={"name": "No meta", "metadata": {}})
    assert response.status_code == 422
