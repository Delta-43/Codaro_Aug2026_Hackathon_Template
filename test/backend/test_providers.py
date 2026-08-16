"""/providers — public discovery (search, by-id, by-code) + follow/unfollow.

Discovery is public (personalised when a token is present); follow/unfollow
require a user. Providers carry derived `serviceIds` and pooled `rating`.
"""

from __future__ import annotations

from helpers import make_provider, make_service

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
