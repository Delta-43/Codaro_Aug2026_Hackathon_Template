# supabase/, database schema

## Role

`schema.sql` defines the tables that back the booking engine. The **neutral base
tables**, `resources`, `slots`, `bookings`, plus the `slot_occupancy` view are
the frozen spine; on top of them sit the **extended entities** the richer domain
needs (`providers`, `services`, `booking_slots`, `reviews`, `follows`, `conversations`, `messages`, `entitlements`, `waitlist_entries`) and the
auth layer (`profiles`). This is the only file in this directory, the database
itself is hosted Supabase (Postgres), not a local container.

## Hard rules

- **Idempotent, always.** Only `create table if not exists`,
  `create index if not exists`, `create or replace view`, and
  `drop policy if exists` before each policy. Never `DROP`/`ALTER` a table, the
  backend re-runs this file on every startup (`SUPABASE_DB_URL`), and existing
  data must survive that.
- **Base tables (`resources`/`slots`/`bookings`) are frozen.** New domain fields
  go in their `metadata jsonb`, never a new column. New *entities* are added as
  **new tables** (idempotently, the same way `profiles` and the extended
  entities were added). That's the pivot design, see root
  [CLAUDE.md](../CLAUDE.md).
- **No custom password table.** Auth is **Supabase Auth**: Supabase owns
  `auth.users` + password hashing. `profiles` (1:1 with `auth.users`) holds the
  engine `role`; per-user profile fields (displayName/timezone/avatar/verified)
  live in Supabase `user_metadata`, not here.
- **`bookings.history`** is append-only jsonb (every status change is pushed on,
  never overwritten).

## Tables

**Base (frozen; new fields ride in `metadata`):**
- `resources`: `metadata`: `service_id`, `capacity`, `active`,
  `attributes[{label,value}]`, `image_url`, `owner_id`.
- `slots`: `metadata`: `service_id`.
- `bookings`: one row per booking; `slot_id` holds the *first* slot for
  base-table compatibility. `metadata`: `party_size`, `reference`,
  `price_minor_units`, `currency`, `provider_id`, `service_id`, `resource_id`,
  `user_id`, `slot_ids[]`, `change_history[]`, `cancelled_at_utc`.

**Extended entities (new tables, idempotent):**
- `providers`: the business/tenant. Columns `owner_id`, `name`,
  `public_code` (unique, for code/QR lookup), `category_id`; `metadata` holds
  presentational fields (avatar/cover/tagline/bio/location/links) and the seeded
  `rating`/`review_count` baseline. Live rating is derived from `reviews`.
- `services`: a bookable offering under a provider. The **per-service rules**
  are real columns: `booking_model`, `slot_duration_minutes`,
  `min/max_slots_per_booking`, `price_minor_units`, `currency`,
  `cancellation_cutoff_hours`.
- `booking_slots`: multi-slot join `(booking_id, slot_id)` (composite PK).
- `reviews`: one per completed booking (`booking_id`, `provider_id`, `rating`,
  `text`); provider aggregates are computed from these.
- `client_reviews`: a provider's rating of a **customer** after a completed
  booking (`booking_id` unique, `client_id`, `provider_id`, `rating`, `text`).
  Public read; owner-only insert. Feeds the customer's reputation
  (`GET /me/reputation`) and the owner-side request screening.
- `follows`: `(user_id, provider_id)` composite PK.
- `profiles`: engine `role` (`owner`|`client`), auto-provisioned by the
  `handle_new_user()` trigger from `raw_user_meta_data->>'role'`.

**`slot_occupancy` view** (`create or replace`) sums **`party_size`** over
`confirmed` bookings joined through `booking_slots`, so shared-capacity party
sizes and multi-slot holds are both counted (was: `count(*)` of confirmed rows).
Only `confirmed` holds capacity; `cancelled`/`rescheduled` release it.

## RLS

Enabled on every table; policies key on `auth.uid()`. Public `select` for
discovery (`providers`/`services`/`resources`/`slots`/`reviews`); owner writes
for `providers`/`services` (own `owner_id` / parent provider); per-user writes
for `bookings` + `booking_slots` (`client_id = auth.uid()`), `follows`, and
`reviews` (own booking). `profiles`: read-own only, a client can't self-promote
(only the trigger / service role / an admin write it). `is_owner()` is a
`security definer` helper the policies use to read the role without recursion.

**Enforcement.** The backend routes user-owned reads/writes through a
JWT-scoped client (`get_user_client`), so these policies enforce live at the
database. The **service key bypasses RLS** and is kept for system/cross-user work
(aggregation, analytics, seeding, resolving roles, control-flow reads). In-router
checks remain as defense-in-depth. See `backend/CLAUDE.md` **Auth**. No explicit
`grant`s live here (Supabase provides the `anon`/`authenticated` roles + default
grants; adding them would roll back the transaction on a non-Supabase Postgres).

Note: seeded providers/resources carry no `owner_id` (created via the service
key), so token-scoped owner edits against them hit RLS 403 by design, owners
manage what they created.

## Testing

No tests of its own, `slot_occupancy` correctness (party-size + multi-slot),
FK/cascade, and RLS behavior are covered by `test/backend` (fake occupancy
mirrors the SQL) and the live `test/e2e` suite. See
[test/CLAUDE.md](../test/CLAUDE.md).
