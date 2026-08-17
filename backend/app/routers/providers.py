"""Provider discovery + follow/unfollow.

Public reads (search, by-id, by-code) go through the service key and are
personalised (followed-first ordering) only when a valid token is present.
Follow/unfollow require a user and write through the RLS-scoped client.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app import discovery
from app.auth import AuthUser, enforce_rls_write, optional_user, require_owner, require_user
from app.avatars import remove_avatar, store_avatar
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import NOT_FOUND, api_error
from app.models import ProviderCreate, ProviderUpdate
from app.routers.resources import delete_resources_for_services
from app.serialize import iso_utc, serialize_provider
from app.users import admin_user_metadata, followed_ids, load_user

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
    # Only the follow set is needed here — call followed_ids directly rather than
    # load_user, which would also hit the auth admin API for user_metadata we
    # never read (one wasted remote round trip on every signed-in search).
    followed: set[str] = set(followed_ids(user)) if user else set()
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


def _provider_avatar_key(provider_id: str) -> str:
    return f"provider/{provider_id}/avatar"


def _owned_provider(db, provider_id: str, owner: AuthUser) -> dict:
    """Fetch the provider, 404 if gone, 403 if it isn't the caller's."""
    existing = maybe_row(db.table("providers").select("*").eq("id", provider_id))
    if existing is None:
        raise api_error(NOT_FOUND, "That provider no longer exists.")
    if existing.get("owner_id") != owner.id:
        raise HTTPException(403, "You can only manage your own businesses.")
    return existing


def _write_provider_avatar(db, owner: AuthUser, existing: dict, avatar_url: str) -> dict:
    """Persist `avatar_url` into the provider's metadata (RLS-scoped write) and
    return the freshly built provider (rating/reviewCount blended, as PATCH does).
    Aggregates are scoped to this one provider — an avatar change doesn't need a
    repo-wide reviews/services scan."""
    md = {**(existing.get("metadata") or {}), "avatar_url": avatar_url}
    updated = (
        get_user_client(owner.token)
        .table("providers")
        .update({"metadata": md})
        .eq("id", existing["id"])
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="provider")
    row = updated[0]
    reviews = db.table("reviews").select("rating").eq("provider_id", row["id"]).execute().data or []
    services = db.table("services").select("id").eq("provider_id", row["id"]).execute().data or []
    return serialize_provider(
        row,
        service_ids=[s["id"] for s in services],
        review_sum=sum(float(r["rating"]) for r in reviews),
        review_count=len(reviews),
    )


@router.post("/{provider_id}/avatar")
async def upload_provider_avatar(
    provider_id: str, file: UploadFile = File(...), owner: AuthUser = Depends(require_owner)
):
    """Upload/replace a business's avatar (owner-gated, own-provider only). Stored
    in the avatars bucket keyed by provider id; the public URL lands in
    providers.metadata.avatar_url, so it shows on the business's cards/profile."""
    db = get_supabase()
    existing = _owned_provider(db, provider_id, owner)
    key = _provider_avatar_key(provider_id)
    avatar_url = await store_avatar(file, key)
    try:
        return _write_provider_avatar(db, owner, existing, avatar_url)
    except Exception:
        # The bytes are already in storage but metadata didn't get the new URL;
        # drop the just-uploaded object so it isn't orphaned.
        remove_avatar(key)
        raise


@router.delete("/{provider_id}/avatar")
def delete_provider_avatar(provider_id: str, owner: AuthUser = Depends(require_owner)):
    """Remove a business's avatar — deletes the object and clears
    metadata.avatar_url (falls back to initials on the cards/profile)."""
    db = get_supabase()
    existing = _owned_provider(db, provider_id, owner)
    remove_avatar(_provider_avatar_key(provider_id))
    return _write_provider_avatar(db, owner, existing, "")


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: str, owner: AuthUser = Depends(require_owner)):
    """Delete one of the owner's businesses. Order matters: its services'
    metadata-linked units are removed first (no FK cascade), then the provider
    delete cascades to services / follows / reviews via FK. RLS
    providers_write_own enforces that it's the caller's provider."""
    db = get_supabase()
    existing = maybe_row(db.table("providers").select("owner_id").eq("id", provider_id))
    if existing is None:
        raise api_error(NOT_FOUND, "That provider no longer exists.")
    if existing.get("owner_id") != owner.id:
        raise HTTPException(403, "You can only manage your own businesses.")

    uc = get_user_client(owner.token)
    service_ids = {
        s["id"]
        for s in db.table("services").select("id").eq("provider_id", provider_id).execute().data or []
    }
    delete_resources_for_services(uc, db, service_ids)
    deleted = uc.table("providers").delete().eq("id", provider_id).execute().data
    enforce_rls_write(deleted, entity="provider")
    return Response(status_code=204)


@router.get("/{provider_id}/reviews")
def provider_reviews(provider_id: str, limit: int = 8):
    """Recent reviews for a provider (public read) — powers the profile's Reviews
    section. Author is the reviewer's self-chosen public display name (never their
    private email); it falls back to "Guest" when unknown. Newest first."""
    db = get_supabase()
    rows = db.table("reviews").select("*").eq("provider_id", provider_id).execute().data or []
    # Newest first, then keep only the page we return — so the per-reviewer admin
    # lookups below are bounded by `limit`, not by the provider's whole review
    # history (a well-reviewed provider would otherwise fan out hundreds of
    # sequential admin round trips on every public request).
    rows.sort(key=lambda r: iso_utc(r.get("created_at")) or "", reverse=True)
    rows = rows[: max(0, limit)]

    booking_ids = [r["booking_id"] for r in rows if r.get("booking_id")]
    # Resolve each review's reviewer id from its booking, then that reviewer's
    # public display_name — GDPR: the private email is never exposed to a public
    # profile viewer. Best-effort; degrades to "Guest" if a lookup is unavailable.
    reviewer_by_booking: dict[str, str] = {}
    if booking_ids:
        brows = db.table("bookings").select("id,client_id").in_("id", booking_ids).execute().data or []
        reviewer_by_booking = {b["id"]: (b.get("client_id") or "") for b in brows}

    names: dict[str, str] = {}
    for client_id in {cid for cid in reviewer_by_booking.values() if cid}:
        md = admin_user_metadata(db, client_id)
        names[client_id] = md.get("display_name") or md.get("displayName") or ""

    def _author(row: dict) -> str:
        client_id = reviewer_by_booking.get(row.get("booking_id")) or ""
        return names.get(client_id) or "Guest"

    return [
        {
            "rating": int(r["rating"]),
            "text": r.get("text") or "",
            "createdAtUtc": iso_utc(r.get("created_at")),
            "author": _author(r),
        }
        for r in rows
    ]


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
