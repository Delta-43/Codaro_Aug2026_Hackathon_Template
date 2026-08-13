from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import get_supabase
from app.rules import RuleViolation, check_cancellation_window, check_capacity

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _history_entry(status: str) -> dict:
    return {"status": status, "at": datetime.now(timezone.utc).isoformat()}


@router.get("")
def list_bookings(client_email: str | None = None):
    query = get_supabase().table("bookings").select("*")
    if client_email:
        query = query.eq("client_email", client_email)
    return query.execute().data


@router.post("")
def create_booking(payload: dict):
    db = get_supabase()
    slot = (
        db.table("slot_occupancy")
        .select("*")
        .eq("slot_id", payload["slot_id"])
        .single()
        .execute()
        .data
    )
    if slot is None:
        raise HTTPException(404, "Slot not found")
    try:
        check_capacity(slot["booked_count"], slot["capacity"])
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    row = {
        **payload,
        "status": "confirmed",
        "history": [_history_entry("confirmed")],
    }
    return db.table("bookings").insert(row).execute().data


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str):
    db = get_supabase()
    booking = db.table("bookings").select("*").eq("id", booking_id).single().execute().data
    if booking is None:
        raise HTTPException(404, "Booking not found")

    slot = db.table("slots").select("*").eq("id", booking["slot_id"]).single().execute().data
    try:
        check_cancellation_window(datetime.fromisoformat(slot["starts_at"]))
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    history = booking["history"] + [_history_entry("cancelled")]
    return (
        db.table("bookings")
        .update({"status": "cancelled", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )


@router.post("/{booking_id}/reschedule")
def reschedule_booking(booking_id: str, payload: dict):
    """payload: {"new_slot_id": str}"""
    db = get_supabase()
    booking = db.table("bookings").select("*").eq("id", booking_id).single().execute().data
    if booking is None:
        raise HTTPException(404, "Booking not found")

    slot = db.table("slots").select("*").eq("id", booking["slot_id"]).single().execute().data
    try:
        check_cancellation_window(datetime.fromisoformat(slot["starts_at"]))
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    new_slot = (
        db.table("slot_occupancy")
        .select("*")
        .eq("slot_id", payload["new_slot_id"])
        .single()
        .execute()
        .data
    )
    if new_slot is None:
        raise HTTPException(404, "New slot not found")
    try:
        check_capacity(new_slot["booked_count"], new_slot["capacity"])
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    history = booking["history"] + [_history_entry("rescheduled")]
    return (
        db.table("bookings")
        .update({"slot_id": payload["new_slot_id"], "status": "confirmed", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )
