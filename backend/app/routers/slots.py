from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import AuthUser, enforce_rls_write, require_owner
from app.db import get_supabase, get_user_client, maybe_row
from app.meta import validate_metadata
from app.models import SlotCreate, SlotUpdate
from app.rules import (
    RuleViolation,
    apply_rules,
    effective_service_config,
    effective_service_rules,
    parse_ts,
)

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


def _service_for_resource(db, resource_id: str) -> dict | None:
    """The service a slot's resource belongs to (`resources.metadata.service_id`).

    Slot geometry is a per-service fact — `services.slot_duration_minutes` is a
    column that exists for exactly this — but slot creation read the GLOBAL
    `timing` block, so neither that column nor a `metadata.timing` override
    affected the grid being laid down. Returns None when the resource is
    unlinked, and the global defaults then apply as before.
    """
    resource = maybe_row(db.table("resources").select("metadata").eq("id", resource_id))
    service_id = ((resource or {}).get("metadata") or {}).get("service_id")
    if not service_id:
        return None
    return maybe_row(db.table("services").select("*").eq("id", service_id))


@router.post("")
def create_slot(payload: SlotCreate, owner: AuthUser = Depends(require_owner)):
    db = get_supabase()
    service = _service_for_resource(db, payload.resource_id)
    rules = effective_service_rules(service)
    timing = effective_service_config(service)["timing"]

    ends_at = payload.ends_at
    if ends_at is None:
        ends_at = (
            parse_ts(payload.starts_at) + timedelta(minutes=rules["slotDurationMinutes"])
        ).isoformat()
    capacity = (
        payload.capacity if payload.capacity is not None else timing["maxBookingsPerSlot"]
    )

    validate_metadata("slots", payload.metadata)

    existing = (
        db.table("slots").select("*").eq("resource_id", payload.resource_id).execute().data
    )
    try:
        apply_rules(
            "slot.create",
            {"starts_at": payload.starts_at, "ends_at": ends_at, "existing_slots": existing},
            timing,
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
    # User-scoped insert so RLS's slots_write_owner enforces that the owner owns
    # the parent resource (existing-slot lookup above stays on the service key).
    created = get_user_client(owner.token).table("slots").insert(row).execute().data
    return enforce_rls_write(created, entity="slot")


@router.patch("/{slot_id}")
def update_slot(
    slot_id: str, payload: SlotUpdate, owner: AuthUser = Depends(require_owner)
):
    db = get_supabase()
    existing = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if existing is None:
        raise HTTPException(404, "Slot not found")

    patch = payload.model_dump(exclude_none=True)
    if "metadata" in patch:
        validate_metadata("slots", patch["metadata"])
    if not patch:
        return [existing]
    # User-scoped update so RLS enforces parent-resource ownership.
    updated = (
        get_user_client(owner.token).table("slots").update(patch).eq("id", slot_id).execute().data
    )
    return enforce_rls_write(updated, entity="slot")


@router.delete("/{slot_id}", status_code=204)
def delete_slot(slot_id: str, owner: AuthUser = Depends(require_owner)):
    db = get_supabase()
    existing = maybe_row(db.table("slots").select("*").eq("id", slot_id))
    if existing is None:
        raise HTTPException(404, "Slot not found")
    # User-scoped delete so RLS enforces parent-resource ownership; the schema
    # cascade removes dependent bookings. Delete returns the removed rows, so an
    # empty result means RLS refused.
    deleted = get_user_client(owner.token).table("slots").delete().eq("id", slot_id).execute().data
    enforce_rls_write(deleted, entity="slot")
    return Response(status_code=204)
