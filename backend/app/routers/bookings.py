from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import get_supabase, maybe_row
from app.meta import validate_metadata
from app.models import ActorBody, BookingCreate, RescheduleRequest
from app.rules import RuleViolation, apply_rules, check_capacity

router = APIRouter(prefix="/bookings", tags=["bookings"])


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
def list_bookings(client_email: str | None = None, status: str | None = None):
    query = get_supabase().table("bookings").select("*")
    if client_email:
        query = query.eq("client_email", client_email)
    if status:
        query = query.eq("status", status)
    return query.execute().data


@router.post("")
def create_booking(payload: BookingCreate):
    db = get_supabase()
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
        "client_email": payload.client_email,
        "client_id": payload.client_id,
        "metadata": payload.metadata,
        "status": "confirmed",
        "history": [_history_entry("confirmed")],
    }
    return db.table("bookings").insert(row).execute().data


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, body: ActorBody | None = None):
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")
    if booking["status"] == "cancelled":
        raise HTTPException(409, "Booking is already cancelled.")

    is_owner = bool(body and body.actor == "owner")
    slot = _booking_slot(db, booking)
    if not is_owner:
        # The cancellation window constrains clients; owners override it.
        try:
            apply_rules("booking.change", {"slot_starts_at": slot["starts_at"]})
        except RuleViolation as e:
            raise HTTPException(409, str(e))

    history = booking["history"] + [
        _history_entry("cancelled", actor="owner" if is_owner else None)
    ]
    return (
        db.table("bookings")
        .update({"status": "cancelled", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )


@router.post("/{booking_id}/confirm")
def confirm_booking(booking_id: str):
    """Owner action — move a booking to confirmed and record it in history."""
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")

    history = booking["history"] + [_history_entry("confirmed", actor="owner")]
    return (
        db.table("bookings")
        .update({"status": "confirmed", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )


@router.post("/{booking_id}/reschedule")
def reschedule_booking(booking_id: str, payload: RescheduleRequest):
    db = get_supabase()
    booking = _booking(db, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")

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
    return (
        db.table("bookings")
        .update(
            {"slot_id": payload.new_slot_id, "status": "confirmed", "history": history}
        )
        .eq("id", booking_id)
        .execute()
        .data
    )


def _booking_slot(db, booking: dict) -> dict:
    slot = maybe_row(db.table("slots").select("*").eq("id", booking["slot_id"]))
    if slot is None:
        raise HTTPException(404, "Slot not found")
    return slot
