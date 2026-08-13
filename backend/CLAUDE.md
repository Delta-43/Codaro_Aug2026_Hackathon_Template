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
| `app/db.py` | Supabase client + optional direct Postgres URL for schema/seed scripts |
| `app/schema_setup.py` | Idempotently applies `supabase/schema.sql` on startup (guarded — never crashes the server) |
| `app/rules.py` | Data-driven rules engine — one `rules.*` config key → one validator function |
| `app/routers/resources.py`, `slots.py`, `bookings.py` | REST endpoints |
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

## Current state / what's stubbed

The routers currently do direct Supabase calls with minimal validation.
Known gaps to close (check `TODO` comments in the router files, and prefer
regenerating `TODO.md` at repo root via the 3-agent pipeline for a current
list rather than trusting this paragraph):

- Request/response models aren't typed with Pydantic yet — payloads are
  raw `dict`.
- `metaFields` from `domain.config.json` aren't validated against
  `resources`/`bookings` payloads.
- `advanceBookingWindowDays` / `bufferMinutes` rules aren't enforced yet
  (`rules.py` has a TODO).
- No auth/authorization split between the "client" and "owner" (admin)
  views — every endpoint is currently open.

## Testing

Don't write tests in this directory. API tests live in `test/` and are
owned by the `test-writer` agent — see [test/CLAUDE.md](../test/CLAUDE.md)
and the pipeline described in the root `CLAUDE.md`. If you change an
endpoint's contract, note it so `test-writer`'s next pass picks it up.
