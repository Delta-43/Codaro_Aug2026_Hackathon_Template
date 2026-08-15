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
- **No custom password table.** Auth is **Supabase Auth** (added on branch
  `16-auth-system`): Supabase owns the `auth.users` table and password hashing,
  so never create a parallel users/passwords table here. Booking rows still key
  ownership by `client_email` / `client_id`, now populated from the verified
  auth user rather than trusted input. If you need per-user profile data (e.g.
  role), add a `profiles` table keyed by `auth.users.id`, kept idempotent like
  everything else.
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

With Supabase Auth on this branch, RLS becomes the enforcement layer for
per-user isolation: policies keyed on `auth.uid()` so a client sees/modifies
only their own bookings and an owner only their own resources. Add these here
(idempotent `drop policy if exists` + `create policy`) when auth is wired.
**Caveat:** the backend currently uses the Supabase **service key**, which
**bypasses RLS** — policies only bite for requests made with the user's token,
so coordinate with `backend/CLAUDE.md`'s **Auth** section on which reads carry
the user JWT. Not yet added — the schema still has no policies.

## Testing

This directory has no tests of its own — `slot_occupancy` correctness and
FK/constraint behavior should be covered by backend integration tests in
`test/` (see [test/CLAUDE.md](../test/CLAUDE.md)), since they require the
backend's Supabase client to exercise.
