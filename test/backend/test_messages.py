# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""/conversations, 1:1 messaging between a client and a provider's owner.

One thread per (provider, client) pair; messages carry delivered/read receipts
and a soft-delete. Offline, RLS is not simulated (the user client is the same
in-memory store), so participant-scoping enforced purely by RLS, e.g. a
non-participant reading someone else's thread, is covered by the live e2e
suite, not here. What IS asserted offline: the router's own checks (owner-path
403, empty body 400, sender-only delete, unknown-id 404), the serialized
shapes, unread tallies, inbox ordering via the emulated `on_message_insert`
trigger, and the preview repoint after deleting the newest message.
"""

from __future__ import annotations

from helpers import DEFAULT_OWNER_ID, DEFAULT_USER_ID, make_provider

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"

CONVERSATION_KEYS = {
    "id",
    "providerId",
    "otherParty",
    "lastMessagePreview",
    "lastMessageAtUtc",
    "unreadCount",
}

MESSAGE_KEYS = {
    "id",
    "conversationId",
    "senderId",
    "body",
    "replyToId",
    "createdAtUtc",
    "deliveredAtUtc",
    "readAtUtc",
    "deletedAtUtc",
    "mine",
}


def _detail_code(resp) -> str:
    return resp.json()["detail"]["code"]


def _client_thread(client, db, auth, provider_name: str = "Alpha") -> tuple[dict, dict]:
    """A (provider, conversation) pair started by the default client."""
    provider = make_provider(db, provider_name, owner_id=DEFAULT_OWNER_ID)
    auth(role="client")
    conv = client.post("/conversations", json={"providerId": provider["id"]}).json()
    return provider, conv


# --- start a thread ---------------------------------------------------------


def test_requires_a_token(client, db):
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={"providerId": "x"}).status_code == 401


def test_client_starts_a_thread_with_a_provider(client, db, auth):
    provider = make_provider(db, "Alpha", owner_id=DEFAULT_OWNER_ID)
    auth(role="client")
    resp = client.post("/conversations", json={"providerId": provider["id"]})
    assert resp.status_code == 200
    conv = resp.json()
    assert set(conv) == CONVERSATION_KEYS
    assert conv["providerId"] == provider["id"]
    # the client's view of the other party is the business.
    assert conv["otherParty"]["name"] == "Alpha"
    assert conv["unreadCount"] == 0
    row = db.rows("conversations")[0]
    assert row["client_id"] == DEFAULT_USER_ID
    assert row["owner_id"] == DEFAULT_OWNER_ID  # resolved from the provider


def test_start_is_idempotent_on_the_provider_client_pair(client, db, auth):
    provider, conv = _client_thread(client, db, auth)
    again = client.post("/conversations", json={"providerId": provider["id"]}).json()
    assert again["id"] == conv["id"]
    assert db.count("conversations") == 1


def test_owner_starts_a_thread_with_a_customer(client, db, auth):
    db.seed_auth_user(
        DEFAULT_USER_ID, email="ada@example.com",
        user_metadata={"display_name": "Ada Lovelace"},
    )
    provider = make_provider(db, "Alpha", owner_id=DEFAULT_OWNER_ID)
    auth(role="owner")
    resp = client.post(
        "/conversations", json={"providerId": provider["id"], "clientId": DEFAULT_USER_ID}
    )
    assert resp.status_code == 200
    conv = resp.json()
    # the owner's view of the other party is the customer, by display name.
    assert conv["otherParty"]["id"] == DEFAULT_USER_ID
    assert conv["otherParty"]["name"] == "Ada Lovelace"
    row = db.rows("conversations")[0]
    assert row["client_id"] == DEFAULT_USER_ID
    assert row["owner_id"] == DEFAULT_OWNER_ID


def test_owner_thread_with_an_unresolvable_customer_degrades_to_a_safe_name(
    client, db, auth
):
    """No auth.admin record for the customer -> the safe fallback, never a 500
    and never their email."""
    provider = make_provider(db, "Alpha", owner_id=DEFAULT_OWNER_ID)
    auth(role="owner")
    conv = client.post(
        "/conversations", json={"providerId": provider["id"], "clientId": DEFAULT_USER_ID}
    ).json()
    assert conv["otherParty"]["name"] == "Customer"


def test_owner_cannot_message_another_owners_customers(client, db, auth):
    provider = make_provider(db, "Alpha", owner_id=DEFAULT_OWNER_ID)
    auth(role="owner", id=OTHER_OWNER_ID)
    resp = client.post(
        "/conversations", json={"providerId": provider["id"], "clientId": DEFAULT_USER_ID}
    )
    assert resp.status_code == 403
    assert db.count("conversations") == 0  # nothing written


def test_start_with_an_unknown_provider_is_404(client, db, auth):
    auth(role="client")
    resp = client.post("/conversations", json={"providerId": "ghost"})
    assert resp.status_code == 404
    assert _detail_code(resp) == "NOT_FOUND"


# --- inbox + single thread --------------------------------------------------


def test_inbox_lists_threads_with_unread_counts_most_recent_first(client, db, auth):
    prov_a = make_provider(db, "Alpha", owner_id=DEFAULT_OWNER_ID)
    prov_b = make_provider(db, "Beta", owner_id=DEFAULT_OWNER_ID)
    auth(role="client")
    conv_a = client.post("/conversations", json={"providerId": prov_a["id"]}).json()
    conv_b = client.post("/conversations", json={"providerId": prov_b["id"]}).json()

    auth(role="owner")
    client.post(f"/conversations/{conv_a['id']}/messages", json={"body": "hello"})
    client.post(f"/conversations/{conv_a['id']}/messages", json={"body": "still there?"})
    client.post(f"/conversations/{conv_b['id']}/messages", json={"body": "beta latest"})

    auth(role="client")
    inbox = client.get("/conversations").json()
    # Beta got the most recent message (via the emulated insert trigger).
    assert [c["id"] for c in inbox] == [conv_b["id"], conv_a["id"]]
    by_id = {c["id"]: c for c in inbox}
    assert by_id[conv_a["id"]]["unreadCount"] == 2
    assert by_id[conv_b["id"]]["unreadCount"] == 1
    assert by_id[conv_a["id"]]["lastMessagePreview"] == "still there?"
    assert by_id[conv_a["id"]]["otherParty"]["name"] == "Alpha"


def test_get_single_thread_carries_other_party_and_unread(client, db, auth):
    """Direct deep-link view. (A NON-participant 404 is RLS behaviour the
    offline fake does not simulate, covered by the live suite.)"""
    _provider, conv = _client_thread(client, db, auth)
    auth(role="owner")
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "hi"})
    auth(role="client")
    got = client.get(f"/conversations/{conv['id']}").json()
    assert set(got) == CONVERSATION_KEYS
    assert got["id"] == conv["id"]
    assert got["unreadCount"] == 1
    assert got["otherParty"]["name"] == "Alpha"


def test_get_unknown_thread_is_404(client, db, auth):
    auth(role="client")
    resp = client.get("/conversations/ghost-thread")
    assert resp.status_code == 404
    assert _detail_code(resp) == "NOT_FOUND"


# --- send / list messages ---------------------------------------------------


def test_send_message_returns_the_serialized_message(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    resp = client.post(f"/conversations/{conv['id']}/messages", json={"body": "  hi there  "})
    assert resp.status_code == 200
    msg = resp.json()
    assert set(msg) == MESSAGE_KEYS
    assert msg["body"] == "hi there"  # trimmed
    assert msg["mine"] is True
    assert msg["senderId"] == DEFAULT_USER_ID
    assert msg["deliveredAtUtc"] is not None
    assert msg["readAtUtc"] is None
    assert msg["deletedAtUtc"] is None


def test_an_empty_message_is_400(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    resp = client.post(f"/conversations/{conv['id']}/messages", json={"body": "   "})
    assert resp.status_code == 400
    assert _detail_code(resp) == "INVALID_RANGE"
    assert db.count("messages") == 0


def test_messages_list_in_send_order_with_viewer_relative_mine_flags(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "one"})
    auth(role="owner")
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "two"})
    auth(role="client")
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "three"})

    rows = client.get(f"/conversations/{conv['id']}/messages").json()
    assert [m["body"] for m in rows] == ["one", "two", "three"]
    assert [m["mine"] for m in rows] == [True, False, True]

    auth(role="owner")
    rows = client.get(f"/conversations/{conv['id']}/messages").json()
    assert [m["mine"] for m in rows] == [False, True, False]


# --- read receipts ----------------------------------------------------------


def test_mark_read_flips_the_other_partys_messages(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    auth(role="owner")
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "a"})
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "b"})

    auth(role="client")
    resp = client.post(f"/conversations/{conv['id']}/read")
    assert resp.json() == {"conversationId": conv["id"], "readCount": 2}
    assert client.get(f"/conversations/{conv['id']}").json()["unreadCount"] == 0
    # the sender sees the receipts.
    auth(role="owner")
    rows = client.get(f"/conversations/{conv['id']}/messages").json()
    assert all(m["readAtUtc"] is not None for m in rows)
    # marking again is a no-op.
    auth(role="client")
    assert client.post(f"/conversations/{conv['id']}/read").json()["readCount"] == 0


# --- soft delete ------------------------------------------------------------


def test_soft_delete_blanks_the_body_but_keeps_the_row(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    msg = client.post(f"/conversations/{conv['id']}/messages", json={"body": "oops"}).json()
    resp = client.delete(f"/conversations/{conv['id']}/messages/{msg['id']}")
    assert resp.status_code == 200
    out = resp.json()
    assert out["deletedAtUtc"] is not None
    assert out["body"] == ""  # placeholder is the client's job, body is blanked
    assert db.count("messages") == 1  # the row (and its receipts) survive


def test_only_the_sender_can_delete_a_message(client, db, auth):
    _provider, conv = _client_thread(client, db, auth)
    msg = client.post(f"/conversations/{conv['id']}/messages", json={"body": "mine"}).json()
    auth(role="owner")  # the other participant
    resp = client.delete(f"/conversations/{conv['id']}/messages/{msg['id']}")
    assert resp.status_code == 404
    assert db.rows("messages")[0]["deleted_at"] is None


def test_deleting_the_newest_message_repoints_the_inbox_preview(client, db, auth):
    """The insert trigger stamps the preview; deleting the newest message must
    re-point it at the latest SURVIVING message, not leave the retracted text."""
    _provider, conv = _client_thread(client, db, auth)
    client.post(f"/conversations/{conv['id']}/messages", json={"body": "first"})
    second = client.post(f"/conversations/{conv['id']}/messages", json={"body": "second"}).json()
    client.delete(f"/conversations/{conv['id']}/messages/{second['id']}")
    got = client.get(f"/conversations/{conv['id']}").json()
    assert got["lastMessagePreview"] == "first"
