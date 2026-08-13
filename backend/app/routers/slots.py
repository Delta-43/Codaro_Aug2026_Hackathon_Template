from fastapi import APIRouter

from app.db import get_supabase

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
def create_slot(payload: dict):
    # TODO: derive ends_at from starts_at + rules.slotDurationMinutes when
    # not explicitly provided.
    return get_supabase().table("slots").insert(payload).execute().data
