# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""/me — the current-user endpoints. GET assembles the User from the token's
`user_metadata` + the follows table; PATCH updates the editable profile fields.
Both require a token and return the full User shape.
"""

from __future__ import annotations

from helpers import (
    DEFAULT_USER_ID,
    make_booking,
    make_client_review,
    make_provider,
    make_service,
    make_slot,
)


def test_get_me_requires_a_token(client, db):
    assert client.get("/me").status_code == 401


def test_get_me_builds_the_user_from_claims_and_follows(client, db, auth):
    p = make_provider(db, "P")
    db.insert_row("follows", user_id=DEFAULT_USER_ID, provider_id=p["id"])
    auth(role="client", email="ada@example.com", metadata={"display_name": "Ada", "timezone": "Europe/Warsaw"})

    me = client.get("/me").json()
    assert set(me) == {
        "id",
        "displayName",
        "email",
        "avatarUrl",
        "timezone",
        "verified",
        "followedProviderIds",
    }
    assert me["displayName"] == "Ada"
    assert me["timezone"] == "Europe/Warsaw"
    assert me["email"] == "ada@example.com"
    assert me["followedProviderIds"] == [p["id"]]


def test_patch_me_updates_editable_fields(client, db, auth):
    auth(role="client", email="ada@example.com", metadata={"display_name": "Ada"})
    resp = client.patch("/me", json={"displayName": "Adalovelace", "timezone": "UTC"})
    assert resp.status_code == 200
    out = resp.json()
    assert out["displayName"] == "Adalovelace"
    assert out["timezone"] == "UTC"


def test_patch_me_requires_a_token(client, db):
    assert client.patch("/me", json={"displayName": "x"}).status_code == 401


# --- /me/reputation --------------------------------------------------------


def test_reputation_requires_a_token(client, db):
    assert client.get("/me/reputation").status_code == 401


def test_reputation_empty_when_no_client_reviews(client, db, auth):
    auth(role="client")
    body = client.get("/me/reputation").json()
    assert body == {"score": 0, "count": 0, "reviews": []}


def test_reputation_aggregates_reviews_newest_first(client, db, auth):
    auth(role="client", email="ada@example.com")  # DEFAULT_USER_ID
    p = make_provider(db, "Acme Fleet")
    svc = make_service(db, p["id"], "S")
    # Two completed bookings for this user, each rated by the same business.
    s1 = make_slot(db, service_id=svc["id"], hours_ahead=-10)
    s2 = make_slot(db, service_id=svc["id"], hours_ahead=-5)
    b1 = make_booking(db, slots=[s1], service={**svc, "provider_id": p["id"]}, reference="BK-1")
    b2 = make_booking(db, slots=[s2], service={**svc, "provider_id": p["id"]}, reference="BK-2")
    older = make_client_review(db, b1, rating=3, provider_id=p["id"])
    # Force a strictly-later created_at on the second so ordering is deterministic.
    for row in db.tables["client_reviews"]:
        if row["id"] == older["id"]:
            row["created_at"] = "2020-01-01T00:00:00+00:00"
    newer = make_client_review(db, b2, rating=5, provider_id=p["id"])
    for row in db.tables["client_reviews"]:
        if row["id"] == newer["id"]:
            row["created_at"] = "2030-01-01T00:00:00+00:00"

    body = client.get("/me/reputation").json()
    assert body["count"] == 2
    assert body["score"] == 4.0  # mean of 3 and 5
    assert [r["rating"] for r in body["reviews"]] == [5, 3]  # newest first
    assert all(r["author"] == "Acme Fleet" for r in body["reviews"])
    assert set(body["reviews"][0]) == {"author", "rating", "text", "createdAtUtc"}


def test_reputation_scoped_to_the_signed_in_user(client, db, auth):
    auth(role="client")  # DEFAULT_USER_ID
    p = make_provider(db, "Acme")
    svc = make_service(db, p["id"], "S")
    s = make_slot(db, service_id=svc["id"], hours_ahead=-5)
    # A review for a DIFFERENT client must not leak into this user's reputation.
    other = make_booking(
        db, slots=[s], service={**svc, "provider_id": p["id"]}, user_id="00000000-0000-0000-0000-000000000abc"
    )
    make_client_review(db, other, rating=5, provider_id=p["id"])
    body = client.get("/me/reputation").json()
    assert body == {"score": 0, "count": 0, "reviews": []}
