from fastapi import APIRouter

from app.db import get_supabase

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
def list_resources():
    return get_supabase().table("resources").select("*").execute().data


@router.post("")
def create_resource(payload: dict):
    # TODO: validate payload against domain.config.json metaFields.resources
    return get_supabase().table("resources").insert(payload).execute().data


@router.get("/{resource_id}")
def get_resource(resource_id: str):
    return (
        get_supabase()
        .table("resources")
        .select("*")
        .eq("id", resource_id)
        .single()
        .execute()
        .data
    )
