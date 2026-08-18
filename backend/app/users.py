"""Assemble the frontend `User` from Supabase auth + the `follows` table.

Profile fields (displayName/avatarUrl/timezone/verified) live in Supabase
`user_metadata`; `followedProviderIds` come from the `follows` table (read
through the user's own client so RLS scopes it). Used by `/me` and the
follow/unfollow endpoints, both of which return the full updated User.
"""
from __future__ import annotations

from app.auth import AuthUser
from app.db import get_supabase, get_user_client
from app.serialize import serialize_user


def apply_user_attrs(user_id: str, attrs: dict) -> None:
    """Persist `attrs` (e.g. {"user_metadata": md} and/or {"email": ...}) via
    the Supabase Auth admin API. Best-effort: if the admin API is unavailable
    (e.g. offline), no-op — callers already return the intended state so the
    client's optimistic update holds for this session."""
    try:
        get_supabase().auth.admin.update_user_by_id(user_id, attrs)
    except Exception:
        pass


def admin_user_metadata(db, user_id: str) -> dict:
    """`user_metadata` for an arbitrary user id via the admin API, using the
    given (service-key) `db` client. Centralises the admin-response → metadata
    extraction; returns `{}` when the user or admin API is unavailable."""
    try:
        resp = db.auth.admin.get_user_by_id(user_id)
        u = getattr(resp, "user", None) or resp
        return dict(getattr(u, "user_metadata", None) or {})
    except Exception:
        return {}


def user_metadata(user: AuthUser) -> dict:
    """Fresh `user_metadata` for the user. Prefer the admin API (reflects a
    just-applied PATCH /me) and fall back to the token's claims if unavailable."""
    try:
        resp = get_supabase().auth.admin.get_user_by_id(user.id)
        u = getattr(resp, "user", None) or resp
        md = getattr(u, "user_metadata", None)
        if md is not None:
            return dict(md)
    except Exception:
        pass
    return dict(user.claims.get("user_metadata") or {})


def followed_ids(user: AuthUser) -> list[str]:
    rows = (
        get_user_client(user.token)
        .table("follows")
        .select("provider_id")
        .eq("user_id", user.id)
        .execute()
        .data
        or []
    )
    return [r["provider_id"] for r in rows]


def load_user(user: AuthUser) -> dict:
    return serialize_user(
        id=user.id,
        email=user.email,
        metadata=user_metadata(user),
        followed_provider_ids=followed_ids(user),
    )
