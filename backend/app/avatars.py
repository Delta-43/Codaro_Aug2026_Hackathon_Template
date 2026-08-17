"""Shared avatar-image handling for the public Supabase Storage `avatars`
bucket (see supabase/schema.sql). Used by both `/me/avatar` (the signed-in
user's own picture, keyed by user id) and `/providers/{id}/avatar` (a business
picture, keyed by provider id). Uploads/removes run with the service key; the
caller is responsible for authorising *which* key it may touch (derived from the
verified JWT / an owner check), never from client input.
"""
import uuid

from fastapi import UploadFile

from app.db import get_supabase
from app.errors import VALIDATION_ERROR, api_error

_BUCKET = "avatars"
# These MUST mirror the avatars bucket DDL in supabase/schema.sql
# (file_size_limit = 5242880 and allowed_mime_types). There is no shared source
# of truth across the SQL and Python layers, so changing one means changing the
# other — otherwise a file passes one check and is rejected by the other.
_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def store_avatar(file: UploadFile, key: str) -> str:
    """Validate `file`, upload its bytes to `key` in the avatars bucket, and
    return the public URL with a cache-busting `?v=` token (the object key is
    stable across re-uploads, so the query param forces browsers off the old
    bytes). Raises VALIDATION_ERROR on a bad type / empty / oversized image."""
    if file.content_type not in _ALLOWED_TYPES:
        raise api_error(VALIDATION_ERROR, "Unsupported image type. Use JPEG, PNG, or WEBP.")
    data = await file.read()
    if not data:
        raise api_error(VALIDATION_ERROR, "The uploaded file is empty.")
    if len(data) > _MAX_BYTES:
        raise api_error(VALIDATION_ERROR, "Image must be 5MB or smaller.")

    supabase = get_supabase()
    supabase.storage.from_(_BUCKET).upload(
        key, data, {"content-type": file.content_type, "upsert": "true"}
    )
    public_url = supabase.storage.from_(_BUCKET).get_public_url(key)
    # A unique token per upload (not a 1s-resolution timestamp), so even two
    # re-uploads within the same second produce distinct URLs.
    return f"{public_url.split('?')[0]}?v={uuid.uuid4().hex}"


def remove_avatar(key: str) -> None:
    """Best-effort delete of the object at `key` (no-op if it's already gone or
    storage is unavailable offline)."""
    try:
        get_supabase().storage.from_(_BUCKET).remove([key])
    except Exception:
        pass
