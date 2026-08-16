"""Provider discovery + follow/unfollow.

Public reads (search, by-id, by-code) go through the service key and are
personalised (followed-first ordering) only when a valid token is present.
Follow/unfollow require a user and write through the RLS-scoped client.
"""
from fastapi import APIRouter, Depends

from app import discovery
from app.auth import AuthUser, enforce_rls_write, optional_user, require_owner, require_user
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import NOT_FOUND, api_error
from app.models import ProviderCreate, ProviderUpdate
from app.serialize import serialize_provider
from app.users import load_user

router = APIRouter(prefix="/providers", tags=["providers"])


def _all_serialized(db) -> list[dict]:
    sums, counts = discovery.review_aggregates(db)
    svc = discovery.service_ids_by_provider(db)
    rows = db.table("providers").select("*").execute().data or []
    return [discovery.build_provider(r, svc_by_prov=svc, sums=sums, counts=counts) for r in rows]


@router.get("")
def search_providers(
    text: str | None = None,
    category_id: str | None = None,
    near: str | None = None,
    user: AuthUser | None = Depends(optional_user),
):
    """searchProviders — category exact, `near` substring on city, `text`
    substring over name+tagline+bio+city. Followed providers pin to the top,
    then rating desc (mirrors the mock)."""
    provs = _all_serialized(get_supabase())

    def match(p: dict) -> bool:
        if category_id and p["categoryId"] != category_id:
            return False
        if near and near.lower() not in (p["location"]["city"] or "").lower():
            return False
        if text:
            hay = f"{p['name']} {p['tagline']} {p['bio']} {p['location']['city']}".lower()
            if text.lower() not in hay:
                return False
        return True

    result = [p for p in provs if match(p)]
    followed: set[str] = set(load_user(user)["followedProviderIds"]) if user else set()
    result.sort(key=lambda p: (0 if p["id"] in followed else 1, -p["rating"]))
    return result


@router.get("/by-code/{code}")
def get_provider_by_code(code: str):
    """Resolve a provider by its public code (case-insensitive) — code entry / QR."""
    for p in _all_serialized(get_supabase()):
        if (p["publicCode"] or "").lower() == code.lower():
            return p
    raise api_error(NOT_FOUND, "No match for that code.")


def _provider_metadata(payload, base: dict | None = None) -> dict:
    """Assemble a provider's presentational metadata from a create/update body,
    dropping keys the body left unset (so PATCH is partial)."""
    md = dict(base or {})
    fields = {
        "avatar_url": payload.avatar_url,
        "cover_url": payload.cover_url,
        "tagline": payload.tagline,
        "bio": payload.bio,
        "location": payload.location,
        "links": payload.links,
    }
    for key, value in fields.items():
        if value is not None:
            md[key] = value
    return md


@router.get("/mine")
def my_providers(owner: AuthUser = Depends(require_owner)):
    """The signed-in owner's own providers (for the owner dashboard)."""
    db = get_supabase()
    rows = db.table("providers").select("*").eq("owner_id", owner.id).execute().data or []
    sums, counts = discovery.review_aggregates(db)
    svc = discovery.service_ids_by_provider(db)
    return [discovery.build_provider(r, svc_by_prov=svc, sums=sums, counts=counts) for r in rows]


@router.post("")
def create_provider(payload: ProviderCreate, owner: AuthUser = Depends(require_owner)):
    row = {
        "owner_id": owner.id,  # RLS providers_write_own checks owner_id == auth.uid()
        "name": payload.name,
        "public_code": payload.public_code,
        "category_id": payload.category_id,
        "metadata": _provider_metadata(payload),
    }
    created = get_user_client(owner.token).table("providers").insert(row).execute().data
    created = enforce_rls_write(created, entity="provider")
    return serialize_provider(created[0])


@router.patch("/{provider_id}")
def update_provider(
    provider_id: str, payload: ProviderUpdate, owner: AuthUser = Depends(require_owner)
):
    db = get_supabase()
    existing = maybe_row(db.table("providers").select("*").eq("id", provider_id))
    if existing is None:
        raise api_error(NOT_FOUND, "That provider no longer exists.")

    patch: dict = {}
    if payload.name is not None:
        patch["name"] = payload.name
    if payload.public_code is not None:
        patch["public_code"] = payload.public_code
    if payload.category_id is not None:
        patch["category_id"] = payload.category_id
    md = _provider_metadata(payload, existing.get("metadata") or {})
    if md != (existing.get("metadata") or {}):
        patch["metadata"] = md
    if not patch:
        return serialize_provider(existing)

    updated = (
        get_user_client(owner.token).table("providers").update(patch).eq("id", provider_id).execute().data
    )
    updated = enforce_rls_write(updated, entity="provider")
    sums, counts = discovery.review_aggregates(db)
    svc = discovery.service_ids_by_provider(db)
    return discovery.build_provider(updated[0], svc_by_prov=svc, sums=sums, counts=counts)


@router.get("/{provider_id}")
def get_provider(provider_id: str):
    db = get_supabase()
    row = maybe_row(db.table("providers").select("*").eq("id", provider_id))
    if row is None:
        raise api_error(NOT_FOUND, "That provider no longer exists.")
    sums, counts = discovery.review_aggregates(db)
    svc = discovery.service_ids_by_provider(db)
    return discovery.build_provider(row, svc_by_prov=svc, sums=sums, counts=counts)


@router.post("/{provider_id}/follow")
def follow_provider(provider_id: str, user: AuthUser = Depends(require_user)):
    if maybe_row(get_supabase().table("providers").select("id").eq("id", provider_id)) is None:
        raise api_error(NOT_FOUND, "That provider no longer exists.")
    try:
        get_user_client(user.token).table("follows").insert(
            {"user_id": user.id, "provider_id": provider_id}
        ).execute()
    except Exception:
        pass  # primary-key conflict → already following; follow is idempotent
    return load_user(user)


@router.post("/{provider_id}/unfollow")
def unfollow_provider(provider_id: str, user: AuthUser = Depends(require_user)):
    get_user_client(user.token).table("follows").delete().eq("user_id", user.id).eq(
        "provider_id", provider_id
    ).execute()
    return load_user(user)
