"""Bookings — the reworked booking loop.

A booking spans one-or-more contiguous, same-resource slots (`booking_slots`),
carries a party size, and computes its reference/price/span/status server-side
(the client's totals are never trusted). Capacity is re-checked at commit from
`slot_occupancy` (which sums party size). Rule violations surface as the
frontend's ApiError codes via `app.errors`.

Reads/writes of a user's own rows go through the RLS-scoped user client;
occupancy/aggregation and slot timings read via the service key (system work).
All endpoints here return a single serialized Booking except `GET /bookings`,
which returns a list.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.auth import AuthUser, enforce_rls_write, require_user
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import (
    CAPACITY_EXCEEDED,
    CUTOFF_PASSED,
    INVALID_RANGE,
    NOT_FOUND,
    SLOT_UNAVAILABLE,
    api_error,
)
from app.models import BookingCreateReq, ReviewReq, RescheduleReq
from app.serialize import _parse, effective_booking_status, iso_utc, serialize_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])

# Reference alphabet — no ambiguous chars (mirrors the mock's BK- references).
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _reference() -> str:
    return "BK-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- lookups ---------------------------------------------------------------


def _load_service(db, service_id: str) -> dict:
    row = maybe_row(db.table("services").select("*").eq("id", service_id))
    if row is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")
    return row


def _occ_by_id(db, slot_ids: list[str]) -> dict[str, dict]:
    if not slot_ids:
        return {}
    rows = db.table("slot_occupancy").select("*").in_("slot_id", slot_ids).execute().data or []
    return {r["slot_id"]: r for r in rows}


def _slot_ids_map(uc, booking_ids: list[str]) -> dict[str, list[str]]:
    if not booking_ids:
        return {}
    rows = (
        uc.table("booking_slots").select("booking_id,slot_id").in_("booking_id", booking_ids).execute().data
        or []
    )
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["booking_id"], []).append(r["slot_id"])
    return out


def _slot_time_map(db, slot_ids: list[str]) -> dict[str, tuple]:
    if not slot_ids:
        return {}
    rows = db.table("slots").select("id,starts_at,ends_at").in_("id", slot_ids).execute().data or []
    return {r["id"]: (r["starts_at"], r["ends_at"]) for r in rows}


def _reviews_map(db, booking_ids: list[str]) -> dict[str, dict]:
    if not booking_ids:
        return {}
    rows = db.table("reviews").select("*").in_("booking_id", booking_ids).execute().data or []
    out: dict[str, dict] = {}
    for r in rows:  # one review per booking; keep the last seen
        out[r["booking_id"]] = r
    return out


def _ordered_span(slot_ids: list[str], time_map: dict[str, tuple]) -> tuple[list[str], str | None, str | None]:
    """Order slot ids by start; return (ordered_ids, first_start, last_end)."""
    known = [sid for sid in slot_ids if sid in time_map]
    known.sort(key=lambda sid: _parse(time_map[sid][0]))
    if not known:
        return slot_ids, None, None
    return known, time_map[known[0]][0], time_map[known[-1]][1]


# --- selection resolution (capacity / contiguity / party) ------------------


def _resolve_selection(
    service: dict,
    occ: dict[str, dict],
    slot_ids: list[str],
    resource_id: str,
    party_size: int,
    credit: set[str],
) -> list[dict]:
    """Validate a slot selection at commit time and return the occupancy rows in
    start order. `credit` is the set of slots the booking already holds (party
    size credited back, for reschedule overlap). Raises the appropriate ApiError."""
    if not slot_ids:
        raise api_error(INVALID_RANGE, "Choose at least one time.")

    rows: list[dict] = []
    for sid in slot_ids:
        r = occ.get(sid)
        if r is None:
            raise api_error(NOT_FOUND, "That time no longer exists.")
        if r["resource_id"] != resource_id:
            raise api_error(INVALID_RANGE, "All times must be for the same option.")
        rows.append(r)

    lo, hi = service["min_slots_per_booking"], service["max_slots_per_booking"]
    n = len(rows)
    if n < lo or n > hi:
        if hi == 1:
            raise api_error(INVALID_RANGE, "Only one slot can be booked at a time.")
        raise api_error(INVALID_RANGE, f"Select between {lo} and {hi} times.")

    rows.sort(key=lambda r: _parse(r["starts_at"]))
    for i in range(1, n):
        if _parse(rows[i]["starts_at"]) != _parse(rows[i - 1]["ends_at"]):
            raise api_error(INVALID_RANGE, "Times must be back-to-back with no gaps.")

    now = _now()
    for r in rows:
        if _parse(r["ends_at"]) <= now:
            raise api_error(SLOT_UNAVAILABLE, "That time has already passed.")
        cap = r["capacity"]
        if cap <= 0:
            raise api_error(SLOT_UNAVAILABLE, "That time is blocked.")
        if party_size > cap:
            raise api_error(CAPACITY_EXCEEDED, "Party size exceeds the capacity for that time.")
        booked = r["booked_count"] - (party_size if r["slot_id"] in credit else 0)
        if cap - booked < party_size:
            raise api_error(
                SLOT_UNAVAILABLE,
                "That time was just taken. We've refreshed availability.",
                details={"slotId": r["slot_id"]},
            )
    return rows


# --- enrichment ------------------------------------------------------------


def _enrich(db, uc, bookings: list[dict]) -> list[dict]:
    """Serialize bookings with their slot ids, span, and review, batched."""
    ids = [b["id"] for b in bookings]
    sids_map = _slot_ids_map(uc, ids)
    all_sids = {s for b in bookings for s in (sids_map.get(b["id"]) or [b["slot_id"]])}
    time_map = _slot_time_map(db, list(all_sids))
    reviews = _reviews_map(db, ids)
    now = _now()

    out = []
    for b in bookings:
        sids = sids_map.get(b["id"]) or ([b["slot_id"]] if b.get("slot_id") else [])
        ordered, start, end = _ordered_span(sids, time_map)
        out.append(
            serialize_booking(
                b, slot_ids=ordered, start_utc=start, end_utc=end, review=reviews.get(b["id"]), now=now
            )
        )
    return out


def _load_own(uc, booking_id: str) -> dict:
    """Load a booking through the user client (RLS scopes to own/owner). 404 if
    missing or not visible to this user."""
    row = maybe_row(uc.table("bookings").select("*").eq("id", booking_id))
    if row is None:
        raise api_error(NOT_FOUND, "That booking could not be found.")
    return row


def _span_of(db, booking: dict, uc) -> tuple[list[str], str | None, str | None]:
    sids = _slot_ids_map(uc, [booking["id"]]).get(booking["id"]) or (
        [booking["slot_id"]] if booking.get("slot_id") else []
    )
    time_map = _slot_time_map(db, sids)
    return _ordered_span(sids, time_map)


# --- endpoints -------------------------------------------------------------


@router.get("")
def list_bookings(scope: str = "all", user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    rows = uc.table("bookings").select("*").execute().data or []
    bookings = _enrich(db, uc, rows)

    now_iso = iso_utc(_now())

    def is_upcoming(b: dict) -> bool:
        return bool(b["endUtc"] and b["endUtc"] > now_iso and b["status"] != "completed")

    if scope == "upcoming":
        bookings = [b for b in bookings if is_upcoming(b)]
        bookings.sort(key=lambda b: b["startUtc"] or "")
    elif scope == "past":
        bookings = [b for b in bookings if not is_upcoming(b)]
        bookings.sort(key=lambda b: b["startUtc"] or "", reverse=True)
    else:
        bookings.sort(key=lambda b: b["startUtc"] or "", reverse=True)
    return bookings


@router.get("/{booking_id}")
def get_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    return _enrich(db, uc, [booking])[0]


@router.post("")
def create_booking(payload: BookingCreateReq, user: AuthUser = Depends(require_user)):
    if not user.email:
        raise api_error(NOT_FOUND, "Authenticated user has no email to book under.")
    db = get_supabase()
    service = _load_service(db, payload.service_id)
    party = max(1, int(payload.party_size or 1))

    occ = _occ_by_id(db, payload.slot_ids)
    rows = _resolve_selection(service, occ, payload.slot_ids, payload.resource_id, party, credit=set())
    ordered = [r["slot_id"] for r in rows]
    start, end = rows[0]["starts_at"], rows[-1]["ends_at"]

    metadata = {
        "party_size": party,
        "reference": _reference(),
        "price_minor_units": service["price_minor_units"] * len(rows) * party,
        "currency": service["currency"],
        "provider_id": service["provider_id"],
        "service_id": service["id"],
        "resource_id": payload.resource_id,
        "user_id": user.id,
        "slot_ids": ordered,
        "change_history": [],
    }
    row = {
        "slot_id": ordered[0],  # first slot, for base-table compatibility
        "client_email": user.email,
        "client_id": user.id,
        "status": "confirmed",
        "history": [{"status": "confirmed", "at": iso_utc(_now())}],
        "metadata": metadata,
    }
    uc = get_user_client(user.token)
    inserted = uc.table("bookings").insert(row).execute().data
    inserted = enforce_rls_write(inserted, entity="booking")
    booking = inserted[0]
    uc.table("booking_slots").insert(
        [{"booking_id": booking["id"], "slot_id": sid} for sid in ordered]
    ).execute()
    return serialize_booking(booking, slot_ids=ordered, start_utc=start, end_utc=end, review=None)


@router.post("/{booking_id}/reschedule")
def reschedule_booking(
    booking_id: str, payload: RescheduleReq, user: AuthUser = Depends(require_user)
):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))

    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    if effective_booking_status(booking["status"], cur_end) != "confirmed":
        raise api_error(CUTOFF_PASSED, "Only upcoming bookings can be moved.")
    if not user.is_owner:
        cutoff = service["cancellation_cutoff_hours"]
        if cur_start and _now() >= _parse(cur_start) - timedelta(hours=cutoff):
            raise api_error(CUTOFF_PASSED, f"Changes closed — within {cutoff}h of the start.")

    party = int(md.get("party_size", 1))
    resource_id = md.get("resource_id")
    occ = _occ_by_id(db, payload.new_slot_ids)
    rows = _resolve_selection(
        service, occ, payload.new_slot_ids, resource_id, party, credit=set(cur_ids)
    )
    ordered = [r["slot_id"] for r in rows]
    new_start, new_end = rows[0]["starts_at"], rows[-1]["ends_at"]

    # Atomic slot swap: replace the join rows, then update the booking.
    uc.table("booking_slots").delete().eq("booking_id", booking_id).execute()
    uc.table("booking_slots").insert(
        [{"booking_id": booking_id, "slot_id": sid} for sid in ordered]
    ).execute()

    md["slot_ids"] = ordered
    md["price_minor_units"] = service["price_minor_units"] * len(rows) * party
    md.setdefault("change_history", []).append(
        {
            "at_utc": iso_utc(_now()),
            "from_start_utc": iso_utc(cur_start),
            "to_start_utc": iso_utc(new_start),
        }
    )
    history = booking["history"] + [{"status": "rescheduled", "at": iso_utc(_now())}]
    updated = (
        uc.table("bookings")
        .update({"slot_id": ordered[0], "status": "confirmed", "history": history, "metadata": md})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    review = _reviews_map(db, [booking_id]).get(booking_id)
    return serialize_booking(updated[0], slot_ids=ordered, start_utc=new_start, end_utc=new_end, review=review)


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    if booking["status"] == "cancelled":  # idempotent
        review = _reviews_map(db, [booking_id]).get(booking_id)
        return serialize_booking(booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review)

    if effective_booking_status(booking["status"], cur_end) == "completed":
        raise api_error(CUTOFF_PASSED, "Completed bookings can't be cancelled.")
    if not user.is_owner:
        md = booking.get("metadata") or {}
        service = _load_service(db, md.get("service_id"))
        cutoff = service["cancellation_cutoff_hours"]
        if cur_start and _now() >= _parse(cur_start) - timedelta(hours=cutoff):
            raise api_error(CUTOFF_PASSED, f"Changes closed — within {cutoff}h of the start.")

    md = dict(booking.get("metadata") or {})
    md["cancelled_at_utc"] = iso_utc(_now())
    history = booking["history"] + [
        {"status": "cancelled", "at": iso_utc(_now()), **({"actor": "owner"} if user.is_owner else {})}
    ]
    updated = (
        uc.table("bookings")
        .update({"status": "cancelled", "history": history, "metadata": md})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    return serialize_booking(updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=None)


@router.post("/{booking_id}/review")
def review_booking(booking_id: str, payload: ReviewReq, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    if effective_booking_status(booking["status"], cur_end) != "completed":
        raise api_error(NOT_FOUND, "Only completed bookings can be reviewed.")

    rating = max(1, min(5, round(payload.rating)))
    md = booking.get("metadata") or {}
    # One review per booking: clear any prior (service key — no user delete
    # policy) then insert through the user client (RLS reviews_insert_own).
    db.table("reviews").delete().eq("booking_id", booking_id).execute()
    uc.table("reviews").insert(
        {
            "booking_id": booking_id,
            "provider_id": md.get("provider_id"),
            "rating": rating,
            "text": (payload.text or "").strip(),
        }
    ).execute()
    review = maybe_row(db.table("reviews").select("*").eq("booking_id", booking_id))
    return serialize_booking(booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review)
