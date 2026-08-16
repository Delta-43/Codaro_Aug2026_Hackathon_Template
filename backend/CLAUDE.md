# backend/ — FastAPI booking engine

## Role

The booking-engine API. Owns: reading the pivot file, per-service rule
resolution, camelCase serialization, the domain routers
(`/providers` `/services` `/resources` `/slots` `/availability` `/bookings`
`/me` `/demo`), Supabase-Auth verification, and three-vertical seeding. It serves
the frontend's exact contract (`frontend/src/types/domain.ts`). See root
[CLAUDE.md](../CLAUDE.md) and [supabase/CLAUDE.md](../supabase/CLAUDE.md).

## Files

| File | Responsibility |
|------|-----------------|
| `app/main.py` | App wiring, lifespan (schema setup + seed), `GET /health`, `GET /config`, `POST /config/reload`, router mounts |
| `app/config.py` | Loads + `lru_cache`s `domain.config.json` |
| `app/db.py` | `get_supabase()` (service key, bypasses RLS) + `get_user_client(token)` (JWT-scoped, RLS applies); `maybe_row()` (normalises PGRST116 **and** malformed-uuid `22P02` → None) |
| `app/schema_setup.py` | Idempotently applies `supabase/schema.sql` on startup (guarded) |
| `app/auth.py` | Verifies the Supabase JWT (ES256 via JWKS **and** legacy HS256); `require_user` / `require_owner` / `optional_user`; role from `profiles` |
| `app/serialize.py` | Row → **camelCase** domain shapes; server-side slot-status + completed-in-past derivation; `iso_utc` (UTC `Z`) |
| `app/rules.py` | Per-service rule resolver (`effective_service_rules`, `within_cutoff`) + the legacy event-keyed registry (still used by `slots.py`) |
| `app/errors.py` | `api_error(code, message, details)` → HTTPException carrying the frontend's `ApiError` envelope |
| `app/models.py` | Pydantic envelopes; the new request models accept camelCase (`CamelModel`) |
| `app/meta.py` | Config-driven `metaFields` validator |
| `app/discovery.py`, `app/users.py` | Aggregation helpers (rating/link arrays) and `User` assembly |
| `app/routers/*.py` | `providers`, `services`, `resources`, `slots`, `availability`, `bookings`, `me`, `demo` |
| `seed.py`, `seed_data.py` | Three-vertical demo seeding; `seed_vertical(id)`, `active_vertical()`, `seed_if_empty()` |

## Conventions

- **Nothing hard-codes a domain term or a magic number.** Vocabulary/defaults
  come from `get_config()`; per-service limits come from the service row via
  `effective_service_rules` — never a literal.
- **New domain data → `metadata jsonb`** on the frozen base tables, never a new
  column. New *entities* are new tables. `serialize.py`'s header documents the
  metadata key conventions (it's the authority; `seed.py` writes the same keys).
- **Serve the frontend contract verbatim.** Routers return the camelCase shapes
  from `serialize.py` — single objects or arrays, not raw PostgREST rows. Rule
  violations surface as `api_error(...)` with a frontend `ApiErrorCode`.
- **Identity comes from the token, not the body.** `create_booking` sets
  `client_email`/`client_id` from the verified user; body identity is ignored.
- **`bookings.history` is append-only**; multi-slot bookings also write
  `booking_slots` rows and carry `slot_ids`/`change_history` in `metadata`.
- **Single-row lookups go through `db.maybe_row()`** (reachable 404s).
- **Startup uses FastAPI lifespan** through module-level `create_tables_if_configured` / `seed_if_empty` (tests monkeypatch them).

## Rules — per service (`rules.py`)

The frontend models rules **per service** (slot duration, min/max slots per
booking, cancellation cutoff, price/currency, booking model).
`effective_service_rules(service)` is the single merge point: a service's own
column wins, else the `domain.config.json` `rules` global default, else a hard
fallback. `domain.config.json`'s role shifted from "the rules" to "vocabulary +
global defaults". `within_cutoff(...)` centralises the cancel/reschedule window.

The **legacy event-keyed registry** (`apply_rules`, `check_capacity`,
`check_cancellation_window`, `bufferMinutes`, `slotDurationMinutes`) is retained
and still used by `slots.py`; the `booking.create`/`booking.change` entries are
superseded by the per-service flow in `bookings.py`. Parse all timestamps through
`parse_ts()` / `serialize._parse` — never compare naive to aware.

## Validation

- **Pydantic envelope, explicit inserts** — never spread `**payload`. The new
  request models (`BookingCreateReq`, `RescheduleReq`, `ReviewReq`, `UserPatch`)
  extend `CamelModel` (accept camelCase and snake_case).
- **`metadata` validated by `meta.py`** from `get_config()["metaFields"][entity]`
  at request time (lenient on undeclared keys, strict on declared).
- **Booking selection** (`bookings._resolve_selection`) re-checks at commit:
  slots exist, same service+resource, within min/max, **contiguous**, not past,
  capacity>0, `party_size ≤ capacity`, remaining seats ≥ party (crediting back
  the booking's own hold on reschedule). Each failure raises the matching
  `ApiErrorCode`.

## Domain API

- **Discovery (public reads, service key; personalised when a token is present
  via `optional_user`):** `GET /providers` (search text/category/near,
  followed-first), `GET /providers/by-code/{code}`, `GET /providers/{id}`;
  `GET /services?provider_id`, `GET /services/{id}`;
  `GET /resources?service_id` (active-only).
- **Availability:** `GET /availability?service_id&resource_id&from&to` →
  `DayAvailability[]` grouped in the viewer's timezone;
  `GET /month-density?...&month` → `MonthDensityCell[]`. Status/occupancy derived
  server-side; occupancy already sums party size.
- **Bookings (`require_user`, RLS-scoped user client):** multi-slot + party-size
  create; `GET /bookings?scope=upcoming|past|all` (RLS scopes to own/owner,
  completed-in-past derived); `GET /bookings/{id}`; reschedule (`newSlotIds`,
  atomic slot swap + change history); idempotent cancel; `POST /{id}/review`.
- **Account:** `GET /me`, `PATCH /me` (writes editable fields to
  `user_metadata`); `POST /providers/{id}/follow` + `/unfollow` (return the User).
- **Demo:** `GET /demo/vertical` (public), `POST /demo/vertical` + `POST
  /demo/reset` (`require_user`, destructive backend reseed).

Owner-gated writes (`require_owner`) exist on resource/slot CRUD + analytics;
provider/service **create** endpoints are not added (seeds populate catalog).

## Auth (Supabase Auth)

`app/auth.py` verifies the `Authorization: Bearer <jwt>` **locally**:

- **Both signing schemes.** The token header's `alg` selects the path —
  **ES256/RS256 via the project's JWKS** (this Supabase project's scheme, keyed
  by `kid`, cached `PyJWKClient`) or legacy **HS256** with `SUPABASE_JWT_SECRET`.
  `aud="authenticated"`. 401 on missing/invalid/expired.
- **`require_user` / `require_owner` / `optional_user`** gate routes; public
  reads stay open. Role is **trusted from `profiles`** (`_resolve_role`, seeded
  from the sign-up role on first sight), not the self-asserted token.
- **RLS is the live enforcement layer.** User-owned reads/writes go through
  `get_user_client(token)`; `enforce_rls_write()` turns an RLS-denied empty write
  into a clear 403. The service key (bypasses RLS) is kept for system work.

Requires `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`,
`SUPABASE_URL` (+ `SUPABASE_DB_URL` for schema/seed) and `pyjwt[crypto]`.

## Seeding (`seed.py` + `seed_data.py`)

`seed_data.VERTICALS` is the three-vertical config ported verbatim from the
frontend mock. `seed_vertical(id)` wipes the extended/booking tables and rebuilds
providers → services → resources → DST-aware slot grids, real occupancy edge
cases (blocked / full / one-left via a hidden "holds" auth user), and the demo
user's lifecycle bookings + a review + a follow. Two auth users are provisioned
via the admin API (`demo@codaro.app`, and the holds user). `seed_if_empty()`
runs on startup when no providers exist; `active_vertical()` infers the current
vertical from a service's booking model.

## Don't

- Touch `supabase/schema.sql`'s base tables (frozen) or add columns to them —
  new fields go in `metadata`, new entities are new tables.
- Hand-roll auth — verify the Supabase JWT (ES256/JWKS or HS256); read roles from
  `profiles`. No parallel users/passwords table.
- Break the frontend contract in `frontend/src/api/index.ts` — keep paths/params
  and the camelCase shapes; only add.
- Ship a config-driven default `"pending"` booking status — `slot_occupancy`
  counts only `confirmed`.

## Testing

Don't write tests here. API tests live in `test/` (owned by `test-writer`):
`test/backend` runs offline (in-memory `FakeSupabase` + a `dependency_overrides`
auth stub); `test/e2e` runs the full stack against live Supabase. If you change a
route's contract, note it for `test-writer`. See [test/CLAUDE.md](../test/CLAUDE.md).
