"""/me — the current-user endpoints. GET assembles the User from the token's
`user_metadata` + the follows table; PATCH updates the editable profile fields.
Both require a token and return the full User shape.
"""

from __future__ import annotations

from helpers import DEFAULT_USER_ID, make_provider


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
