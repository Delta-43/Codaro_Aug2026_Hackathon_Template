"""An in-memory stand-in for the Supabase (PostgREST) client.

CI has no Supabase project and no network, so the routers' database calls
are served by this fake. It implements exactly the fluent chain the backend
uses today::

    db.table("bookings").select("*").eq("id", x).single().execute().data
    db.table("bookings").insert(row).execute().data
    db.table("bookings").update(patch).eq("id", x).execute().data
    db.table("resources").select("id").limit(1).execute().data   # seed.py

Design notes / deliberate fidelity choices:

* ``slot_occupancy`` is a *derived view* (recomputed on every read from
  ``slots`` + ``bookings``), exactly like the SQL view in
  ``supabase/schema.sql``. That means capacity behaviour is genuinely
  exercised end to end: insert a booking and the occupancy the router reads
  changes, without any test-side bookkeeping.
* Column defaults mirror ``supabase/schema.sql`` (``status='confirmed'``,
  ``history='[]'``, ``metadata='{}'`` ...), so an insert that omits them
  behaves like the real table.
* Reads and writes deep-copy, so callers can never mutate the store by
  holding onto a returned row (PostgREST returns JSON, not references).

``strict_single`` toggles the one place where real PostgREST and the
backend's expectations disagree: with ``strict_single=False`` (default)
``.single()`` returns ``None`` for zero rows, which is what the routers
assume (``if slot is None: raise HTTPException(404, ...)``). With
``strict_single=True`` it raises like PostgREST's ``PGRST116``, which is what
a live Supabase actually does — used by the xfail tests that pin that gap.
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
}

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "resources": ("name",),
    "slots": ("resource_id", "starts_at", "ends_at"),
    "bookings": ("slot_id", "client_email"),
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
        self._order: tuple[str, bool] | None = None

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

    def limit(self, count: int) -> "_Query":
        self._limit = count
        return self

    def order(self, column: str, desc: bool = False) -> "_Query":
        self._order = (column, desc)
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
            actual = row.get(column)
            if kind == "eq" and actual != value:
                return False
            if kind == "neq" and actual == value:
                return False
            if kind == "in" and actual not in value:
                return False
        return True

    def _project(self, row: dict) -> dict:
        if self._columns.strip() == "*":
            return copy.deepcopy(row)
        wanted = [c.strip() for c in self._columns.split(",") if c.strip()]
        return {c: copy.deepcopy(row.get(c)) for c in wanted}

    def _run_select(self):
        rows = [self._project(r) for r in self._db.rows(self._table) if self._matches(r)]
        if self._order:
            column, desc = self._order
            rows.sort(key=lambda r: r.get(column), reverse=desc)
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
            row = {
                "id": str(uuid.uuid4()),
                "created_at": _now_iso(),
                **copy.deepcopy(TABLE_DEFAULTS.get(self._table, {})),
                **copy.deepcopy(payload),
            }
            self._db.tables[self._table].append(row)
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

    BASE_TABLES = ("resources", "slots", "bookings")

    def __init__(self, strict_single: bool = False):
        self.tables: dict[str, list[dict]] = {name: [] for name in self.BASE_TABLES}
        self.strict_single = strict_single
        self.calls: list[tuple[str, str]] = []

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

    # -- views (mirror supabase/schema.sql) ---------------------------
    def _slot_occupancy(self) -> list[dict]:
        rows = []
        for slot in self.tables["slots"]:
            booked = sum(
                1
                for b in self.tables["bookings"]
                if b.get("slot_id") == slot["id"] and b.get("status") == "confirmed"
            )
            capacity = slot.get("capacity", 1)
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
