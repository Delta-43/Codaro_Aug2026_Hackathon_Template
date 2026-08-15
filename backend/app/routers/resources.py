from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthUser, enforce_rls_write, require_owner
from app.db import get_supabase, get_user_client, maybe_row
from app.meta import validate_metadata
from app.models import ResourceCreate, ResourceUpdate
from app.serialize import serialize_resource

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
def list_resources(service_id: str | None = None):
    """List resources as the frontend `Resource` shape. With `?service_id`,
    returns only that service's **active** resources (getResources); without it,
    returns all (owner/debug listing)."""
    rows = get_supabase().table("resources").select("*").execute().data or []
    out = [serialize_resource(r) for r in rows]
    if service_id:
        out = [r for r in out if r["serviceId"] == service_id and r["active"]]
    return out


@router.post("")
def create_resource(payload: ResourceCreate, owner: AuthUser = Depends(require_owner)):
    validate_metadata("resources", payload.metadata)
    # Stamp ownership in metadata (the schema is frozen — no owner column). This
    # is what the resources RLS policies key on, and it records who created it.
    metadata = {**payload.metadata, "owner_id": owner.id}
    row = {
        "name": payload.name,
        "description": payload.description,
        "metadata": metadata,
    }
    # User-scoped insert so RLS's resources_insert_owner (is_owner()) enforces.
    created = get_user_client(owner.token).table("resources").insert(row).execute().data
    return enforce_rls_write(created, entity="resource")


@router.get("/{resource_id}")
def get_resource(resource_id: str):
    resource = maybe_row(get_supabase().table("resources").select("*").eq("id", resource_id))
    if resource is None:
        raise HTTPException(404, "Resource not found")
    return serialize_resource(resource)


@router.patch("/{resource_id}")
def update_resource(
    resource_id: str, payload: ResourceUpdate, owner: AuthUser = Depends(require_owner)
):
    db = get_supabase()
    existing = maybe_row(db.table("resources").select("*").eq("id", resource_id))
    if existing is None:
        raise HTTPException(404, "Resource not found")

    patch = payload.model_dump(exclude_none=True)
    if "metadata" in patch:
        validate_metadata("resources", patch["metadata"])
    if not patch:
        return [existing]
    # User-scoped update so RLS's resources_modify_own (owner_id == auth.uid())
    # enforces that an owner edits only their own resources.
    updated = (
        get_user_client(owner.token).table("resources").update(patch).eq("id", resource_id).execute().data
    )
    return enforce_rls_write(updated, entity="resource")


@router.get("/{resource_id}/analytics")
def resource_analytics(resource_id: str, _owner: AuthUser = Depends(require_owner)):
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
