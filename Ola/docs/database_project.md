# Database Entities

Domain-agnostic naming for Track A (general resource booking). Terminology can
be aliased for Track B (doctor/patient scheduling) at the presentation layer
without changing the schema — see [Track B mapping](#track-b-mapping) below.

## Entity overview

| Table | Purpose | Key columns |
|---|---|---|
| `resources` | The bookable thing | `id`, `name`, `category`, `capacity`, `metadata jsonb` |
| `slots` | Fixed bookable time windows per resource | `id`, `resource_id`, `start_time`, `end_time`, `is_recurring` |
| `clients` | Who books (or reuse Supabase `auth.users`) | `id`, `name`, `email` |
| `reservations` | The booking itself | `id`, `slot_id`, `client_id`, `status`, `created_at` |
| `reservation_events` | Audit trail of changes/cancellations | `id`, `reservation_id`, `action`, `old_status`, `new_status`, `changed_at`, `reason` |

## `resources`

The bookable entity type — a room, a machine, a doctor, a table, etc.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid`, PK | |
| `name` | `text` | |
| `category` | `text` | e.g. "meeting room", "consultant" — used for filtering |
| `capacity` | `int` | how many concurrent reservations a single slot can hold (default 1) |
| `buffer_minutes` | `int` | gap required between consecutive slots on this resource |
| `cancellation_window_hours` | `int` | how late a reservation can still be cancelled |
| `metadata` | `jsonb` | free-form extra fields per resource type |

## `slots`

Discrete bookable time windows belonging to a resource.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid`, PK | |
| `resource_id` | `uuid`, FK → `resources.id` | |
| `start_time` | `timestamptz` | |
| `end_time` | `timestamptz` | |
| `is_recurring` | `boolean` | flags slots generated from a recurrence rule |

## `clients`

Who makes a reservation. Can reuse Supabase `auth.users` instead of a
separate table if auth is wired up early.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid`, PK | |
| `name` | `text` | |
| `email` | `text`, unique | |

## `reservations`

The booking itself, linking a client to a slot.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid`, PK | |
| `slot_id` | `uuid`, FK → `slots.id` | |
| `client_id` | `uuid`, FK → `clients.id` | |
| `status` | `enum` | `pending`, `confirmed`, `cancelled` |
| `created_at` | `timestamptz` | |

**Constraint:** at most one active (`pending`/`confirmed`) reservation per
slot beyond a resource's `capacity` — enforced at the database level, not
just in the app.

## `reservation_events`

Audit trail for every change made to a reservation (confirmation, edit,
cancellation).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid`, PK | |
| `reservation_id` | `uuid`, FK → `reservations.id` | |
| `action` | `text` | e.g. `created`, `confirmed`, `changed`, `cancelled` |
| `old_status` | `enum`, nullable | |
| `new_status` | `enum` | |
| `changed_at` | `timestamptz` | |
| `reason` | `text`, nullable | free-text cancellation/change reason |

## Relationships

- `resources (1) → slots (many)`
- `slots (1) → reservations (many)`, capped by `resources.capacity`
- `reservations (1) → reservation_events (many)`

## Track B mapping

No schema changes — only presentation-layer aliasing and rule values:

| Track A | Track B |
|---|---|
| `resources` | doctors |
| `clients` | patients |
| `slots` | appointment slots |
| `reservations` | appointments |

`buffer_minutes` and `cancellation_window_hours` on `resources` carry the
per-domain business rules (e.g. buffer time between appointments) without
needing separate schemas per track.
