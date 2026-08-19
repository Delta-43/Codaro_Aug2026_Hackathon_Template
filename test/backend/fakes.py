"""An in-memory stand-in for the Supabase (PostgREST) client.

CI has no Supabase project and no network, so the routers' database calls
are served by this fake. It implements the fluent chain the backend uses::

    db.table("bookings").select("*").eq("id", x).maybe_single().execute().data
    db.table("bookings").insert(row).execute().data
    db.table("bookings").update(patch).eq("id", x).execute().data
    db.table("slot_occupancy").select("*").in_("slot_id", ids).execute().data

Design notes / deliberate fidelity choices:

* The schema grew to `providers / services / resources / slots / bookings /
  booking_slots / reviews / follows / profiles`. All are modelled here.
* ``slot_occupancy`` is a *derived view*, recomputed on every read exactly like
  the SQL view in ``supabase/schema.sql``: it **sums party_size** across the
  ``confirmed`` bookings linked to each slot **via booking_slots**. That means
  multi-slot + shared-capacity party sizes are genuinely exercised — insert a
  booking (plus its booking_slots) and occupancy shifts with no test bookkeeping.
* Column defaults mirror ``supabase/schema.sql`` so an insert that omits them
  behaves like the real table.
* Reads and writes deep-copy, so callers can never mutate the store by holding a
  returned row (PostgREST returns JSON, not references).

``strict_single`` toggles the one place real PostgREST and the routers disagree:
with it off (default) ``.maybe_single()`` returns ``None`` for zero rows (what
``db.maybe_row`` normalises to); with it on it raises ``PGRST116`` like a live
project.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any


class FakeAPIError(Exception):
    """Mimics ``postgrest.exceptions.APIError`` closely enough for tests."""

    def __init__(self, message: str, code: str = "PGRST116") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _column_value(row: dict, column: str) -> Any:
    """Resolve a filter column to the row's value.

    Real PostgREST accepts jsonb arrow paths as filter columns (e.g.
    ``.in_("metadata->>provider_id", ids)``): ``->>`` extracts the value as
    text. Our stored jsonb values are already strings/uuids, so direct
    equality against the extracted value matches the live behaviour.
    """
    if "->" in column:
        value: Any = row
        for key in column.replace("->>", "->").split("->"):
            value = value.get(key) if isinstance(value, dict) else None
        return value
    return row.get(column)


# Column defaults per supabase/schema.sql.
TABLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "resources": {"description": None, "metadata": {}},
    "slots": {"capacity": 1, "metadata": {}},
    "bookings": {
        "client_id": None,
        "status": "confirmed",
        "history": [],
        "metadata": {},
    },
    "providers": {
        "owner_id": None,
        "public_code": None,
        "category_id": None,
        "metadata": {},
    },
    "services": {
        "description": None,
        "booking_model": "one_to_one",
        "slot_duration_minutes": 30,
        "min_slots_per_booking": 1,
        "max_slots_per_booking": 1,
        "price_minor_units": 0,
        "currency": "EUR",
        "cancellation_cutoff_hours": 24,
        "metadata": {},
    },
    "booking_slots": {},
    "reviews": {"text": None},
    "client_reviews": {"provider_id": None, "text": ""},
    "follows": {},
    "profiles": {"email": None, "role": "client"},
    # schema.sql defaults `starts_at` to now(); None behaves identically for
    # `rules.resolve_entitlement` ("no start" = already started), so tests
    # needn't fake a clock.
    "entitlements": {
        "provider_id": None,
        "status": "active",
        "credits_total": None,
        "credits_used": 0,
        "starts_at": None,
        "ends_at": None,
        "metadata": {},
    },
    "waitlist_entries": {
        "service_id": None,
        "resource_id": None,
        "party_size": 1,
        "status": "waiting",
        "booking_id": None,
    },
    "conversations": {
        "owner_id": None,
        "last_message_at": None,
        "last_message_preview": None,
        "metadata": {},
    },
    "messages": {
        "reply_to_id": None,
        "delivered_at": None,
        "read_at": None,
        "deleted_at": None,
        "metadata": {},
    },
}

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "resources": ("name",),
    "slots": ("resource_id", "starts_at", "ends_at"),
    "bookings": ("slot_id", "client_email"),
    "providers": ("name",),
    "services": ("provider_id", "name"),
    "booking_slots": ("booking_id", "slot_id"),
    "reviews": ("booking_id", "provider_id", "rating"),
    "client_reviews": ("booking_id", "client_id", "rating"),
    "follows": ("user_id", "provider_id"),
    "profiles": ("id",),
    "entitlements": ("user_id", "plan_key"),
    "waitlist_entries": ("slot_id", "user_id", "position"),
    "conversations": ("provider_id", "client_id"),
    "messages": ("conversation_id", "sender_id", "body"),
}

# Tables whose primary key is caller-supplied (composite join tables / profiles):
# a duplicate insert must raise a unique violation, exactly like Postgres, so the
# routers' idempotency (`follow` swallows the conflict) is genuinely exercised.
# `conversations` is here for its UNIQUE (provider_id, client_id) — same insert
# behaviour as a composite PK, which is what the find-or-create route relies on.
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "booking_slots": ("booking_id", "slot_id"),
    "follows": ("user_id", "provider_id"),
    "profiles": ("id",),
    "conversations": ("provider_id", "client_id"),
}


class _Query:
    def __init__(self, db: "FakeSupabase", table: str, op: str, payload: Any = None):
        self._db = db
        self._table = table
        self._op = op
        self._payload = payload
        self._columns = "*"
        self._filters: list[tuple[str, str, Any]] = []
        self._single = False
        self._limit: int | None = None
        self._range: tuple[int, int] | None = None
        # Accumulated like PostgREST's chained .order(): the FIRST call is the
        # primary sort key (db.fetch_all relies on that for its total order).
        self._orders: list[tuple[str, bool]] = []

    # -- builder -----------------------------------------------------
    def select(self, columns: str = "*") -> "_Query":
        self._columns = columns
        return self

    def eq(self, column: str, value: Any) -> "_Query":
        self._filters.append(("eq", column, value))
        return self

    def neq(self, column: str, value: Any) -> "_Query":
        self._filters.append(("neq", column, value))
        return self

    def in_(self, column: str, values: list) -> "_Query":
        self._filters.append(("in", column, list(values)))
        return self

    def is_(self, column: str, value) -> "_Query":
        """PostgREST's IS filter — the routers use it for `"null"`/`"not.null"`
        (soft-delete + read-receipt predicates on `messages`)."""
        self._filters.append(("is", column, value))
        return self

    def gte(self, column: str, value: Any) -> "_Query":
        self._filters.append(("gte", column, value))
        return self

    def gt(self, column: str, value: Any) -> "_Query":
        self._filters.append(("gt", column, value))
        return self

    def lte(self, column: str, value: Any) -> "_Query":
        self._filters.append(("lte", column, value))
        return self

    def lt(self, column: str, value: Any) -> "_Query":
        self._filters.append(("lt", column, value))
        return self

    def range(self, start: int, end: int) -> "_Query":
        """PostgREST's inclusive row range, as `db.fetch_all` uses it to page
        past the implicit 1000-row cap. Without this the fake raised
        AttributeError on every paged read."""
        self._range = (start, end)
        return self

    def limit(self, count: int) -> "_Query":
        self._limit = count
        return self

    def order(self, column: str, desc: bool = False) -> "_Query":
        self._orders.append((column, desc))
        return self

    def single(self) -> "_Query":
        self._single = True
        return self

    def maybe_single(self) -> "_Query":
        self._single = True
        return self

    # -- execution ---------------------------------------------------
    def execute(self) -> "FakeResponse":
        self._db.calls.append((self._op, self._table))
        handler = {
            "select": self._run_select,
            "insert": self._run_insert,
            "update": self._run_update,
            "delete": self._run_delete,
        }[self._op]
        return FakeResponse(handler())

    # -- internals ---------------------------------------------------
    def _matches(self, row: dict) -> bool:
        for kind, column, value in self._filters:
            actual = _column_value(row, column)
            if kind == "eq" and actual != value:
                return False
            if kind == "neq" and actual == value:
                return False
            if kind == "in" and actual not in value:
                return False
            if kind == "is":
                if value in (None, "null"):
                    if actual is not None:
                        return False
                elif value == "not.null":
                    if actual is None:
                        return False
                elif actual is not value:  # True / False
                    return False
            if kind in ("gte", "gt", "lte", "lt"):
                if actual is None:
                    return False
                if kind == "gte" and not (actual >= value):
                    return False
                if kind == "gt" and not (actual > value):
                    return False
                if kind == "lte" and not (actual <= value):
                    return False
                if kind == "lt" and not (actual < value):
                    return False
        return True

    def _project(self, row: dict) -> dict:
        if self._columns.strip() == "*":
            return copy.deepcopy(row)
        wanted = [c.strip() for c in self._columns.split(",") if c.strip()]
        return {c: copy.deepcopy(row.get(c)) for c in wanted}

    def _run_select(self):
        rows = [self._project(r) for r in self._db.rows(self._table) if self._matches(r)]
        # Multi-key sort: apply the keys last-to-first with stable sorts, so the
        # first .order() call is the primary key. Nulls sort last ascending /
        # first descending, like Postgres defaults.
        for column, desc in reversed(self._orders):
            rows.sort(
                key=lambda r, c=column: (r.get(c) is None, r.get(c)), reverse=desc
            )
        if self._range is not None:
            start, end = self._range
            rows = rows[start : end + 1]  # PostgREST's range is inclusive
        if self._limit is not None:
            rows = rows[: self._limit]
        if self._single:
            if not rows:
                if self._db.strict_single:
                    raise FakeAPIError(
                        "JSON object requested, multiple (or no) rows returned",
                        code="PGRST116",
                    )
                return None
            if len(rows) > 1:
                raise FakeAPIError(
                    f"single() matched {len(rows)} rows in {self._table}",
                    code="PGRST116",
                )
            return rows[0]
        return rows

    def _run_insert(self):
        self._db.assert_writable(self._table)
        payloads = self._payload if isinstance(self._payload, list) else [self._payload]
        inserted = []
        for payload in payloads:
            if not isinstance(payload, dict):
                raise FakeAPIError("insert payload must be an object", code="PGRST102")
            for column in REQUIRED_COLUMNS.get(self._table, ()):
                if payload.get(column) is None:
                    raise FakeAPIError(
                        f'null value in column "{column}" violates not-null constraint',
                        code="23502",
                    )
            pk = PRIMARY_KEYS.get(self._table)
            if pk and any(
                all(existing.get(c) == payload.get(c) for c in pk)
                for existing in self._db.tables[self._table]
            ):
                raise FakeAPIError(
                    f"duplicate key value violates unique constraint on {self._table}",
                    code="23505",
                )
            row = {
                "id": str(uuid.uuid4()),
                "created_at": _now_iso(),
                **copy.deepcopy(TABLE_DEFAULTS.get(self._table, {})),
                **copy.deepcopy(payload),
            }
            self._db.tables[self._table].append(row)
            self._db.after_insert(self._table, row)
            inserted.append(copy.deepcopy(row))
        return inserted

    def _run_update(self):
        self._db.assert_writable(self._table)
        updated = []
        for row in self._db.tables[self._table]:
            if self._matches(row):
                row.update(copy.deepcopy(self._payload))
                updated.append(copy.deepcopy(row))
        return updated

    def _run_delete(self):
        self._db.assert_writable(self._table)
        kept, removed = [], []
        for row in self._db.tables[self._table]:
            (removed if self._matches(row) else kept).append(row)
        self._db.tables[self._table] = kept
        self._db.cascade_delete(self._table, removed)
        return copy.deepcopy(removed)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FakeResponse({self.data!r})"


class _TableHandle:
    def __init__(self, db: "FakeSupabase", table: str):
        self._db = db
        self._table = table

    def select(self, columns: str = "*", **_kwargs) -> _Query:
        return _Query(self._db, self._table, "select").select(columns)

    def insert(self, payload, **_kwargs) -> _Query:
        return _Query(self._db, self._table, "insert", payload)

    def update(self, payload, **_kwargs) -> _Query:
        return _Query(self._db, self._table, "update", payload)

    def upsert(self, payload, **_kwargs) -> _Query:
        return _Query(self._db, self._table, "insert", payload)

    def delete(self, **_kwargs) -> _Query:
        return _Query(self._db, self._table, "delete")


class FakeSupabase:
    """Minimal in-memory replacement for ``supabase.Client``."""

    BASE_TABLES = (
        "resources",
        "slots",
        "bookings",
        "providers",
        "services",
        "booking_slots",
        "reviews",
        "client_reviews",
        "follows",
        "profiles",
        "entitlements",
        "waitlist_entries",
        "conversations",
        "messages",
    )

    def __init__(self, strict_single: bool = False):
        self.tables: dict[str, list[dict]] = {name: [] for name in self.BASE_TABLES}
        self.strict_single = strict_single
        self.calls: list[tuple[str, str]] = []
        # Minimal Supabase Auth admin surface. Empty by default, so every code
        # path that degrades when the admin API is unavailable (owner screening,
        # review author names) keeps degrading exactly as before — only a test
        # that calls `seed_auth_user()` makes a user resolvable.
        self.auth_users: dict[str, dict] = {}
        self.auth = _FakeAuth(self)

    # -- client surface ----------------------------------------------
    def table(self, name: str) -> _TableHandle:
        if name not in self.tables and name not in self.VIEWS:
            raise FakeAPIError(
                f"Could not find the table 'public.{name}' in the schema cache",
                code="PGRST205",
            )
        return _TableHandle(self, name)

    from_ = table  # supabase-py exposes both .table() and .from_()

    # -- storage ------------------------------------------------------
    def rows(self, name: str) -> list[dict]:
        if name in self.VIEWS:
            return self.VIEWS[name](self)
        return self.tables[name]

    def assert_writable(self, name: str) -> None:
        if name in self.VIEWS:
            raise FakeAPIError(f"cannot write to view {name}", code="42809")

    # -- referential integrity (mirror `on delete cascade` in schema.sql) --
    # A parent may cascade to several children: (child_table, parent_key, child_key).
    _CASCADES: dict[str, tuple[tuple[str, str, str], ...]] = {
        "resources": (
            ("slots", "id", "resource_id"),
            ("waitlist_entries", "id", "resource_id"),
        ),
        "slots": (
            ("bookings", "id", "slot_id"),
            ("booking_slots", "id", "slot_id"),
            ("waitlist_entries", "id", "slot_id"),
        ),
        "bookings": (
            ("booking_slots", "id", "booking_id"),
            ("reviews", "id", "booking_id"),
            ("client_reviews", "id", "booking_id"),
            # waitlist_entries.booking_id is ON DELETE SET NULL, not cascade —
            # deliberately not modelled here (this map only deletes).
        ),
        "providers": (
            ("services", "id", "provider_id"),
            ("reviews", "id", "provider_id"),
            ("client_reviews", "id", "provider_id"),
            ("follows", "id", "provider_id"),
            ("entitlements", "id", "provider_id"),
            ("conversations", "id", "provider_id"),
        ),
        "services": (("waitlist_entries", "id", "service_id"),),
        "conversations": (("messages", "id", "conversation_id"),),
    }

    def cascade_delete(self, table: str, removed_rows: list[dict]) -> None:
        rules = self._CASCADES.get(table)
        if not rules or not removed_rows:
            return
        for child_table, parent_key, child_key in rules:
            removed_ids = {row.get(parent_key) for row in removed_rows}
            kept, orphaned = [], []
            for row in self.tables[child_table]:
                (orphaned if row.get(child_key) in removed_ids else kept).append(row)
            self.tables[child_table] = kept
            self.cascade_delete(child_table, orphaned)

    # -- views (mirror supabase/schema.sql) ---------------------------
    def _slot_occupancy(self) -> list[dict]:
        # Confirmed bookings by id, with their party size (default 1).
        confirmed: dict[str, int] = {}
        for b in self.tables["bookings"]:
            if b.get("status") == "confirmed":
                confirmed[b["id"]] = int((b.get("metadata") or {}).get("party_size", 1) or 1)
        # slot_id -> summed party size across confirmed bookings linked via booking_slots.
        booked_by_slot: dict[str, int] = {}
        for bs in self.tables["booking_slots"]:
            party = confirmed.get(bs.get("booking_id"))
            if party is not None:
                booked_by_slot[bs["slot_id"]] = booked_by_slot.get(bs["slot_id"], 0) + party
        rows = []
        for slot in self.tables["slots"]:
            capacity = slot.get("capacity", 1)
            booked = booked_by_slot.get(slot["id"], 0)
            rows.append(
                {
                    "slot_id": slot["id"],
                    "resource_id": slot.get("resource_id"),
                    "starts_at": slot.get("starts_at"),
                    "ends_at": slot.get("ends_at"),
                    "capacity": capacity,
                    "booked_count": booked,
                    "available_count": capacity - booked,
                }
            )
        return rows

    VIEWS = {"slot_occupancy": _slot_occupancy}

    # -- triggers (mirror supabase/schema.sql) -------------------------
    def after_insert(self, table: str, row: dict) -> None:
        """Mirror the `on_message_insert` trigger: stamp the parent thread's
        inbox preview/timestamp on every new message, so the inbox can list
        threads without scanning messages — exactly like the SQL trigger."""
        if table != "messages":
            return
        for conv in self.tables["conversations"]:
            if conv["id"] == row.get("conversation_id"):
                conv["last_message_at"] = row.get("created_at")
                conv["last_message_preview"] = row.get("body")

    # -- test helpers -------------------------------------------------
    def insert_row(self, table: str, **row) -> dict:
        """Seed a row directly, bypassing the API (returns the stored row)."""
        return _Query(self, table, "insert", row).execute().data[0]

    def get_row(self, table: str, row_id: str) -> dict | None:
        for row in self.rows(table):
            if row.get("id") == row_id:
                return copy.deepcopy(row)
        return None

    def count(self, table: str) -> int:
        return len(self.rows(table))

    def seed_auth_user(
        self, user_id: str, *, email: str, user_metadata: dict | None = None
    ) -> None:
        """Make `auth.admin.get_user_by_id(user_id)` resolve (email/display
        name), like a provisioned Supabase Auth user. Unknown ids keep raising,
        so the degrade paths other tests pin remain untouched."""
        self.auth_users[user_id] = {
            "email": email,
            "user_metadata": dict(user_metadata or {}),
            "created_at": _now_iso(),
        }


# --- Supabase Auth admin stub ----------------------------------------------
#
# Just enough of `client.auth.admin` for the routers that resolve emails /
# display names cross-user (waitlist promotion, messaging). Unknown users raise
# (like the real GoTrue admin API), so every best-effort caller still falls into
# its documented fallback when nothing was seeded.


class _FakeAuthAdmin:
    def __init__(self, db: "FakeSupabase") -> None:
        self._db = db

    def _get(self, user_id: str) -> dict:
        info = self._db.auth_users.get(user_id)
        if info is None:
            raise FakeAPIError(f"User not found: {user_id}", code="user_not_found")
        return info

    def get_user_by_id(self, user_id: str):
        info = self._get(user_id)
        user = _AuthUserObj(
            id=user_id,
            email=info.get("email"),
            user_metadata=copy.deepcopy(info.get("user_metadata") or {}),
            created_at=info.get("created_at"),
        )
        return _AuthResponse(user=user)

    def update_user_by_id(self, user_id: str, attrs: dict):
        info = self._get(user_id)
        if "email" in attrs:
            info["email"] = attrs["email"]
        if "user_metadata" in attrs:
            info["user_metadata"] = {
                **(info.get("user_metadata") or {}),
                **(attrs["user_metadata"] or {}),
            }
        return self.get_user_by_id(user_id)

    def delete_user(self, user_id: str) -> None:
        self._get(user_id)
        del self._db.auth_users[user_id]


class _FakeAuth:
    def __init__(self, db: "FakeSupabase") -> None:
        self.admin = _FakeAuthAdmin(db)


class _AuthUserObj:
    def __init__(self, **attrs) -> None:
        self.__dict__.update(attrs)


class _AuthResponse:
    def __init__(self, user) -> None:
        self.user = user
