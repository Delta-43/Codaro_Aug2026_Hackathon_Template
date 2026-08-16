"""Current-user endpoints. `GET /me` assembles the User; `PATCH /me` updates the
editable profile fields in Supabase `user_metadata` (role/verified are not
self-editable). `POST /me/avatar` / `DELETE /me/avatar` upload/remove the
profile picture (Supabase Storage `avatars` bucket, see supabase/schema.sql)
and write the resulting URL into the same `avatar_url` field. All return the
full User shape."""
import time

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import AuthUser, require_user
from app.db import get_supabase
from app.errors import VALIDATION_ERROR, api_error
from app.models import UserPatch
from app.serialize import serialize_user
from app.users import apply_user_attrs, followed_ids, load_user, user_metadata

router = APIRouter(tags=["me"])

_EDITABLE = ("display_name", "timezone", "avatar_url")

_AVATAR_BUCKET = "avatars"
_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


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
    if file.content_type not in _ALLOWED_AVATAR_TYPES:
        raise api_error(VALIDATION_ERROR, "Unsupported image type. Use JPEG, PNG, or WEBP.")
    data = await file.read()
    if not data:
        raise api_error(VALIDATION_ERROR, "The uploaded file is empty.")
    if len(data) > _MAX_AVATAR_BYTES:
        raise api_error(VALIDATION_ERROR, "Image must be 5MB or smaller.")

    key = _avatar_key(user.id)
    supabase = get_supabase()
    supabase.storage.from_(_AVATAR_BUCKET).upload(
        key, data, {"content-type": file.content_type, "upsert": "true"}
    )
    public_url = supabase.storage.from_(_AVATAR_BUCKET).get_public_url(key)
    # The object key never changes across re-uploads; cache-bust with a query
    # param so the browser doesn't keep serving the previous bytes.
    avatar_url = f"{public_url.split('?')[0]}?v={int(time.time())}"

    md = _write_avatar_url(user, avatar_url)
    return serialize_user(
        id=user.id, email=user.email, metadata=md, followed_provider_ids=followed_ids(user)
    )


@router.delete("/me/avatar")
def delete_avatar(user: AuthUser = Depends(require_user)):
    try:
        get_supabase().storage.from_(_AVATAR_BUCKET).remove([_avatar_key(user.id)])
    except Exception:
        pass  # nothing to delete, or storage unavailable offline

    md = _write_avatar_url(user, "")
    return serialize_user(
        id=user.id, email=user.email, metadata=md, followed_provider_ids=followed_ids(user)
    )
