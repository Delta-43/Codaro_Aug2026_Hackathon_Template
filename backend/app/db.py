"""Supabase client + optional direct Postgres connection for schema setup."""
import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase() -> Client:
    """Service-key client. **Bypasses RLS** — use for cross-user / system work
    (capacity aggregation, analytics, seeding, schema, resolving a user's role
    from `profiles`). For user-owned reads/writes use `get_user_client` so RLS
    applies."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_user_client(token: str) -> Client:
    """A per-request client that carries the **user's** JWT, so PostgREST runs
    the query as that user and Row Level Security (supabase/schema.sql) applies.

    Built with the anon key (like a browser would) and then re-pointed at the
    user's token; the anon `apikey` stays, `Authorization` becomes the user
    bearer — exactly what Supabase expects for an RLS-scoped request. Not cached:
    the token is per-user and expires, and sharing one client across threads
    would race on its Authorization header."""
    url = os.environ["SUPABASE_URL"]
    anon = os.environ["SUPABASE_ANON_KEY"]
    client = create_client(url, anon)
    client.postgrest.auth(token)
    return client


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
