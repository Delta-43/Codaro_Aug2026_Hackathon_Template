# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""/services — public reads. A service carries per-service rule columns and a
derived `resourceIds` link array (its active resources)."""

from __future__ import annotations

from helpers import (
    DEFAULT_OWNER_ID,
    make_booking,
    make_provider,
    make_resource,
    make_service,
    make_slot,
)

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"

SERVICE_KEYS = {
    "id",
    "providerId",
    "name",
    "description",
    "imageUrl",
    "bookingModel",
    "slotDurationMinutes",
    "minSlotsPerBooking",
    "maxSlotsPerBooking",
    "priceMinorUnits",
    "currency",
    "cancellationCutoffHours",
    "autoApprove",
    "capabilities",
    "pricingModel",
    "rateUnit",
    "paymentFlow",
    "billingCycle",
    "prerequisites",
    "recurrence",
    "waitlist",
    "resourceIds",
    # The v2 offer-shape blocks. Every one was declared in the config, resolved
    # per service, and served to nobody — so the client could not render (let
    # alone collect) a party band, an add-on, a subject, a course or a payment
    # schedule.
    "unitKind",
    "party",
    "subject",
    "options",
    "sequence",
    "paymentSchedule",
    "locationModes",
    "locationDefault",
}


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


# --- owner-gated create (POST /services) -----------------------------------


def test_create_service_without_a_token_is_401(client, db):
    p = make_provider(db, "P")
    resp = client.post("/services", json={"providerId": p["id"], "name": "S"})
    assert resp.status_code == 401


def test_create_service_as_client_is_403(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P")
    resp = client.post("/services", json={"providerId": p["id"], "name": "S"})
    assert resp.status_code == 403


def test_create_service_as_owner_returns_serialized_service(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    resp = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "Compact",
            "description": "A small car",
            "bookingModel": "one_to_one",
            "slotDurationMinutes": 60,
            "minSlotsPerBooking": 1,
            "maxSlotsPerBooking": 4,
            "priceMinorUnits": 4500,
            "currency": "PLN",
            "cancellationCutoffHours": 12,
            "imageUrl": "http://img/compact.png",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert set(body) == SERVICE_KEYS
    assert body["providerId"] == p["id"]
    assert body["name"] == "Compact"
    assert body["slotDurationMinutes"] == 60
    assert body["maxSlotsPerBooking"] == 4
    assert body["priceMinorUnits"] == 4500
    assert body["currency"] == "PLN"
    assert body["cancellationCutoffHours"] == 12
    assert body["imageUrl"] == "http://img/compact.png"
    assert body["autoApprove"] is True  # default when omitted
    assert body["resourceIds"] == []  # no resources linked yet


def test_create_service_with_auto_approve_false_persists_to_metadata(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    resp = client.post(
        "/services",
        json={"providerId": p["id"], "name": "By request", "autoApprove": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["autoApprove"] is False
    # auto_approve is NOT a column — it rides in services.metadata like image_url.
    stored = db.get_row("services", body["id"])
    assert stored["metadata"]["auto_approve"] is False
    assert "auto_approve" not in stored  # never a column


def test_create_service_defaults_persist_as_columns(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    body = client.post("/services", json={"providerId": p["id"], "name": "Bare"}).json()
    stored = db.get_row("services", body["id"])
    # the per-service rule defaults land as real columns (not metadata).
    assert stored["booking_model"] == "one_to_one"
    assert stored["slot_duration_minutes"] == 30
    assert stored["price_minor_units"] == 0
    assert stored["currency"] == "EUR"
    assert stored["cancellation_cutoff_hours"] == 24


# --- owner-gated update (PATCH /services/{id}) ------------------------------


def test_patch_service_without_a_token_is_401(client, db):
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S")
    assert client.patch(f"/services/{svc['id']}", json={"name": "x"}).status_code == 401


def test_patch_service_as_client_is_403(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S")
    assert client.patch(f"/services/{svc['id']}", json={"name": "x"}).status_code == 403


def test_patch_service_unknown_is_404(client, db, auth):
    auth(role="owner")
    assert client.patch("/services/nope", json={"name": "x"}).status_code == 404


def test_patch_service_updates_columns(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "Before", price_minor_units=1000, currency="EUR")
    active = make_resource(db, "R", service_id=svc["id"], active=True)
    resp = client.patch(
        f"/services/{svc['id']}",
        json={"name": "After", "priceMinorUnits": 9900, "currency": "PLN"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == SERVICE_KEYS
    assert body["name"] == "After"
    assert body["priceMinorUnits"] == 9900
    assert body["currency"] == "PLN"
    # PATCH runs through build_service, so resourceIds are derived.
    assert body["resourceIds"] == [active["id"]]
    stored = db.get_row("services", svc["id"])
    assert stored["price_minor_units"] == 9900


def test_patch_service_image_url_writes_to_metadata(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S")
    resp = client.patch(
        f"/services/{svc['id']}", json={"imageUrl": "http://img/new.png"}
    )
    assert resp.status_code == 200
    assert resp.json()["imageUrl"] == "http://img/new.png"
    assert db.get_row("services", svc["id"])["metadata"]["image_url"] == "http://img/new.png"


def test_patch_service_toggles_auto_approve_and_merges_metadata(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    # Seed a service that already has an image_url in metadata + default auto-approve.
    svc = make_service(db, p["id"], "S", metadata={"image_url": "http://img/keep.png"})
    resp = client.patch(f"/services/{svc['id']}", json={"autoApprove": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["autoApprove"] is False
    assert body["imageUrl"] == "http://img/keep.png"  # not dropped by the merge
    stored = db.get_row("services", svc["id"])
    assert stored["metadata"]["auto_approve"] is False
    assert stored["metadata"]["image_url"] == "http://img/keep.png"

    # Toggling back to True merges again (still keeps image_url).
    back = client.patch(f"/services/{svc['id']}", json={"autoApprove": True})
    assert back.json()["autoApprove"] is True
    assert db.get_row("services", svc["id"])["metadata"]["image_url"] == "http://img/keep.png"


def test_patch_service_empty_body_returns_serialized_existing(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "Steady", price_minor_units=500)
    resp = client.patch(f"/services/{svc['id']}", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == svc["id"]
    assert body["name"] == "Steady"
    assert body["priceMinorUnits"] == 500


# --- owner-gated delete (DELETE /services/{id}) ----------------------------


def test_delete_service_without_a_token_is_401(client, db):
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    assert client.delete(f"/services/{svc['id']}").status_code == 401


def test_delete_service_as_client_is_403(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    assert client.delete(f"/services/{svc['id']}").status_code == 403


def test_delete_service_unknown_is_404(client, db, auth):
    auth(role="owner")
    assert client.delete("/services/nope").status_code == 404


def test_delete_service_of_another_owners_provider_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "Not mine", owner_id=OTHER_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    assert client.delete(f"/services/{svc['id']}").status_code == 403
    assert db.get_row("services", svc["id"]) is not None


def test_delete_service_happy_path_removes_row(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    resp = client.delete(f"/services/{svc['id']}")
    assert resp.status_code == 204
    assert resp.content == b""
    assert db.get_row("services", svc["id"]) is None
    # the parent provider is untouched.
    assert db.get_row("providers", p["id"]) is not None


def test_delete_service_removes_its_metadata_linked_resources(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    res = make_resource(
        db, "Unit", service_id=svc["id"], capacity=2, owner_id=DEFAULT_OWNER_ID
    )
    slot = make_slot(db, res["id"], service_id=svc["id"], capacity=2)
    make_booking(db, slots=[slot], service=svc, party_size=1)
    # a resource under a *different* service must survive.
    other = make_resource(
        db, "Other unit", service_id="svc-other", owner_id=DEFAULT_OWNER_ID
    )

    resp = client.delete(f"/services/{svc['id']}")
    assert resp.status_code == 204
    # the service's metadata-linked resource (and its slot/booking cascade) go...
    assert db.get_row("services", svc["id"]) is None
    assert db.get_row("resources", res["id"]) is None
    assert db.get_row("slots", slot["id"]) is None
    assert db.count("bookings") == 0
    assert db.count("booking_slots") == 0
    # ...but an unrelated resource stays.
    assert db.get_row("resources", other["id"]) is not None


# --- prerequisites are only served when the capability is on (regression) ---


def test_prerequisites_only_serialized_when_the_capability_is_on(
    client, db, auth, domain_config
):
    """Enforcement (create/approve) ANDs `capabilities.prerequisites`, so
    serving the declared list on a capability-off deployment advertised a step
    the API never enforced — it must serialize as []."""
    prereqs = [{
        "key": "licence", "kind": "licence", "label": "Licence",
        "required": True, "blocksConfirmation": True,
    }]
    p = make_provider(db, "P")
    svc = make_service(db, p["id"], "S")

    domain_config(prerequisites=prereqs, capabilities={"prerequisites": False})
    assert client.get(f"/services/{svc['id']}").json()["prerequisites"] == []

    domain_config(prerequisites=prereqs, capabilities={"prerequisites": True})
    served = client.get(f"/services/{svc['id']}").json()["prerequisites"]
    assert [x["key"] for x in served] == ["licence"]
    assert served[0]["blocksConfirmation"] is True
    assert served[0]["label"] == "Licence"
