# backend/ — FastAPI booking engine

## Role

Generic booking engine API. Owns: reading the pivot file, the data-driven
rules engine, and the `/resources` `/slots` `/bookings` (+ `/slots/occupancy`)
routers. See root [CLAUDE.md](../CLAUDE.md) for the overall architecture and
[supabase/CLAUDE.md](../supabase/CLAUDE.md) for the schema this talks to.

## Files

| File | Responsibility |
|------|-----------------|
| `app/main.py` | App wiring, startup (schema setup + seed), `GET /health`, `GET /config` |
| `app/config.py` | Loads + `lru_cache`s `domain.config.json` |
| `app/db.py` | Supabase client + optional direct Postgres URL for schema/seed scripts; `maybe_row()` not-found guard for single-row lookups |
| `app/schema_setup.py` | Idempotently applies `supabase/schema.sql` on startup (guarded — never crashes the server) |
| `app/rules.py` | Data-driven rules engine — event-keyed registry of validators (see below) |
| `app/models.py` | Pydantic models for the neutral request envelope (see Validation) |
| `app/meta.py` | Config-driven `metaFields` validator (see Validation) |
| `app/routers/resources.py`, `slots.py`, `bookings.py` | REST endpoints (client + owner API) |
| `seed.py` | Domain-aware demo data; `seed_if_empty()` runs on startup only when `resources` is empty |
| `reseed.py` | Truncates + reseeds — destructive, run manually after a pivot |

## Conventions

- **Nothing hard-codes a domain term or a magic number.** Pull vocabulary
  and limits from `get_config()`, never a literal string like `"Doctor"` or
  a bare number like `24` for the cancellation window.
- **New domain data → `metadata jsonb`,** never a new column/migration.
  `supabase/schema.sql` is frozen at pivot time.
- **A new business rule = one config key in `domain.config.json` + one
  small validator in `rules.py`.** Don't scatter rule logic across routers.
- **Users have no passwords.** Identify/track by `client_email` /
  `client_id` only.
- **`bookings.history` is append-only** — every status change appends an
  entry, never overwrites the array.
- **Single-row lookups go through `db.maybe_row()`,** not a bare
  `.single()`/`.maybe_single()`: real PostgREST is inconsistent on zero rows
  (raises `PGRST116`, returns a null-data response, or returns `None`
  outright depending on version), and `maybe_row` normalises all three to
  `None` so the `404` branch is actually reachable.
- **Rule-violation messages interpolate config `terms`** (e.g.
  `f"This {terms['slot'].lower()} is fully booked."`) so error copy pivots
  with the domain. The frontend renders `detail` verbatim.
- **Startup uses FastAPI lifespan, not `@app.on_event`** — and the lifespan
  body must call `create_tables_if_configured` / `seed_if_empty` through
  their module-level names (`test/backend/conftest.py` monkeypatches them
  on the `main` module).
- **`POST /config/reload`** (`clear_config_cache()` then return fresh
  config) is the intended instant-pivot mechanism; `make reload`
  (container restart) is the fallback.

## Rules engine (`rules.py`)

The registry maps *event* → *config key* → *validator*:

```python
RULES = {
    "booking.create": {"maxBookingsPerSlot": _capacity,
                       "advanceBookingWindowDays": _advance_window},
    "booking.change": {"cancellationWindowHours": _cancellation_window},
    "slot.create":    {"bufferMinutes": _buffer},
}

def apply_rules(event: str, ctx: dict) -> None:
    configured = get_config().get("rules", {})
    for key, validator in RULES.get(event, {}).items():
        if configured.get(key) is not None:
            validator(configured[key], ctx)
```

- Routers call `apply_rules(event, ctx)` — never a validator directly.
- Absent/unknown config keys are **skipped gracefully**: deleting a key
  from `domain.config.json` disables the rule; no code change. This is the
  pivot story.
- Adding a rule = one config key + one ~4-line validator + one registry
  entry. Nothing else.
- Keep `check_cancellation_window` / `check_capacity` as thin wrappers over
  their validators — tests and `bookings.py` import them by name.
- Parse all timestamps through a shared `parse_ts()` helper:
  `datetime.fromisoformat`, apply UTC when the string is naive. Never
  compare naive to aware datetimes.
- All five rule keys are wired: `maxBookingsPerSlot` / `cancellationWindowHours`
  (capacity + window), `advanceBookingWindowDays` (booking.create — slot must
  start within N days), `bufferMinutes` (slot.create — reject a slot
  overlapping another of the same resource once padded by the buffer), and
  `slotDurationMinutes` (derives a slot's `ends_at`).

## Validation

- **Pydantic envelope, explicit inserts.** `models.py` types only the
  neutral envelope (`name`, `starts_at`, `client_email`, `capacity`, …)
  plus `metadata: dict = {}`. Routers build insert rows explicitly from
  model fields — **never spread `**payload` into an insert** (arbitrary-key
  injection, `KeyError` 500s).
- **`metadata` is validated separately** by `meta.py`, built from
  `get_config()["metaFields"][entity]` *at request time* so a pivot needs
  no code change. Lenient on undeclared keys (the `metadata jsonb` column
  is the extension point); strict on declared keys — wrong type → 422 with
  `{field, label, expected}` detail. Honor an optional `"required": true`
  per field. Type map: `text → str`, `number → int|float`,
  `boolean → bool`; unknown types pass through.
- No dynamic Pydantic model generation for metadata — a plain validator is
  simpler and equally config-driven.
- `POST /slots` derives `ends_at = starts_at + rules.slotDurationMinutes`
  when absent, and defaults `capacity` from `rules.maxBookingsPerSlot`
  (same as `seed.py` — no magic literals).

## Owner API (term-neutral, no auth)

The owner/client split is a UI concern (`terms.admin` labels it); the
backend takes an `actor` flag, never credentials:

- `PATCH /resources/{id}` — partial update (`model_dump(exclude_none=True)`);
  validate `metadata` if present.
- `PATCH /slots/{id}`, `DELETE /slots/{id}` — schema cascade removes
  dependent bookings; return 204 on delete.
- `POST /bookings/{id}/confirm` — set status + append
  `{"status": "confirmed", "at": ..., "actor": "owner"}` to `history`.
- Owner cancel — same `POST /bookings/{id}/cancel` endpoint with optional
  body `{"actor": "owner"}`: skips the cancellation-window rule (the window
  constrains clients; owners override) and records the actor in `history`.
  No body ⇒ client behavior, so the existing frontend call keeps working.
- `GET /bookings` without `client_email` already returns all; add an
  optional `status` query filter.
- `GET /resources/{id}/analytics` — computed in Python from
  `slot_occupancy` + a bookings query (schema stays frozen; no new SQL).
  Shape: `{total_slots, total_capacity, booked_count, available_count,
  occupancy_rate, bookings_by_status}` where `bookings_by_status` is
  aggregated from the rows (a `Counter`), never a hardcoded status list.

## Don't

- Touch `supabase/schema.sql` — frozen; analytics and aggregates are
  computed in Python, not new views.
- Add auth, passwords, JWTs, or role tables — `actor` flag +
  `client_email` only.
- Break the frontend contract in `frontend/lib/api.ts`: keep existing
  paths/params, keep POST endpoints returning PostgREST row **lists**;
  only add.
- Ship a config-driven `"pending"` default booking status — the
  `slot_occupancy` view only counts `confirmed`, so pending bookings would
  not hold capacity. Documented stretch goal only.

## Current state

The engine is complete and covered by `test/backend` (128 passing — run via
the 3-agent pipeline in the root `CLAUDE.md`; regenerate `TODO.md` there for
the authoritative gap list). What's implemented:

- **Validation:** `models.py` (Pydantic envelopes) + `meta.py` (config-driven
  `metaFields`). POST endpoints build inserts explicitly and reject bad
  payloads with `422` instead of DB 500s.
- **Rules engine:** the event-keyed registry above, with `parse_ts()` and all
  five rule keys wired (capacity, cancellation window, advance window,
  buffer; `slotDurationMinutes` derives `ends_at`).
- **Not-found handling:** `db.maybe_row()` makes every `404` branch reachable
  against real PostgREST.
- **Owner API:** `PATCH /resources/{id}`, `GET /resources/{id}/analytics`,
  `PATCH`/`DELETE /slots/{id}`, `POST /bookings/{id}/confirm`, a `status`
  filter on `GET /bookings`, and the `{"actor":"owner"}` cancel override —
  all no-auth (`actor` flag only).
- **Infra:** startup via FastAPI lifespan; `POST /config/reload` for the
  instant pivot.

Verified live against a real Supabase project (schema setup, `slot_occupancy`
view, cascade delete) in addition to the offline suite. The 13 formerly
`xfail`-marked tests now pass; the `test-writer` agent has since removed those
markers and added owner-endpoint coverage.

## Testing

Don't write tests in this directory. API tests live in `test/` and are
owned by the `test-writer` agent — see [test/CLAUDE.md](../test/CLAUDE.md)
and the pipeline described in the root `CLAUDE.md`. If you change an
endpoint's contract, note it so `test-writer`'s next pass picks it up.
