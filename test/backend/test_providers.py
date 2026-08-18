"""/providers — public discovery (search, by-id, by-code) + follow/unfollow.

Discovery is public (personalised when a token is present); follow/unfollow
require a user. Providers carry derived `serviceIds` and pooled `rating`.
"""

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

PROVIDER_KEYS = {
    "id",
    "name",
    "avatarUrl",
    "coverUrl",
    "tagline",
    "bio",
    "categoryId",
    "location",
    "rating",
    "reviewCount",
    "priceFromMinorUnits",
    "currency",
    "links",
    "publicCode",
    "serviceIds",
}


def test_search_lists_serialized_providers(client, db):
    p = make_provider(db, "Vistula Auto", category_id="economy", public_code="VISTULA-4471")
    make_service(db, p["id"], "Compact")
    rows = client.get("/providers").json()
    assert len(rows) == 1
    assert rows[0]["publicCode"] == "VISTULA-4471"
    assert rows[0]["serviceIds"]  # the service is linked


def test_search_exposes_price_from_cheapest_service(client, db):
    p = make_provider(db, "Vistula Auto", category_id="economy")
    make_service(db, p["id"], "Premium", price_minor_units=9000, currency="PLN")
    make_service(db, p["id"], "Compact", price_minor_units=4500, currency="USD")
    rows = client.get("/providers").json()
    assert len(rows) == 1
    # cheapest service wins, carrying its own currency.
    assert rows[0]["priceFromMinorUnits"] == 4500
    assert rows[0]["currency"] == "USD"


def test_search_price_from_is_null_without_services(client, db):
    make_provider(db, "Empty", category_id="economy")
    rows = client.get("/providers").json()
    assert rows[0]["priceFromMinorUnits"] is None
    assert rows[0]["currency"] == ""


def test_search_filters_by_category(client, db):
    make_provider(db, "A", category_id="economy")
    make_provider(db, "B", category_id="suv")
    rows = client.get("/providers", params={"category_id": "suv"}).json()
    assert [r["name"] for r in rows] == ["B"]


def test_search_filters_by_text_over_name(client, db):
    make_provider(db, "Vistula Auto", category_id="economy")
    make_provider(db, "Nord Fleet", category_id="suv")
    rows = client.get("/providers", params={"text": "vistula"}).json()
    assert [r["name"] for r in rows] == ["Vistula Auto"]


def test_search_orders_by_rating_desc(client, db):
    make_provider(db, "Low", metadata={"rating": 3.0, "review_count": 10})
    make_provider(db, "High", metadata={"rating": 4.9, "review_count": 10})
    rows = client.get("/providers").json()
    assert [r["name"] for r in rows] == ["High", "Low"]


def test_get_provider_by_id(client, db):
    p = make_provider(db, "Solo")
    got = client.get(f"/providers/{p['id']}").json()
    assert got["id"] == p["id"]


def test_get_unknown_provider_is_404(client, db):
    assert client.get("/providers/nope").status_code == 404


def test_get_provider_by_code_is_case_insensitive(client, db):
    make_provider(db, "Vistula", public_code="VISTULA-4471")
    got = client.get("/providers/by-code/vistula-4471").json()
    assert got["publicCode"] == "VISTULA-4471"


def test_get_provider_by_unknown_code_is_404(client, db):
    assert client.get("/providers/by-code/ZZZ-0000").status_code == 404


# --- follow / unfollow -----------------------------------------------------


def test_follow_requires_a_token(client, db):
    p = make_provider(db, "P")
    assert client.post(f"/providers/{p['id']}/follow").status_code == 401


def test_follow_then_unfollow(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P")
    followed = client.post(f"/providers/{p['id']}/follow").json()
    assert p["id"] in followed["followedProviderIds"]

    unfollowed = client.post(f"/providers/{p['id']}/unfollow").json()
    assert p["id"] not in unfollowed["followedProviderIds"]


def test_follow_is_idempotent(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P")
    client.post(f"/providers/{p['id']}/follow")
    second = client.post(f"/providers/{p['id']}/follow").json()
    assert second["followedProviderIds"].count(p["id"]) == 1


def test_follow_reports_403_when_rls_drops_the_write(client, db, auth, monkeypatch):
    """RLS refuses a write in two shapes: it raises, or it returns no rows. Only
    the raising one was handled, so a silently-dropped insert still returned 200
    and the UI showed "Following" for a row that was never written. Every other
    write in the codebase guards the empty-result form with `enforce_rls_write`."""
    auth(role="client")
    p = make_provider(db, "P")

    real_table = db.table

    def _empty_insert(name):
        builder = real_table(name)
        if name == "follows":
            real_insert = builder.insert

            def _insert(*args, **kwargs):
                q = real_insert(*args, **kwargs)
                real_execute = q.execute

                def _execute():
                    resp = real_execute()
                    resp.data = []  # RLS filtered the returned representation
                    return resp

                q.execute = _execute
                return q

            builder.insert = _insert
        return builder

    monkeypatch.setattr(db, "table", _empty_insert)
    resp = client.post(f"/providers/{p['id']}/follow")
    assert resp.status_code == 403


def test_follow_unknown_provider_is_404(client, db, auth):
    auth(role="client")
    assert client.post("/providers/nope/follow").status_code == 404


def test_followed_provider_pins_to_top_of_search(client, db, auth):
    auth(role="client")
    make_provider(db, "Top-rated", metadata={"rating": 5.0, "review_count": 5})
    followed_p = make_provider(db, "Followed", metadata={"rating": 1.0, "review_count": 5})
    client.post(f"/providers/{followed_p['id']}/follow")
    rows = client.get("/providers").json()
    assert rows[0]["name"] == "Followed"  # pinned despite lower rating


# --- owner-gated create (POST /providers) ----------------------------------


def test_create_provider_without_a_token_is_401(client, db):
    assert client.post("/providers", json={"name": "New"}).status_code == 401


def test_create_provider_as_client_is_403(client, db, auth):
    auth(role="client")
    assert client.post("/providers", json={"name": "New"}).status_code == 403


def test_create_provider_as_owner_returns_serialized_provider(client, db, auth):
    auth(role="owner")
    resp = client.post(
        "/providers",
        json={
            "name": "Vistula Auto",
            "publicCode": "VISTULA-4471",
            "categoryId": "economy",
            "tagline": "Rent smart",
            "bio": "City fleet",
            "location": {"city": "Warsaw", "country": "PL"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert set(body) == PROVIDER_KEYS
    assert body["name"] == "Vistula Auto"
    assert body["publicCode"] == "VISTULA-4471"
    assert body["categoryId"] == "economy"
    assert body["tagline"] == "Rent smart"
    assert body["location"]["city"] == "Warsaw"
    assert body["serviceIds"] == []  # brand new provider


def test_create_provider_stamps_owner_id_from_token(client, db, auth):
    owner = auth(role="owner")
    body = client.post("/providers", json={"name": "Owned"}).json()
    # owner_id is a real column (not exposed by serialize_provider); assert it
    # via the stored row.
    stored = db.get_row("providers", body["id"])
    assert stored["owner_id"] == owner.id


# --- owner-gated update (PATCH /providers/{id}) -----------------------------


def test_patch_provider_without_a_token_is_401(client, db):
    p = make_provider(db, "P")
    assert client.patch(f"/providers/{p['id']}", json={"name": "x"}).status_code == 401


def test_patch_provider_as_client_is_403(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P")
    assert client.patch(f"/providers/{p['id']}", json={"name": "x"}).status_code == 403


def test_patch_provider_unknown_is_404(client, db, auth):
    auth(role="owner")
    assert client.patch("/providers/nope", json={"name": "x"}).status_code == 404


def test_patch_provider_updates_columns_and_metadata(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "Before", category_id="economy")
    resp = client.patch(
        f"/providers/{p['id']}",
        json={"name": "After", "categoryId": "suv", "tagline": "Now bigger"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PROVIDER_KEYS
    assert body["name"] == "After"
    assert body["categoryId"] == "suv"
    assert body["tagline"] == "Now bigger"
    stored = db.get_row("providers", p["id"])
    assert stored["name"] == "After"
    assert stored["metadata"]["tagline"] == "Now bigger"


def test_patch_provider_empty_body_returns_serialized_existing(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "Steady", public_code="CODE-1")
    resp = client.patch(f"/providers/{p['id']}", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == p["id"]
    assert body["name"] == "Steady"
    assert body["publicCode"] == "CODE-1"


# --- owner's own providers (GET /providers/mine) ---------------------------


def test_my_providers_without_a_token_is_401(client, db):
    assert client.get("/providers/mine").status_code == 401


def test_my_providers_as_client_is_403(client, db, auth):
    auth(role="client")
    assert client.get("/providers/mine").status_code == 403


def test_my_providers_returns_only_owner_owned(client, db, auth):
    owner = auth(role="owner")
    mine = make_provider(db, "Mine", owner_id=owner.id)
    make_provider(db, "Someone else", owner_id="99999999-9999-9999-9999-999999999999")
    make_provider(db, "Unowned")  # owner_id None
    rows = client.get("/providers/mine").json()
    assert [r["name"] for r in rows] == ["Mine"]
    assert rows[0]["id"] == mine["id"]
    assert set(rows[0]) == PROVIDER_KEYS


def test_my_providers_reflects_a_just_created_one(client, db, auth):
    auth(role="owner")
    created = client.post("/providers", json={"name": "Fresh"}).json()
    rows = client.get("/providers/mine").json()
    assert [r["id"] for r in rows] == [created["id"]]


# --- owner-gated delete (DELETE /providers/{id}) ---------------------------


def test_delete_provider_without_a_token_is_401(client, db):
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    assert client.delete(f"/providers/{p['id']}").status_code == 401


def test_delete_provider_as_client_is_403(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    assert client.delete(f"/providers/{p['id']}").status_code == 403


def test_delete_provider_unknown_is_404(client, db, auth):
    auth(role="owner")
    assert client.delete("/providers/nope").status_code == 404


def test_delete_another_owners_provider_is_403(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "Not mine", owner_id=OTHER_OWNER_ID)
    assert client.delete(f"/providers/{p['id']}").status_code == 403
    assert db.get_row("providers", p["id"]) is not None


def test_delete_provider_happy_path_removes_row(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "Gone soon", owner_id=DEFAULT_OWNER_ID)
    resp = client.delete(f"/providers/{p['id']}")
    assert resp.status_code == 204
    assert resp.content == b""
    assert db.get_row("providers", p["id"]) is None


def test_delete_provider_cascades_services_follows_and_reviews(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    p = make_provider(db, "Full house", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    db.insert_row("follows", user_id=DEFAULT_OWNER_ID, provider_id=p["id"])

    resp = client.delete(f"/providers/{p['id']}")
    assert resp.status_code == 204
    assert db.get_row("providers", p["id"]) is None
    # FK cascade removes services + follows under the provider.
    assert db.get_row("services", svc["id"]) is None
    assert db.count("follows") == 0


def test_delete_provider_removes_metadata_linked_resources_and_their_slots(
    client, db, auth
):
    auth(role="owner")  # DEFAULT_OWNER_ID; make_catalog stamps the same owner_id
    cat = make_catalog_owned(db)
    make_booking(db, slots=[cat["slot"]], service=cat["service"], party_size=1)
    provider_id = cat["provider"]["id"]
    resource_id = cat["resource"]["id"]
    slot_id = cat["slot"]["id"]
    assert db.count("resources") == 1
    assert db.count("slots") == 1
    assert db.count("bookings") == 1

    resp = client.delete(f"/providers/{provider_id}")
    assert resp.status_code == 204
    # provider gone; its service gone by FK cascade...
    assert db.get_row("providers", provider_id) is None
    assert db.get_row("services", cat["service"]["id"]) is None
    # ...and its metadata-linked resource (no FK) removed by the router helper,
    # taking its slot -> booking -> booking_slots cascade with it.
    assert db.get_row("resources", resource_id) is None
    assert db.get_row("slots", slot_id) is None
    assert db.count("resources") == 0
    assert db.count("slots") == 0
    assert db.count("bookings") == 0
    assert db.count("booking_slots") == 0


def test_delete_provider_leaves_another_providers_resources(client, db, auth):
    auth(role="owner")  # DEFAULT_OWNER_ID
    mine = make_catalog_owned(db)
    # a second provider (also owned) with its own service + resource.
    other_p = make_provider(db, "Keep me", owner_id=DEFAULT_OWNER_ID)
    other_svc = make_service(db, other_p["id"], "Keep svc")
    other_res = make_resource(
        db, "Keep unit", service_id=other_svc["id"], owner_id=DEFAULT_OWNER_ID
    )

    resp = client.delete(f"/providers/{mine['provider']['id']}")
    assert resp.status_code == 204
    # only the deleted provider's resource is gone; the other provider's stays.
    assert db.get_row("resources", mine["resource"]["id"]) is None
    assert db.get_row("resources", other_res["id"]) is not None
    assert db.get_row("services", other_svc["id"]) is not None
    assert db.get_row("providers", other_p["id"]) is not None


# --- public provider reviews ------------------------------------------------


def test_provider_reviews_newest_first_with_public_display_name(client, db):
    p = make_provider(db, "Acme")
    svc = make_service(db, p["id"], "S")
    s1 = make_slot(db, service_id=svc["id"], hours_ahead=-10)
    s2 = make_slot(db, service_id=svc["id"], hours_ahead=-5)
    b1 = make_booking(
        db, slots=[s1], service={**svc, "provider_id": p["id"]}, client_email="ada@example.com", reference="BK-1"
    )
    b2 = make_booking(
        db, slots=[s2], service={**svc, "provider_id": p["id"]}, client_email="grace@example.com", reference="BK-2"
    )
    db.insert_row(
        "reviews", booking_id=b1["id"], provider_id=p["id"], rating=3, text="ok",
        created_at="2020-01-01T00:00:00+00:00",
    )
    db.insert_row(
        "reviews", booking_id=b2["id"], provider_id=p["id"], rating=5, text="great",
        created_at="2030-01-01T00:00:00+00:00",
    )

    rows = client.get(f"/providers/{p['id']}/reviews").json()
    assert [r["rating"] for r in rows] == [5, 3]  # newest first
    # author is the reviewer's self-chosen public display name (from Supabase
    # user_metadata), never the email local-part. Offline the FakeSupabase has
    # no auth.admin, so the name can't be resolved and it falls back to "Guest".
    assert [r["author"] for r in rows] == ["Guest", "Guest"]
    assert set(rows[0]) == {"rating", "text", "createdAtUtc", "author"}


def test_provider_reviews_empty_for_provider_without_reviews(client, db):
    p = make_provider(db, "Quiet")
    assert client.get(f"/providers/{p['id']}/reviews").json() == []


def make_catalog_owned(db):
    """A provider + service + resource + slot, all stamped with the owner used by
    `auth(role="owner")` so the ownership check passes and the metadata link is
    exercised end to end."""
    p = make_provider(db, "Owned", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S")
    res = make_resource(
        db, "Unit", service_id=svc["id"], capacity=2, owner_id=DEFAULT_OWNER_ID
    )
    slot = make_slot(db, res["id"], service_id=svc["id"], capacity=2)
    return {"provider": p, "service": svc, "resource": res, "slot": slot}
