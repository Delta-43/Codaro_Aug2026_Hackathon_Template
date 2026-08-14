from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response

from app.config import get_config
from app.db import get_supabase, maybe_row
from app.meta import validate_metadata
from app.models import SlotCreate, SlotUpdate
from app.rules import RuleViolation, apply_rules, parse_ts

router = APIRouter(prefix="/slots", tags=["slots"])


@router.get("")
def list_slots(resource_id: str | None = None):
    query = get_supabase().table("slots").select("*")
    if resource_id:
        query = query.eq("resource_id", resource_id)
    return query.execute().data


@router.get("/occupancy")
def slot_occupancy(resource_id: str | None = None):
    query = get_supabase().table("slot_occupancy").select("*")
    if resource_id:
        query = query.eq("resource_id", resource_id)
    return query.execute().data


@router.post("")
def create_slot(payload: SlotCreate):
    db = get_supabase()
    rules = get_config()["rules"]

    ends_at = payload.ends_at
    if ends_at is None:
        ends_at = (
            parse_ts(payload.starts_at) + timedelta(minutes=rules["slotDurationMinutes"])
        ).isoformat()
    capacity = payload.capacity if payload.capacity is not None else rules["maxBookingsPerSlot"]

    validate_metadata("slots", payload.metadata)

    existing = (
        db.table("slots").select("*").eq("resource_id", payload.resource_id).execute().data
    )
    try:
        apply_rules(
            "slot.create",
            {"starts_at": payload.starts_at, "ends_at": ends_at, "existing_slots": existing},
        )
    except RuleViolation as e:
        raise HTTPException(409, str(e))

    row = {
        "resource_id": payload.resource_id,
        "starts_at": payload.starts_at,
        "ends_at": ends_at,
        "capacity": capacity,
        "metadata": payload.metadata,
    }
    return db.table("slots").insert(row).execute().data


@router.patch("/{slot_id}")
def update_slot(slot_id: str, payload: SlotUpdate):
    db = get_supabase()
    existing = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if existing is None:
        raise HTTPException(404, "Slot not found")

    patch = payload.model_dump(exclude_none=True)
    if "metadata" in patch:
        validate_metadata("slots", patch["metadata"])
    if not patch:
        return [existing]
    return db.table("slots").update(patch).eq("id", slot_id).execute().data


@router.delete("/{slot_id}", status_code=204)
def delete_slot(slot_id: str):
    db = get_supabase()
    existing = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if existing is None:
        raise HTTPException(404, "Slot not found")
    # schema cascade removes dependent bookings.
    db.table("slots").delete().eq("id", slot_id).execute()
    return Response(status_code=204)
