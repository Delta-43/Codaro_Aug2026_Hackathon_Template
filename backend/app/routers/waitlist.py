"""Waitlist — who wants a slot that is already full.

`timing.waitlist` (`enabled`, `autoPromote`, `maxPerSlot`) shipped with v2 and
was enforced by nothing: a config could advertise a 200-deep auto-promoting
queue and the engine had no way to record one person on it. `capabilities.
waitlist` gates the whole surface.

The queue is per SLOT, not per service: a customer wants a particular time, and
"any time next week" is a search, not a waitlist.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth import AuthUser, enforce_rls_write, require_user
from app.clock import now_utc
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import INVALID_RANGE, NOT_FOUND, api_error
from app.rules import capability, effective_service_config
from app.serialize import iso_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slots", tags=["waitlist"])


def waitlist_config(service: dict | None) -> dict:
    """The resolved `timing.waitlist` block for a service."""
    return effective_service_config(service)["timing"].get("waitlist") or {}


def _slot_or_404(db, slot_id: str) -> dict:
    row = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if row is None:
        raise api_error(NOT_FOUND, "That time no longer exists.")
    return row


def serialize_entry(row: dict, *, ahead: int | None = None) -> dict:
    out = {
        "id": row["id"],
        "slotId": row["slot_id"],
        "serviceId": row.get("service_id"),
        "resourceId": row.get("resource_id"),
        "partySize": int(row.get("party_size") or 1),
        "position": int(row.get("position") or 0),
        "status": row.get("status"),
        "bookingId": row.get("booking_id"),
        "createdAtUtc": iso_utc(row.get("created_at")),
    }
    if ahead is not None:
        # What the customer actually wants to know. `position` is a join-order
        # stamp that is never renumbered, so it is not a place in the queue.
        out["peopleAhead"] = ahead
    return out


@router.post("/{slot_id}/waitlist")
def join_waitlist(slot_id: str, user: AuthUser = Depends(require_user)):
    """Take a place in the queue for a full slot.

    Refuses when the slot still has room — a waitlist for something bookable is
    a worse experience than booking it, and would let someone hold a queue place
    against a seat they could simply take.
    """
    db = get_supabase()
    slot = _slot_or_404(db, slot_id)
    service_id = (slot.get("metadata") or {}).get("service_id")
    service = maybe_row(db.table("services").select("*").eq("id", service_id)) if service_id else None

    if not capability("waitlist", service):
        raise api_error(INVALID_RANGE, "This service does not offer a waitlist.")
    cfg = waitlist_config(service)
    if not cfg.get("enabled"):
        raise api_error(INVALID_RANGE, "This service does not offer a waitlist.")

    occ = maybe_row(db.table("slot_occupancy").select("*").eq("slot_id", slot_id))
    remaining = int((occ or {}).get("available_count") or 0)
    if remaining > 0:
        raise api_error(INVALID_RANGE, "That time is still available — book it instead.")

    existing = (
        db.table("waitlist_entries").select("*")
        .eq("slot_id", slot_id).eq("status", "waiting").execute().data
        or []
    )
    mine = next((e for e in existing if e["user_id"] == user.id), None)
    if mine:
        # Idempotent: joining twice returns the place already held rather than
        # erroring, so a double-tap cannot look like a failure.
        return serialize_entry(mine, ahead=sum(1 for e in existing if e["position"] < mine["position"]))

    cap = int(cfg.get("maxPerSlot") or 0)
    if cap and len(existing) >= cap:
        raise api_error(INVALID_RANGE, "The waitlist for that time is full.")

    position = max((int(e["position"]) for e in existing), default=0) + 1
    inserted = get_user_client(user.token).table("waitlist_entries").insert({
        "slot_id": slot_id,
        "user_id": user.id,
        "service_id": service_id,
        "resource_id": slot.get("resource_id"),
        "party_size": 1,
        "position": position,
    }).execute().data
    inserted = enforce_rls_write(inserted, entity="waitlist entry")
    return serialize_entry(inserted[0], ahead=len(existing))


@router.delete("/{slot_id}/waitlist")
def leave_waitlist(slot_id: str, user: AuthUser = Depends(require_user)):
    """Give up a place. Positions are NOT renumbered — see the schema note."""
    uc = get_user_client(user.token)
    uc.table("waitlist_entries").update({"status": "cancelled"}) \
        .eq("slot_id", slot_id).eq("user_id", user.id).eq("status", "waiting").execute()
    return {"ok": True}


@router.get("/{slot_id}/waitlist")
def my_place(slot_id: str, user: AuthUser = Depends(require_user)):
    """This customer's place in one slot's queue, or null."""
    db = get_supabase()
    rows = (
        db.table("waitlist_entries").select("*")
        .eq("slot_id", slot_id).eq("status", "waiting").execute().data
        or []
    )
    mine = next((e for e in rows if e["user_id"] == user.id), None)
    if mine is None:
        return {"entry": None, "depth": len(rows)}
    return {
        "entry": serialize_entry(mine, ahead=sum(1 for e in rows if e["position"] < mine["position"])),
        "depth": len(rows),
    }


def promote_from_waitlist(db, slot_ids: list[str], service: dict | None) -> list[dict]:
    """Hand a freed seat to the head of each slot's queue.

    Called when capacity is released (a cancellation). Returns the entries that
    were promoted, for logging and tests.

    `autoPromote: false` is a real configuration, not an oversight: plenty of
    businesses want to ring the next person rather than commit them to a booking
    they have not agreed to. In that mode the queue is recorded and the owner
    works it manually, so this returns nothing.

    Best-effort by design — a cancellation must succeed whether or not the
    promotion does. The customer being cancelled is owed their cancellation; the
    person on the waitlist is owed a call, and a failure here leaves them at the
    head of the queue for the next attempt rather than losing their place.
    """
    if not slot_ids or not capability("waitlist", service):
        return []
    cfg = waitlist_config(service)
    if not cfg.get("enabled") or not cfg.get("autoPromote"):
        return []

    promoted: list[dict] = []
    for slot_id in slot_ids:
        try:
            occ = maybe_row(db.table("slot_occupancy").select("*").eq("slot_id", slot_id))
            if int((occ or {}).get("available_count") or 0) <= 0:
                continue  # nothing actually freed on this slot
            waiting = (
                db.table("waitlist_entries").select("*")
                .eq("slot_id", slot_id).eq("status", "waiting")
                .order("position").limit(1).execute().data
                or []
            )
            if not waiting:
                continue
            entry = waiting[0]
            booking = _book_for_entry(db, entry, slot_id)
            db.table("waitlist_entries").update({
                "status": "promoted",
                "booking_id": booking["id"] if booking else None,
            }).eq("id", entry["id"]).execute()
            promoted.append(entry)
        except Exception:
            logger.exception("Waitlist promotion failed for slot %s", slot_id)
    return promoted


def _book_for_entry(db, entry: dict, slot_id: str) -> dict | None:
    """Turn a promoted waitlist entry into a real booking.

    Deliberately created as PENDING regardless of the service's auto-approve
    setting. The customer joined a queue, they did not agree to a specific
    booking — auto-confirming would charge and commit someone who has not said
    yes since. Pending holds no capacity, so the seat stays available to whoever
    acts first, which is the honest behaviour.
    """
    # Imported here: `bookings` imports this module for `promote_from_waitlist`,
    # so a module-level import in the other direction would be circular.
    from app.references import booking_reference
    from app.routers.bookings import _consume_credit, _entitlement, _load_service, _price
    from app.serialize import iso_utc as _iso

    service = _load_service(db, entry["service_id"]) if entry.get("service_id") else None
    slot = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if service is None or slot is None:
        return None
    # `bookings.client_email` is NOT NULL and the waitlist row cannot carry it:
    # the table is new but already created, and the schema is append-only
    # (no ALTER), so the address is resolved here instead. One extra call on a
    # rare path — a cancellation with someone actually waiting.
    try:
        email = db.auth.admin.get_user_by_id(entry["user_id"]).user.email
    except Exception:
        logger.exception("Could not resolve email for waitlist user %s", entry["user_id"])
        return None
    if not email:
        return None

    party = int(entry.get("party_size") or 1)
    # Priced with the customer's entitlement, exactly as a direct booking would
    # be. Without it, reaching a seat through the queue cost more than booking
    # it yourself, and a pass-type plan spent no credit.
    ent = _entitlement(db, entry["user_id"], service)
    priced = _price(service, [{"starts_at": slot["starts_at"], "ends_at": slot["ends_at"],
                               "slot_id": slot_id}], party, ent)
    now = now_utc()
    rows = db.table("bookings").insert({
        "slot_id": slot_id,
        "client_email": email,
        "client_id": entry["user_id"],
        "status": "pending",
        "history": [{"status": "pending", "at": _iso(now), "actor": "waitlist"}],
        "metadata": {
            "party_size": party,
            "reference": booking_reference(),
            "price_minor_units": priced["amountMinorUnits"],
            "currency": priced["currency"],
            "price_breakdown": priced["breakdown"],
            "deposit_minor_units": priced["depositMinorUnits"],
            "entitlement_key": (ent or {}).get("key"),
            "entitlement_id": ((ent or {}).get("row") or {}).get("id"),
            "provider_id": service["provider_id"],
            "service_id": service["id"],
            "resource_id": entry.get("resource_id") or slot.get("resource_id"),
            "user_id": entry["user_id"],
            "slot_ids": [slot_id],
            "change_history": [],
            "from_waitlist": True,
        },
    }).execute().data
    if not rows:
        return None
    db.table("booking_slots").insert(
        [{"booking_id": rows[0]["id"], "slot_id": slot_id}]
    ).execute()
    _consume_credit(db, ent, rows[0]["id"])
    return rows[0]
