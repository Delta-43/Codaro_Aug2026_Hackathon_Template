"""/services — public reads. A service carries per-service rule columns and a
derived `resourceIds` link array (its active resources)."""

from __future__ import annotations

from helpers import make_provider, make_resource, make_service


def test_list_services(client, db):
    p = make_provider(db, "P")
    make_service(db, p["id"], "Compact", price_minor_units=4500, currency="PLN")
    rows = client.get("/services").json()
    assert len(rows) == 1
    svc = rows[0]
    assert svc["providerId"] == p["id"]
    assert svc["priceMinorUnits"] == 4500
    assert svc["currency"] == "PLN"


def test_list_services_filtered_by_provider(client, db):
    p1 = make_provider(db, "P1")
    p2 = make_provider(db, "P2")
    make_service(db, p1["id"], "S1")
    make_service(db, p2["id"], "S2")
    rows = client.get("/services", params={"provider_id": p1["id"]}).json()
    assert [s["name"] for s in rows] == ["S1"]


def test_service_resource_ids_are_derived_from_active_resources(client, db):
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S")
    active = make_resource(db, "Active", service_id=svc["id"], active=True)
    make_resource(db, "Inactive", service_id=svc["id"], active=False)
    got = client.get(f"/services/{svc['id']}").json()
    assert got["resourceIds"] == [active["id"]]


def test_get_unknown_service_is_404(client, db):
    assert client.get("/services/nope").status_code == 404
