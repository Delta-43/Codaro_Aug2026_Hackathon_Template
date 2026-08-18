"""Messaging — 1:1 conversations between a client and a provider's owner.

A conversation is one thread per (provider, client) pair; messages carry
delivered/read receipts and a soft-delete. Every user-owned read/write goes
through the RLS-scoped user client (`get_user_client`), so the database enforces
that only the two participants can see or touch a thread. The service-key client
is used **only** for the cross-user display-name resolution RLS can't do (the
provider's name/avatar, and the other participant's `user_metadata`).

Identity always comes from the verified token (`user.id` / `user.email`), never
the request body — mirroring `create_booking`. Live delivery is Supabase
Realtime (see the frontend hook), gated by the same RLS; this router owns the
durable send/read/delete/list path.
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthUser, enforce_rls_write, require_user
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import INVALID_RANGE, NOT_FOUND, api_error
from app.models import ConversationCreateReq, MessageCreateReq
from app.serialize import iso_utc, serialize_conversation, serialize_message
from app.clock import now_utc

router = APIRouter(prefix="/conversations", tags=["messages"])


# --- cross-user display resolution (service key — spans RLS boundaries) -----


def _provider_map(db, provider_ids) -> dict[str, dict]:
    """Batch id → {id, name, avatar_url} for providers, so the inbox resolves the
    business a client is talking to in one query."""
    ids = {i for i in provider_ids if i}
    if not ids:
        return {}
    rows = db.table("providers").select("id,name,metadata").in_("id", list(ids)).execute().data or []
    out: dict[str, dict] = {}
    for r in rows:
        md = r.get("metadata") or {}
        out[r["id"]] = {"id": r["id"], "name": r.get("name") or "", "avatar_url": md.get("avatar_url")}
    return out


def _user_display(db, uid: str) -> dict:
    """{id, name, avatar_url} for an auth user, from user_metadata via the admin
    API. Degrades gracefully (the offline fake / a missing user → a safe
    fallback) — the same best-effort stance as owner.py's client screening."""
    try:
        resp = db.auth.admin.get_user_by_id(uid)
        u = getattr(resp, "user", None) or resp
        md = getattr(u, "user_metadata", None) or {}
        email = getattr(u, "email", None) or ""
        name = (
            md.get("display_name")
            or md.get("displayName")
            or (email.split("@")[0] if email else "")
            or "Customer"
        )
        return {"id": uid, "name": name, "avatar_url": md.get("avatar_url") or md.get("avatarUrl")}
    except Exception:
        return {"id": uid, "name": "Customer", "avatar_url": None}


def _other_party(db, conv: dict, me_id: str, prov_map: dict, user_cache: dict) -> dict:
    """Who the current user is talking to in this thread: the provider when I'm
    the client, the customer when I'm the owner. `user_cache` collapses repeat
    admin lookups within one request."""
    if conv["client_id"] != me_id and conv.get("owner_id") == me_id:
        client_id = conv["client_id"]
        if client_id not in user_cache:
            user_cache[client_id] = _user_display(db, client_id)
        return user_cache[client_id]
    p = prov_map.get(conv["provider_id"])
    return p or {"id": conv["provider_id"], "name": "", "avatar_url": None}


def _load_conversation(uc, conversation_id: str) -> dict:
    """Load a thread through the user client (RLS scopes to participants). 404 if
    missing or the caller isn't a participant."""
    row = maybe_row(uc.table("conversations").select("*").eq("id", conversation_id))
    if row is None:
        raise api_error(NOT_FOUND, "That conversation could not be found.")
    return row


# --- endpoints -------------------------------------------------------------


@router.get("")
def list_conversations(user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    convs = uc.table("conversations").select("*").execute().data or []
    if not convs:
        return []

    conv_ids = [c["id"] for c in convs]
    prov_map = _provider_map(db, [c["provider_id"] for c in convs])

    # Unread = the other party's un-read, non-deleted messages, tallied per thread.
    unread_rows = (
        uc.table("messages")
        .select("conversation_id,sender_id,read_at,deleted_at")
        .in_("conversation_id", conv_ids)
        .execute()
        .data
        or []
    )
    unread: dict[str, int] = {}
    for m in unread_rows:
        if m.get("read_at") is None and m.get("deleted_at") is None and m["sender_id"] != user.id:
            unread[m["conversation_id"]] = unread.get(m["conversation_id"], 0) + 1

    user_cache: dict[str, dict] = {}
    out = [
        serialize_conversation(
            c,
            other_party=_other_party(db, c, user.id, prov_map, user_cache),
            unread_count=unread.get(c["id"], 0),
        )
        for c in convs
    ]
    # Most recent thread first; threads with no messages yet sort to the bottom.
    out.sort(key=lambda c: c["lastMessageAtUtc"] or "", reverse=True)
    return out


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, user: AuthUser = Depends(require_user)):
    """A single thread with its other party + unread count — what the thread view
    needs for its header on a direct deep-link (404s a non-participant)."""
    db = get_supabase()
    uc = get_user_client(user.token)
    conv = _load_conversation(uc, conversation_id)
    prov_map = _provider_map(db, [conv["provider_id"]])
    other = _other_party(db, conv, user.id, prov_map, {})
    rows = (
        uc.table("messages")
        .select("sender_id,read_at,deleted_at")
        .eq("conversation_id", conversation_id)
        .execute()
        .data
        or []
    )
    unread = sum(
        1
        for m in rows
        if m.get("read_at") is None and m.get("deleted_at") is None and m["sender_id"] != user.id
    )
    return serialize_conversation(conv, other_party=other, unread_count=unread)


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str, user: AuthUser = Depends(require_user)):
    uc = get_user_client(user.token)
    _load_conversation(uc, conversation_id)  # 404s non-participants
    rows = (
        uc.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    return [serialize_message(r, me_id=user.id) for r in rows]


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str, payload: MessageCreateReq, user: AuthUser = Depends(require_user)
):
    uc = get_user_client(user.token)
    _load_conversation(uc, conversation_id)  # 404s non-participants
    body = (payload.body or "").strip()
    if not body:
        raise api_error(INVALID_RANGE, "A message can't be empty.")

    row = {
        "conversation_id": conversation_id,
        "sender_id": user.id,
        "body": body,
        "reply_to_id": payload.reply_to_id or None,
        "delivered_at": iso_utc(now_utc()),
    }
    inserted = uc.table("messages").insert(row).execute().data
    inserted = enforce_rls_write(inserted, entity="message")
    return serialize_message(inserted[0], me_id=user.id)


@router.post("/{conversation_id}/read")
def mark_read(conversation_id: str, user: AuthUser = Depends(require_user)):
    """Mark the other party's unread messages in this thread as read (the read
    receipt the sender sees flip to 'Read'). A no-op when nothing is unread."""
    uc = get_user_client(user.token)
    _load_conversation(uc, conversation_id)  # 404s non-participants
    updated = (
        uc.table("messages")
        .update({"read_at": iso_utc(now_utc())})
        .eq("conversation_id", conversation_id)
        .neq("sender_id", user.id)
        .is_("read_at", "null")
        .execute()
        .data
        or []
    )
    return {"conversationId": conversation_id, "readCount": len(updated)}


@router.delete("/{conversation_id}/messages/{message_id}")
def delete_message(
    conversation_id: str, message_id: str, user: AuthUser = Depends(require_user)
):
    """Soft-delete one of the caller's own messages (body blanks to a 'Message
    deleted' placeholder; the row and its receipts survive)."""
    uc = get_user_client(user.token)
    _load_conversation(uc, conversation_id)  # 404s non-participants
    updated = (
        uc.table("messages")
        .update({"deleted_at": iso_utc(now_utc())})
        .eq("id", message_id)
        .eq("conversation_id", conversation_id)
        .eq("sender_id", user.id)
        .execute()
        .data
        or []
    )
    if not updated:
        raise api_error(NOT_FOUND, "That message could not be found.")
    return serialize_message(updated[0], me_id=user.id)


@router.post("")
def start_conversation(payload: ConversationCreateReq, user: AuthUser = Depends(require_user)):
    """Find-or-create a thread with a provider. Two directions:
      * **client** (default) — the caller is the customer: `client_id = me`,
        `owner_id` resolved from the provider.
      * **owner** — the caller passes a `client_id` to reach out to; the caller
        must own the provider (verified below), so `owner_id = me`.
    Idempotent on the (provider, client) pair either way."""
    db = get_supabase()
    uc = get_user_client(user.token)

    provider = maybe_row(
        db.table("providers").select("id,name,owner_id,metadata").eq("id", payload.provider_id)
    )
    if provider is None:
        raise api_error(NOT_FOUND, "That business could not be found.")

    if payload.client_id:
        # Owner path: only the provider's owner may open a thread with a customer.
        if provider.get("owner_id") != user.id:
            raise HTTPException(403, "You can only message customers of your own business.")
        client_id, owner_id = payload.client_id, user.id
    else:
        client_id, owner_id = user.id, provider.get("owner_id")

    existing = maybe_row(
        uc.table("conversations")
        .select("*")
        .eq("provider_id", payload.provider_id)
        .eq("client_id", client_id)
    )
    if existing is not None:
        conv = existing
    else:
        inserted = (
            uc.table("conversations")
            .insert(
                {"provider_id": payload.provider_id, "client_id": client_id, "owner_id": owner_id}
            )
            .execute()
            .data
        )
        conv = enforce_rls_write(inserted, entity="conversation")[0]

    other = _other_party(db, conv, user.id, _provider_map(db, [conv["provider_id"]]), {})
    return serialize_conversation(conv, other_party=other, unread_count=0)
