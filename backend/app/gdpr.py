# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""GDPR right-to-erasure orchestration (see backend/CLAUDE.md "Auth" and the
schema's FK map in supabase/schema.sql).

`erase_user` removes every record tied to a user and then their Supabase Auth
account. It runs with the **service key** (a system, cross-user operation,
mirrors `owner.py`) because the user↔booking link is a `client_id` column plus
`metadata`, not a database foreign key, so a plain `auth.users` delete would NOT
cascade bookings. The order matters:

  1. the user's own bookings (cascades booking_slots + reviews on them),
  2. reviews businesses left *about* the user (client_reviews.client_id),
  3. follows the user made,
  4. the user's avatar object in storage,
  5. if the user owns providers, the whole business under each (other customers'
     bookings included), then the provider rows themselves,
  6. finally the auth account (cascades profiles + any remaining follows).

The record-cleanup steps (1–5) are best-effort/idempotent: an offline admin API
or an already-deleted row must not turn erasure into a 500. The final
auth-account deletion (6) is authoritative, if it fails, `erase_user` raises so
the endpoint cannot falsely report success while the account still exists.
"""
from __future__ import annotations

import logging

from app.auth import OWNER_ROLE, AuthUser
from app.avatars import remove_avatar

logger = logging.getLogger(__name__)


def _safe(step: str, fn) -> None:
    """Run one erasure step, swallowing (but logging) any failure so the overall
    erasure proceeds, partial success beats a 500 that leaves the user unsure
    whether anything was removed."""
    try:
        fn()
    except Exception:  # noqa: BLE001 - erasure must be resilient to offline/missing tables
        logger.warning("gdpr erase: step %r failed; continuing.", step, exc_info=False)


def _delete_owned_businesses(db, owner_id: str) -> None:
    """For an owner, remove the whole business under each provider they own:
    every booking made against it (other customers' rows, provider_id lives in
    bookings.metadata, so this is a scan-and-filter), the resources beneath its
    services (slots cascade from resources), then the provider row itself
    (cascades services, reviews, follows, and client_reviews via their provider
    FKs)."""
    providers = db.table("providers").select("id").eq("owner_id", owner_id).execute().data or []
    provider_ids = {p["id"] for p in providers}
    if not provider_ids:
        return

    services = (
        db.table("services").select("id").in_("provider_id", list(provider_ids)).execute().data or []
    )
    service_ids = {s["id"] for s in services}

    # Bookings under these providers (provider_id is in metadata jsonb, no column
    # to filter on, so scan and match in Python, like owner.py's _Scope), then a
    # single batched delete rather than one round trip per row.
    all_bookings = db.table("bookings").select("id,metadata").execute().data or []
    doomed_bookings = [
        b["id"] for b in all_bookings if (b.get("metadata") or {}).get("provider_id") in provider_ids
    ]
    if doomed_bookings:
        _safe(
            "owner-bookings",
            lambda: db.table("bookings").delete().in_("id", doomed_bookings).execute(),
        )

    # Resources under these services (service_id is in metadata jsonb too).
    if service_ids:
        all_resources = db.table("resources").select("id,metadata").execute().data or []
        doomed_resources = [
            r["id"] for r in all_resources if (r.get("metadata") or {}).get("service_id") in service_ids
        ]
        if doomed_resources:
            _safe(
                "owner-resources",
                lambda: db.table("resources").delete().in_("id", doomed_resources).execute(),
            )

    _safe(
        "owner-providers",
        lambda: db.table("providers").delete().in_("id", list(provider_ids)).execute(),
    )


def erase_user(db, user: AuthUser) -> None:
    """Erase all records tied to `user` and delete their auth account. Record
    cleanup is best-effort; the final auth-account deletion is authoritative and
    raises on failure (so DELETE /me can't return a false 204). `db` must be the
    service-key client."""
    uid = user.id

    _safe(
        "own-bookings",
        lambda: db.table("bookings").delete().eq("client_id", uid).execute(),
    )
    # Legacy bookings keyed only by metadata.user_id (null client_id), the same
    # fallback identity list_bookings honours. Without this, a user's pre-auth
    # bookings survived erasure, leaving the GDPR delete incomplete.
    _safe(
        "own-bookings-legacy",
        lambda: db.table("bookings").delete()
        .is_("client_id", "null").eq("metadata->>user_id", uid).execute(),
    )
    _safe(
        "client-reviews",
        lambda: db.table("client_reviews").delete().eq("client_id", uid).execute(),
    )
    _safe(
        "follows",
        lambda: db.table("follows").delete().eq("user_id", uid).execute(),
    )
    _safe("avatar", lambda: remove_avatar(f"{uid}/avatar"))

    if user.role == OWNER_ROLE:
        _safe("owned-businesses", lambda: _delete_owned_businesses(db, uid))

    # The auth account is the definitive erasure: unlike the record-cleanup steps
    # above, a failure here must NOT be swallowed, reporting success while the
    # account still exists would be a false GDPR erasure. Let it propagate so
    # DELETE /me surfaces an error instead of a 204.
    db.auth.admin.delete_user(uid)
