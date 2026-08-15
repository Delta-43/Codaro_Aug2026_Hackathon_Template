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

Base tables + `slot_occupancy` view, **plus the auth layer** added on branch
`16-auth-system` (all in `schema.sql`, idempotent):

- **`profiles`** — 1:1 with `auth.users` (`id` FK, `on delete cascade`),
  holding the engine `role` (`'owner'|'client'`, default `client`). Not a
  password table (Supabase owns `auth.users`).
- **`handle_new_user()` trigger** on `auth.users` — auto-creates a profile on
  sign-up, copying `raw_user_meta_data->>'role'` (what the frontend sets in
  `user_metadata`). Wrapped in a guarded `DO` block: if the DB role lacks
  privilege on `auth.users` the trigger is skipped with a `notice` instead of
  rolling back the whole (single-transaction) file — populate `profiles`
  manually/via an admin in that case.
- **`public.is_owner()`** — `security definer` helper the policies use to check
  the caller's role from `profiles` without RLS recursion.
- **RLS enabled + policies** on `profiles`/`resources`/`slots`/`bookings`,
  keyed on `auth.uid()`:
  - `resources`/`slots`: public `select` (the landing page lists them for anon);
    write limited to the owner. Resource ownership is `metadata.owner_id` (schema
    frozen — no new column), stamped by the backend's `create_resource`; slot
    writes check the parent resource's owner.
  - `bookings`: a client sees/creates/updates only rows where
    `client_id = auth.uid()`; an owner sees/manages all.
  - `profiles`: a user reads only their own row; no API insert/update/delete, so
    a client can't self-promote to owner (only the trigger / service role / an
    admin write it).

Validated on a throwaway PG16 cluster (idempotent re-apply + policy behavior as
a non-superuser `authenticated` role).

**RLS is live.** The backend routes user-owned reads/writes through a
client that carries the user's JWT (`get_user_client` in `backend/app/db.py`),
so these policies enforce at the database; it keeps the **service key** (which
**bypasses RLS**) only for system/cross-user work — capacity aggregation,
analytics, control-flow reads, seeding, and resolving a user's role from
`profiles`. See `backend/CLAUDE.md` **Auth**. The in-router checks remain as
defense-in-depth. No explicit `grant`s live in `schema.sql` (they'd roll the
transaction back on a non-Supabase Postgres where the `anon`/`authenticated`
roles don't exist — Supabase provides them, and their default table grants,
already).

Note: RLS owner-writes rely on `resources.metadata.owner_id`, stamped by
`create_resource`. Rows seeded before auth (or without an owner) can't be
edited via a user token — expected; owners manage resources they created.

## Testing

This directory has no tests of its own — `slot_occupancy` correctness and
FK/constraint behavior should be covered by backend integration tests in
`test/` (see [test/CLAUDE.md](../test/CLAUDE.md)), since they require the
backend's Supabase client to exercise.
