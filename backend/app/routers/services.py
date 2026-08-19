"""Service discovery (public reads). A service carries the per-service rules as
columns and its `resourceIds` as a derived link array."""
from fastapi import APIRouter, Depends, HTTPException, Response

from app import discovery
from app.auth import AuthUser, enforce_rls_write, require_owner
from app.db import get_supabase, get_user_client, maybe_row
from app.config import get_config
from app.config_schema import validate_overrides
from app.errors import NOT_FOUND, VALIDATION_ERROR, api_error
from app.meta import merged_metadata
from app.models import ServiceCreate, ServiceUpdate
from app.rules import OVERRIDABLE_BLOCKS
from app.routers.resources import delete_resources_for_services
from app.serialize import serialize_service

router = APIRouter(prefix="/services", tags=["services"])

# Service fields that don't have a column and instead ride in services.metadata.
# Kept in one place so create + update agree on the keys.
_META_FIELDS = ("image_url", "auto_approve")


def _service_metadata(base: dict | None = None, *, custom: dict | None = None, **fields) -> dict:
    """Merge the non-column service fields into metadata, dropping keys left
    unset (None) so a PATCH stays partial.

    `custom` is the client's `metaFields.services` data. It goes UNDER everything
    the engine owns — the `_META_FIELDS` keys and the `OVERRIDABLE_BLOCKS` config
    blocks — so a domain field can never shadow a config override; `config` stays
    the only way to declare one."""
    md = dict(base or {})
    md.update(
        merged_metadata("services", custom, reserved=_META_FIELDS + tuple(OVERRIDABLE_BLOCKS))
    )
    for key, value in fields.items():
        if value is not None:
            md[key] = value
    return md


def _config_overrides(config: dict | None) -> dict:
    """Validate a service's config overrides and return them as metadata blocks.

    The global config is validated at load; these were not, so until now a
    service could carry a `pricing` block the engine would happily use to quote
    real money. Rejected here rather than silently dropped at read time — a
    business that mistypes its own pricing should be told, not quietly billed at
    the platform default.
    """
    if not config:
        return {}
    unknown = sorted(set(config) - set(OVERRIDABLE_BLOCKS))
    if unknown:
        raise api_error(
            VALIDATION_ERROR,
            f"Unknown config block(s): {', '.join(unknown)}. "
            f"Overridable blocks are: {', '.join(OVERRIDABLE_BLOCKS)}.",
            status=422,
        )
    problems = validate_overrides(config, get_config())
    if problems:
        raise api_error(
            VALIDATION_ERROR,
            "This service's config overrides are not valid: " + "; ".join(problems),
            details={"problems": problems},
            status=422,
        )
    return dict(config)


def _owned_service(db, service_id: str, owner: AuthUser) -> dict:
    """Fetch a service and assert the caller owns its parent provider. 404 if the
    service is gone, 403 if the provider belongs to someone else. Used before a
    destructive delete so we never partially delete another owner's data."""
    service = maybe_row(db.table("services").select("*").eq("id", service_id))
    if service is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")
    provider = maybe_row(
        db.table("providers").select("owner_id").eq("id", service["provider_id"])
    )
    if not provider or provider.get("owner_id") != owner.id:
        raise HTTPException(403, "You can only manage your own services.")
    return service


@router.post("")
def create_service(payload: ServiceCreate, owner: AuthUser = Depends(require_owner)):
    """Create a service under a provider the owner owns (RLS services_write_own
    checks the parent provider's owner_id via the user client)."""
    row = {
        "provider_id": payload.provider_id,
        "name": payload.name,
        "description": payload.description,
        "booking_model": payload.booking_model,
        "slot_duration_minutes": payload.slot_duration_minutes,
        "min_slots_per_booking": payload.min_slots_per_booking,
        "max_slots_per_booking": payload.max_slots_per_booking,
        "price_minor_units": payload.price_minor_units,
        "currency": payload.currency,
        "cancellation_cutoff_hours": payload.cancellation_cutoff_hours,
        "metadata": _service_metadata(
            _config_overrides(payload.config),
            custom=payload.metadata,
            image_url=payload.image_url,
            auto_approve=payload.auto_approve,
        ),
    }
    created = get_user_client(owner.token).table("services").insert(row).execute().data
    created = enforce_rls_write(created, entity="service")
    return serialize_service(created[0])


@router.patch("/{service_id}")
def update_service(
    service_id: str, payload: ServiceUpdate, owner: AuthUser = Depends(require_owner)
):
    db = get_supabase()
    existing = maybe_row(db.table("services").select("*").eq("id", service_id))
    if existing is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")

    patch = payload.model_dump(exclude_none=True, by_alias=False)
    # image_url / auto_approve aren't columns — pull them out of the column patch
    # and merge into metadata instead (leaving the rest as real column updates).
    meta_patch = {k: patch.pop(k) for k in _META_FIELDS if k in patch}
    custom = patch.pop("metadata", None)
    # Config blocks replace wholesale per block (a partial deep-merge would make
    # it impossible to ever remove a key), but untouched blocks are preserved.
    overrides = _config_overrides(patch.pop("config", None))
    if meta_patch or overrides or custom:
        patch["metadata"] = {
            **_service_metadata(existing.get("metadata") or {}, custom=custom, **meta_patch),
            **overrides,
        }
    if not patch:
        return serialize_service(existing)

    updated = (
        get_user_client(owner.token).table("services").update(patch).eq("id", service_id).execute().data
    )
    updated = enforce_rls_write(updated, entity="service")
    res_by_svc = discovery.resource_ids_by_service(db)
    return discovery.build_service(updated[0], res_by_svc=res_by_svc)


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: str, owner: AuthUser = Depends(require_owner)):
    """Delete one of the owner's services. Its metadata-linked units are removed
    first (they don't FK-cascade); the service delete then removes the row (RLS
    services_write_own enforces ownership via the parent provider)."""
    db = get_supabase()
    _owned_service(db, service_id, owner)  # 404 missing / 403 not-yours
    uc = get_user_client(owner.token)
    delete_resources_for_services(uc, db, {service_id})
    deleted = uc.table("services").delete().eq("id", service_id).execute().data
    enforce_rls_write(deleted, entity="service")
    return Response(status_code=204)


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
