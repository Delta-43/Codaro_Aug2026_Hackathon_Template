"""Current-user endpoints. `GET /me` assembles the User; `PATCH /me` updates the
editable profile fields in Supabase `user_metadata` (role/verified are not
self-editable). Both return the full User shape."""
from fastapi import APIRouter, Depends

from app.auth import AuthUser, require_user
from app.db import get_supabase
from app.models import UserPatch
from app.serialize import iso_utc, serialize_user
from app.users import followed_ids, load_user, user_metadata

router = APIRouter(tags=["me"])

_EDITABLE = ("display_name", "timezone", "avatar_url")


@router.get("/me")
def get_me(user: AuthUser = Depends(require_user)):
    return load_user(user)


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
    try:
        get_supabase().auth.admin.update_user_by_id(user.id, attrs)
    except Exception:
        # Admin update unavailable (e.g. offline) — still reflect the change in
        # the response so the client's optimistic update holds for this session.
        pass

    return serialize_user(
        id=user.id,
        email=patch.get("email", user.email),
        metadata=md,
        followed_provider_ids=followed_ids(user),
    )
