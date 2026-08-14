from collections import Counter

from fastapi import APIRouter, HTTPException

from app.db import get_supabase, maybe_row
from app.meta import validate_metadata
from app.models import ResourceCreate, ResourceUpdate

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
def list_resources():
    return get_supabase().table("resources").select("*").execute().data


@router.post("")
def create_resource(payload: ResourceCreate):
    validate_metadata("resources", payload.metadata)
    row = {
        "name": payload.name,
        "description": payload.description,
        "metadata": payload.metadata,
    }
    return get_supabase().table("resources").insert(row).execute().data


@router.get("/{resource_id}")
def get_resource(resource_id: str):
    resource = maybe_row(get_supabase().table("resources").select("*").eq("id", resource_id))
    if resource is None:
        raise HTTPException(404, "Resource not found")
    return resource


@router.patch("/{resource_id}")
def update_resource(resource_id: str, payload: ResourceUpdate):
    db = get_supabase()
    existing = maybe_row(db.table("resources").select("*").eq("id", resource_id))
    if existing is None:
        raise HTTPException(404, "Resource not found")

    patch = payload.model_dump(exclude_none=True)
    if "metadata" in patch:
        validate_metadata("resources", patch["metadata"])
    if not patch:
        return [existing]
    return db.table("resources").update(patch).eq("id", resource_id).execute().data


@router.get("/{resource_id}/analytics")
def resource_analytics(resource_id: str):
    """Owner analytics, computed in Python from slot_occupancy + bookings —
    no new SQL/view (the schema stays frozen)."""
    db = get_supabase()
    if maybe_row(db.table("resources").select("id").eq("id", resource_id)) is None:
        raise HTTPException(404, "Resource not found")

    occupancy = (
        db.table("slot_occupancy").select("*").eq("resource_id", resource_id).execute().data
    )
    total_slots = len(occupancy)
    total_capacity = sum(row["capacity"] for row in occupancy)
    booked_count = sum(row["booked_count"] for row in occupancy)
    available_count = sum(row["available_count"] for row in occupancy)

    slot_ids = [row["slot_id"] for row in occupancy]
    bookings = (
        db.table("bookings").select("status").in_("slot_id", slot_ids).execute().data
        if slot_ids
        else []
    )
    bookings_by_status = Counter(row["status"] for row in bookings)

    return {
        "total_slots": total_slots,
        "total_capacity": total_capacity,
        "booked_count": booked_count,
        "available_count": available_count,
        "occupancy_rate": (booked_count / total_capacity) if total_capacity else 0.0,
        "bookings_by_status": dict(bookings_by_status),
    }
