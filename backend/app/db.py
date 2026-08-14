"""Supabase client + optional direct Postgres connection for schema setup."""
import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_db_url() -> str | None:
    """Direct Postgres connection string, used only for schema setup/seeding
    (SUPABASE_DB_URL). Optional — if unset, schema.sql must be run manually."""
    return os.environ.get("SUPABASE_DB_URL")


# PostgREST error code for "JSON object requested, multiple (or no) rows".
_NOT_FOUND_CODE = "PGRST116"


def maybe_row(query):
    """Fetch a single row, returning ``None`` when nothing matches.

    Real PostgREST raises ``PGRST116`` from ``.single()`` on zero rows, and a
    strict client can surface the same from ``.maybe_single()``. Prefer
    ``.maybe_single()`` and treat that specific error as "no row" so the
    router's ``if x is None -> 404`` branch is actually reachable in
    production. ``query`` is the builder up to (but not including) the
    single-row terminator."""
    try:
        response = query.maybe_single().execute()
    except Exception as exc:  # noqa: BLE001 - re-raised unless it's the not-found code
        if getattr(exc, "code", None) == _NOT_FOUND_CODE:
            return None
        raise
    # supabase-py is inconsistent across versions on "no row": it may raise
    # PGRST116 (handled above), return a response with data=None, or return
    # None outright. Normalise all of them to None.
    return response.data if response is not None else None
