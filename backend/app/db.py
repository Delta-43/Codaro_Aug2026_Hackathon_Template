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
# Postgres "invalid input syntax" — a malformed uuid passed as an id. Every id
# column is a uuid, so a non-uuid lookup value simply matches no row: normalise
# it to "not found" (a clean 404) rather than a 500.
_INVALID_TEXT_CODE = "22P02"
_NOT_FOUND_CODES = {_NOT_FOUND_CODE, _INVALID_TEXT_CODE}

# Postgres "unique_violation" — an insert that duplicates a primary/unique key.
# Callers whose write is idempotent (follow, for one) swallow exactly this and
# nothing else: a blanket `except Exception` there reports success for an RLS
# denial or a dropped connection just as happily.
UNIQUE_VIOLATION_CODE = "23505"

# Postgres "insufficient_privilege" — the raising form of an RLS refusal (a
# WITH CHECK violation). The other form returns no rows; `enforce_rls_write`
# covers that one. Both should reach the caller as the same 403.
RLS_DENIED_CODE = "42501"


# PostgREST caps an unbounded select at 1000 rows and says nothing about it —
# no error, no truncation flag, just a short list. A busy service has far more
# slots than that, so `/slots` and `/slots/occupancy` were each returning a
# silent prefix, and because they truncate INDEPENDENTLY a client joining them
# saw slots with no matching occupancy row and concluded the calendar was
# fragmented. Anything that must return a COMPLETE set goes through this.
_PAGE = 1000


def fetch_all(query, page: int = _PAGE) -> list[dict]:
    """Every row a query matches, paging past PostgREST's implicit 1000 cap.

    Stops on the first short page, so a result that fits in one page costs
    exactly one round trip — the common case is unchanged.
    """
    out: list[dict] = []
    start = 0
    while True:
        rows = query.range(start, start + page - 1).execute().data or []
        out.extend(rows)
        if len(rows) < page:
            return out
        start += page


def maybe_row(query):
    """Fetch a single row, returning ``None`` when nothing matches.

    Real PostgREST raises ``PGRST116`` from ``.single()`` on zero rows, and a
    strict client can surface the same from ``.maybe_single()``. Prefer
    ``.maybe_single()`` and treat that (and a malformed-uuid ``22P02``) as "no
    row" so the router's ``if x is None -> 404`` branch is actually reachable in
    production. ``query`` is the builder up to (but not including) the
    single-row terminator."""
    try:
        response = query.maybe_single().execute()
    except Exception as exc:  # noqa: BLE001 - re-raised unless it's a not-found code
        if getattr(exc, "code", None) in _NOT_FOUND_CODES:
            return None
        raise
    # supabase-py is inconsistent across versions on "no row": it may raise
    # PGRST116 (handled above), return a response with data=None, or return
    # None outright. Normalise all of them to None.
    return response.data if response is not None else None
