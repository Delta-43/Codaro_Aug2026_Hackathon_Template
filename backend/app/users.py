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
