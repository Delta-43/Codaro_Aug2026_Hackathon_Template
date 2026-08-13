# supabase/ — database schema

## Role

`schema.sql` defines the **neutral**, domain-agnostic tables that back the
booking engine: `resources`, `slots`, `bookings`, plus the `slot_occupancy`
view used for the availability grid. This is the only file in this
directory — the database itself is hosted Supabase (Postgres), not a local
container.

## Hard rules

- **Idempotent, always.** Only `create table if not exists`,
  `create index if not exists`, `create or replace view`. Never `DROP` or
  `ALTER` — the backend re-runs this file on every startup
  (`SUPABASE_DB_URL`), and existing data must survive that.
- **Treat as frozen once the event/pivot starts.** New domain-specific data
  goes into each table's `metadata jsonb` column, never a new migration or
  column. That's the whole point of the pivot design — see root
  [CLAUDE.md](../CLAUDE.md).
- **No password storage.** Users (clients) are identified by
  `client_email` / `client_id` only — there is no auth/password table.
- **`bookings.history`** is append-only jsonb: every status change
  (confirm/cancel/reschedule) should be pushed onto it, not overwrite it, so
  the full history survives.

## Current state

Base tables + `slot_occupancy` view exist (see `schema.sql`). No RLS
policies, no additional indexes beyond FK lookups. If per-owner data
isolation is needed, add Supabase RLS policies here — keep them additive
and idempotent (`drop policy if exists` + `create policy` is fine since
policies aren't covered by the "no DROP" rule, which is about table/column
structure, not policies).

## Testing

This directory has no tests of its own — `slot_occupancy` correctness and
FK/constraint behavior should be covered by backend integration tests in
`test/` (see [test/CLAUDE.md](../test/CLAUDE.md)), since they require the
backend's Supabase client to exercise.
