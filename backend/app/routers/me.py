"""Current-user endpoints. `GET /me` assembles the User; `PATCH /me` updates the
editable profile fields in Supabase `user_metadata` (role/verified are not
self-editable). `POST /me/avatar` / `DELETE /me/avatar` upload/remove the
profile picture (Supabase Storage `avatars` bucket, see supabase/schema.sql)
and write the resulting URL into the same `avatar_url` field. All return the
full User shape."""
import logging

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app import gdpr
from app.auth import AuthUser, require_user
from app.avatars import remove_avatar, store_avatar
from app.config import get_config
from app.db import get_supabase, get_user_client
from app.models import UserPatch
from app.serialize import iso_utc
from app.rules import capability, resolve_entitlement
from app.serialize import serialize_entitlement, serialize_user
from app.users import apply_user_attrs, followed_ids, load_user, user_metadata

logger = logging.getLogger(__name__)
router = APIRouter(tags=["me"])

_EDITABLE = ("display_name", "timezone", "avatar_url")


@router.get("/me")
def get_me(user: AuthUser = Depends(require_user)):
    return load_user(user)


@router.get("/me/role")
def get_my_role(user: AuthUser = Depends(require_user)):
    """The caller's **trusted** engine role, resolved from `profiles` — the same
    value `require_owner` gates on.

    The frontend used to derive this from the JWT's `user_metadata.role`, which
    the user can write themselves (`supabase.auth.updateUser`). That made the two
    sides disagree in both directions: a customer who set the claim saw the whole
    business UI while every call inside it 403'd, and an admin promoting someone
    the documented way (UPDATE `profiles.role`) got backend access the UI kept
    hiding. Serving the resolved role from here makes `profiles` the single
    source of truth for both.

    Deliberately lean and separate from `GET /me`: this runs on every page load
    to decide which app to render, and the User shape stays a profile shape, not
    an authorization one. `require_user` has already resolved the role (cached
    for a few seconds per user), so this costs no extra query.
    """
    return {"role": user.role}


@router.delete("/me", status_code=204)
def delete_me(user: AuthUser = Depends(require_user)):
    """GDPR right to erasure — permanently remove every record tied to the
    signed-in user and delete their auth account. Idempotent (a repeat call is a
    no-op). Runs the erasure with the service key; see `app.gdpr.erase_user`."""
    gdpr.erase_user(get_supabase(), user)
    return Response(status_code=204)


@router.get("/me/entitlements")
def my_entitlements(user: AuthUser = Depends(require_user)):
    """What this customer holds, and what the deployment sells.

    `plans` comes from `domain.config.json` (`entitlements.plans[]`) — the
    catalogue — and `held` from the `entitlements` table. Returning both in one
    response lets the UI say "you are a Member" or "become a Member for X"
    without a second round trip and without the client knowing the config shape.

    Read through an RLS-scoped client, so a customer can only ever see their own
    rows even if the filter below were wrong.
    """
    cfg = get_config()["entitlements"]
    if not cfg.get("enabled") or not capability("entitlements"):
        # Capability off: an empty catalogue, not a 404. The UI hides the surface
        # on `plans` being empty, and a deployment turning entitlements off
        # mid-flight should degrade quietly rather than error.
        return {"enabled": False, "kind": "none", "plans": [], "held": []}

    try:
        rows = (
            get_user_client(user.token).table("entitlements").select("*")
            .eq("user_id", user.id).order("created_at", desc=True).execute().data
            or []
        )
    except Exception:
        logger.exception("Could not load entitlements for %s", user.id)
        rows = []

    return {
        "enabled": True,
        "kind": cfg.get("kind") or "none",
        "plans": [
            {
                "key": p.get("key"),
                "label": p.get("label") or p.get("key"),
                "priceMinorUnits": p.get("priceMinorUnits"),
                "cycle": p.get("cycle") or "none",
                "credits": p.get("credits"),
                "discountBps": int(p.get("discountBps") or 0),
            }
            for p in (cfg.get("plans") or [])
            if isinstance(p, dict) and p.get("key")
        ],
        "held": [serialize_entitlement(r) for r in rows],
        # The one that would price a booking right now, so the UI does not have
        # to reimplement the selection rules (active window, credits left,
        # largest discount wins).
        "active": (lambda e: None if e is None else serialize_entitlement(e["row"]))(
            resolve_entitlement(rows)
        ),
    }


@router.get("/me/reputation")
def my_reputation(user: AuthUser = Depends(require_user)):
    """The signed-in customer's reputation as businesses see it: the pooled
    rating and the reviews providers left after completed bookings. Read via the
    service key (system aggregation over the user's own client_reviews)."""
    db = get_supabase()
    try:
        rows = db.table("client_reviews").select("*").eq("client_id", user.id).execute().data or []
    except Exception:
        rows = []  # table not present yet (e.g. offline) — empty reputation
    provider_ids = list({r["provider_id"] for r in rows if r.get("provider_id")})
    names: dict[str, str] = {}
    if provider_ids:
        provs = db.table("providers").select("id,name").in_("id", provider_ids).execute().data or []
        names = {p["id"]: p["name"] for p in provs}

    reviews = [
        {
            "author": names.get(r.get("provider_id"), "A business"),
            "rating": int(r["rating"]),
            "text": r.get("text") or "",
            "createdAtUtc": iso_utc(r.get("created_at")),
        }
        for r in rows
    ]
    reviews.sort(key=lambda x: x["createdAtUtc"] or "", reverse=True)
    count = len(reviews)
    score = round(sum(r["rating"] for r in reviews) / count, 1) if count else 0.0
    return {"score": score, "count": count, "reviews": reviews}


@router.patch("/me")
def patch_me(payload: UserPatch, user: AuthUser = Depends(require_user)):
    patch = payload.model_dump(exclude_none=True)
    md = user_metadata(user)
    for key in _EDITABLE:
        if key in patch:
            md[key] = patch[key]

    attrs: dict = {"user_metadata": md}
    if "email" in patch:
        attrs["email"] = patch["email"]
    apply_user_attrs(user.id, attrs)

    return serialize_user(
        id=user.id,
        email=patch.get("email", user.email),
        metadata=md,
        followed_provider_ids=followed_ids(user),
    )


def _avatar_key(user_id: str) -> str:
    return f"{user_id}/avatar"


def _write_avatar_url(user: AuthUser, avatar_url: str) -> dict:
    md = user_metadata(user)
    md["avatar_url"] = avatar_url
    apply_user_attrs(user.id, {"user_metadata": md})
    return md


@router.post("/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: AuthUser = Depends(require_user)):
    avatar_url = await store_avatar(file, _avatar_key(user.id))
    md = _write_avatar_url(user, avatar_url)
    return serialize_user(
        id=user.id, email=user.email, metadata=md, followed_provider_ids=followed_ids(user)
    )


@router.delete("/me/avatar")
def delete_avatar(user: AuthUser = Depends(require_user)):
    remove_avatar(_avatar_key(user.id))
    md = _write_avatar_url(user, "")
    return serialize_user(
        id=user.id, email=user.email, metadata=md, followed_provider_ids=followed_ids(user)
    )
