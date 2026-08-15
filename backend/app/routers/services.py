"""Service discovery (public reads). A service carries the per-service rules as
columns and its `resourceIds` as a derived link array."""
from fastapi import APIRouter

from app import discovery
from app.db import get_supabase, maybe_row
from app.errors import NOT_FOUND, api_error

router = APIRouter(prefix="/services", tags=["services"])


@router.get("")
def list_services(provider_id: str | None = None):
    db = get_supabase()
    res_by_svc = discovery.resource_ids_by_service(db)
    query = db.table("services").select("*")
    if provider_id:
        query = query.eq("provider_id", provider_id)
    rows = query.execute().data or []
    return [discovery.build_service(r, res_by_svc=res_by_svc) for r in rows]


@router.get("/{service_id}")
def get_service(service_id: str):
    db = get_supabase()
    row = maybe_row(db.table("services").select("*").eq("id", service_id))
    if row is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")
    res_by_svc = discovery.resource_ids_by_service(db)
    return discovery.build_service(row, res_by_svc=res_by_svc)
