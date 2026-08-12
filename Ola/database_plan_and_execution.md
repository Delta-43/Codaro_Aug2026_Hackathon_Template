# Database Plan

## 1. Define the entities

Keep it domain-agnostic (generic terms now, alias later for Track B).

| Table | Purpose | Key columns |
|---|---|---|
| `resources` | The bookable thing | `id`, `name`, `category`, `capacity`, `metadata jsonb` |
| `slots` | Fixed bookable time windows per resource | `id`, `resource_id`, `start_time`, `end_time`, `is_recurring` |
| `clients` | Who books (or reuse Supabase `auth.users`) | `id`, `name`, `email` |
| `reservations` | The booking itself | `id`, `slot_id`, `client_id`, `status`, `created_at` |
| `reservation_events` | Audit trail of changes/cancellations | `id`, `reservation_id`, `action`, `old_status`, `new_status`, `changed_at`, `reason` |

`status` as an enum: `pending` → `confirmed` → `cancelled` (+ `changed` if you track modifications separately, or just log them in `reservation_events`).

**Status**: Created a database_project.md, schema.sql and Markdown files: POSTGRES_ACCORDANCE.md which explains how the SQL code is written in accordance with SQL (useful for future bugs) and schema_info.md which explains SQL syntax I do not understand.

## 2. Relationships & constraints

- `resources (1)` → `slots (many)`
- `slots (1)` → `reservations (many)` — but enforce **one active reservation per slot** (unless resources allow overlapping capacity > 1)
- `reservations (1)` → `reservation_events (many)` for history/audit
- Use a `EXCLUDE` constraint or a partial unique index on `(slot_id) WHERE status IN ('pending','confirmed')` to prevent double-booking at the DB level, not just app level — this is the kind of thing judges notice.

**Status**: According to Claude the created database adheres to this constrains.

## 3. Business rules to encode

- Cancellation window (e.g. can't cancel < X hours before start) — enforce in a trigger or in FastAPI, your call, but decide now.
- Max bookings per slot (capacity > 1 case, e.g. a class or shared resource).
- Buffer time between slots for a resource (relevant for Track B doctor pivot). Put these as either DB constraints/triggers (safer, demoable) or app-layer checks (faster to write). Given hackathon time, I'd do the double-booking prevention in the DB and everything else in FastAPI.

### Detailed plan:
Plan: Cancellation Window & Buffer Time
Confirmed from docs/database.md / schema.sql: resources.buffer_minutes and resources.cancellation_window_hours already exist as columns, but nothing reads them yet. Max bookings per slot (capacity) is already done — the check_slot_capacity() trigger from the earlier step covers it, no more work needed there.

Per your split (double-booking in DB, everything else in FastAPI), here's the plan for the remaining two:

1. Cancellation window — FastAPI
Build the cancel endpoint (PATCH /reservations/{id}/cancel or similar).
On request: fetch the reservation joined with its slot.start_time and the parent resources.cancellation_window_hours.
Compute slot.start_time - now(); if it's less than cancellation_window_hours, reject with a 400 and a clear message (e.g. "cancellation window has passed").
If allowed: update reservations.status = 'cancelled', and insert a row into reservation_events (action='cancelled', old_status, new_status, reason).
2. Buffer time between slots — FastAPI
This applies at slot creation time, not booking time, since slots are fixed windows (slots table) rather than computed on the fly.
Wherever slots get created for a resource (seed script or an admin endpoint), before inserting: query existing slots for that resource_id, and reject if the new slot's start/end falls within buffer_minutes of any neighboring slot's start/end.
Relevant directly for the Track B pivot (buffer between doctor appointments).
3. Audit trail wiring
Since reservation_events isn't populated automatically by any trigger, every status-changing endpoint (create, confirm, cancel, modify) needs to explicitly insert an event row in the same request — decide now that this lives in FastAPI too, consistent with the "everything but double-booking is app-layer" call.
4. Testing
FastAPI-level tests: cancel within window → rejected; cancel outside window → accepted. Slot creation violating buffer → rejected; valid gap → accepted.
Optional: reuse the local Postgres instance from before to sanity-check the underlying data (no new DB logic to test here since these two rules stay app-layer).
5. Stretch goal (only if time allows)
Mirror the cancellation-window check as a DB trigger/CHECK too, as a safety net against bypassing the API — skip this unless the core booking flow is done early.

## 4. The occupancy view

This is your killer feature for judges — a SQL view, not app logic:

```sql
create view occupancy as
select r.id as resource_id, r.name,
       s.id as slot_id, s.start_time, s.end_time,
       res.status
from resources r
join slots s on s.resource_id = r.id
left join reservations res on res.slot_id = s.id and res.status in ('pending','confirmed');
```

Frontend queries this view directly (Supabase client can hit it) to render the calendar — no need for a separate FastAPI endpoint if you want to save time.

## 5. Supabase-specific setup

- Enable Row Level Security early, not at the end — retrofitting RLS the night before demo is painful.
- Decide: does `clients` map to `auth.users` (Supabase auth) or a separate table? Using `auth.users` directly saves you an entire signup flow.
- Realtime: subscribe to `reservations` changes so the calendar updates live when someone else books — nice demo moment, low effort with Supabase.

## 6. Track B compatibility

No schema changes needed — just:

- A config/mapping layer for labels (resource→doctor, client→patient) in the frontend, not the DB.
- Business rules (cancellation window, buffer time) as **columns on** `resources` (e.g. `buffer_minutes`, `cancellation_window_hours`) rather than hardcoded, so the same tables serve both tracks.

## 7. Build order (suggested)

1. `resources`, `slots` tables + seed data
2. `reservations` table + double-booking constraint
3. Occupancy view
4. `reservation_events` audit table + cancellation logic
5. RLS policies
6. Realtime subscription check

---

Want me to write the actual SQL migration files next, or start with seed data so the frontend team has something to build against immediately?