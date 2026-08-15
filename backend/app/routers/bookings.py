from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthUser, enforce_rls_write, require_owner, require_user
from app.config import get_config
from app.db import get_supabase, get_user_client, maybe_row
from app.meta import validate_metadata
from app.models import BookingCreate, RescheduleRequest
from app.rules import RuleViolation, apply_rules, check_capacity

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _own_or_owner(booking: dict, user: AuthUser) -> None:
    """A client may only act on their own bookings; an owner may act on any.
    403 otherwise. Message pivots with the domain via ``terms.booking``."""
    if user.is_owner or booking.get("client_email") == user.email:
        return
    booking_term = get_config()["terms"]["booking"].lower()
    raise HTTPException(403, f"You can only manage your own {booking_term}.")


def _history_entry(status: str, actor: str | None = None) -> dict:
    entry = {"status": status, "at": datetime.now(timezone.utc).isoformat()}
    if actor:
        entry["actor"] = actor
    return entry


def _occupancy(db, slot_id: str) -> dict | None:
    return maybe_row(db.table("slot_occupancy").select("*").eq("slot_id", slot_id))


def _booking(db, booking_id: str) -> dict | None:
    return maybe_row(db.table("bookings").select("*").eq("id", booking_id))


@router.get("")
def list_bookings(
    user: AuthUser = Depends(require_user),
    client_email: str | None = None,
    status: str | None = None,
):
    # Read through the user's own client so RLS scopes the result: a client sees
    # only their own rows, an owner sees all. The owner may still narrow to one
    # client via the query param; for a client that param is moot (RLS already
    # limits them to themselves).
    query = get_user_client(user.token).table("bookings").select("*")
    if user.is_owner and client_email:
        query = query.eq("client_email", client_email)
    if status:
        query = query.eq("status", status)
    return query.execute().data


@router.post("")
def create_booking(payload: BookingCreate, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    if not user.email:
        raise HTTPException(400, "Authenticated user has no email to book under.")
    slot = _occupancy(db, payload.slot_id)
    if slot is None:
        raise HTTPException(404, "Slot not found")

    validate_metadata("bookings", payload.metadata)
    try:
        apply_rules(
            "booking.create",
            {
                "booked_count": slot["booked_count"],
                "capacity": slot["capacity"],
                "slot_starts_at": slot["starts_at"],
            },
        )
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    row = {
        "slot_id": payload.slot_id,
        # Ownership comes from the verified token, not the body.
        "client_email": user.email,
        "client_id": user.id,
        "metadata": payload.metadata,
        "status": "confirmed",
        "history": [_history_entry("confirmed")],
    }
    # Insert through the user's client: RLS's bookings_insert_own enforces that
    # client_id == the authenticated user (capacity was read above via service).
    inserted = get_user_client(user.token).table("bookings").insert(row).execute().data
    return enforce_rls_write(inserted, entity="booking")


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")
    _own_or_owner(booking, user)
    if booking["status"] == "cancelled":
        raise HTTPException(409, "Booking is already cancelled.")

    # The owner role (verified from the token) overrides the cancellation
    # window; a client is held to it.
    is_owner = user.is_owner
    slot = _booking_slot(db, booking)
    if not is_owner:
        try:
            apply_rules("booking.change", {"slot_starts_at": slot["starts_at"]})
        except RuleViolation as e:
            raise HTTPException(409, str(e))

    history = booking["history"] + [
        _history_entry("cancelled", actor="owner" if is_owner else None)
    ]
    # The write goes through the user's client so RLS is the final authority
    # (a client can only touch their own row; an owner, any).
    updated = (
        get_user_client(user.token)
        .table("bookings")
        .update({"status": "cancelled", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )
    return enforce_rls_write(updated, entity="booking")


@router.post("/{booking_id}/confirm")
def confirm_booking(booking_id: str, owner: AuthUser = Depends(require_owner)):
    """Owner action — move a booking to confirmed and record it in history."""
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")

    history = booking["history"] + [_history_entry("confirmed", actor="owner")]
    updated = (
        get_user_client(owner.token)
        .table("bookings")
        .update({"status": "confirmed", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )
    return enforce_rls_write(updated, entity="booking")


@router.post("/{booking_id}/reschedule")
def reschedule_booking(
    booking_id: str,
    payload: RescheduleRequest,
    user: AuthUser = Depends(require_user),
):
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")
    _own_or_owner(booking, user)

    slot = _booking_slot(db, booking)
    try:
        apply_rules("booking.change", {"slot_starts_at": slot["starts_at"]})
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    new_slot = _occupancy(db, payload.new_slot_id)
    if new_slot is None:
        raise HTTPException(404, "New slot not found")

    # Don't count the booking being moved against its own target slot,
    # otherwise a capacity-1 self-reschedule would be reported as full.
    booked = new_slot["booked_count"]
    if booking["slot_id"] == payload.new_slot_id and booking["status"] == "confirmed":
        booked -= 1
    try:
        check_capacity(booked, new_slot["capacity"])
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    history = booking["history"] + [_history_entry("rescheduled")]
    updated = (
        get_user_client(user.token)
        .table("bookings")
        .update(
            {"slot_id": payload.new_slot_id, "status": "confirmed", "history": history}
        )
        .eq("id", booking_id)
        .execute()
        .data
    )
    return enforce_rls_write(updated, entity="booking")


def _booking_slot(db, booking: dict) -> dict:
    slot = maybe_row(db.table("slots").select("*").eq("id", booking["slot_id"]))
    if slot is None:
        raise HTTPException(404, "Slot not found")
    return slot
