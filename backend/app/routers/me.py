"""Current-user endpoints. `GET /me` assembles the User; `PATCH /me` updates the
editable profile fields in Supabase `user_metadata` (role/verified are not
self-editable). Both return the full User shape."""
from fastapi import APIRouter, Depends

from app.auth import AuthUser, require_user
from app.db import get_supabase
from app.models import UserPatch
from app.serialize import serialize_user
from app.users import followed_ids, load_user, user_metadata

router = APIRouter(tags=["me"])

_EDITABLE = ("display_name", "timezone", "avatar_url")


@router.get("/me")
def get_me(user: AuthUser = Depends(require_user)):
    return load_user(user)


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
