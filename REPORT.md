# REPORT — Frontend ⇄ Backend wiring

_Snapshot after wiring the new `frontend/src/` app to the FastAPI backend on a
live Supabase project. Regenerate rather than hand-edit (see root `CLAUDE.md`)._

Branch: `16-auth-system`. Verified live (schema, seed, auth, RLS) against the
project's hosted Supabase, plus a headless-browser click-through of the app.

## What this delivery did

The new frontend (`frontend/src/`) previously ran entirely on an in-memory mock
(`src/api/mockStore.ts`). It models a much richer domain than the original flat
engine: **Provider → Service → Resource → Slot → Booking → User**, with search,
follow, reviews, day-availability, month-density, party size, and multi-slot
bookings. The backend was extended to own that domain and serve the frontend's
exact **camelCase** contract; the mock was deleted; real Supabase auth was added
to the frontend.

## Backend — what exists and how

### Schema (`supabase/schema.sql`, idempotent, RLS)
- **New tables** (`create table if not exists`): `providers`, `services`,
  `booking_slots` (multi-slot join), `reviews`, `follows`. The three base tables
  (`resources`/`slots`/`bookings`) stay frozen — their new fields ride in
  `metadata jsonb` (documented in a header comment).
- **`slot_occupancy` rewritten** (`create or replace`) to SUM `party_size` over
  confirmed bookings via `booking_slots`, so shared-capacity party sizes and
  multi-slot holds both count.
- **RLS** on all new tables: public read for discovery; owner writes for
  provider/service; per-user writes for booking children / follows / reviews.

### Serialization (`app/serialize.py`)
Pure row→wire mappers producing the exact `src/types/domain.ts` shapes
(camelCase). Server-side slot-status derivation (`past→blocked→full→
partially_booked→available`), completed-in-past booking status, and `iso_utc`
(UTC, trailing `Z`).

### Rules (`app/rules.py`)
`effective_service_rules(service)` merges a service's own columns over
`domain.config.json` global defaults over hard fallbacks — config's role shifted
from "the rules" to "defaults + vocabulary". `within_cutoff(...)` centralises the
cancel/reschedule window. The legacy global registry is retained for `slots.py`.

### Routers (`app/routers/`)
- `providers.py` — `GET /providers` (search text/category/near, followed-first),
  `GET /providers/by-code/{code}`, `GET /providers/{id}`, follow/unfollow.
- `services.py` — `GET /services?provider_id`, `GET /services/{id}`.
- `resources.py` — `GET /resources?service_id` (active-only), serialized output.
- `availability.py` — `GET /availability` (day-grouped in the viewer tz),
  `GET /month-density`.
- `bookings.py` — multi-slot + party-size create, `?scope` list, single get,
  reschedule (`newSlotIds`, atomic slot swap + change history), idempotent
  cancel, `POST /{id}/review`. Rule violations → typed `ApiError` codes.
- `me.py` — `GET /me`, `PATCH /me` (writes `user_metadata`).
- `demo.py` — `GET/POST /demo/vertical`, `POST /demo/reset` (backend reseed).
- `errors.py` — `api_error(code, message, details)` → the frontend's `ApiError`
  envelope `{code, message, details?}`.

### Auth (`app/auth.py`)
Verifies Supabase access tokens in **both** schemes: **ES256 via JWKS** (this
project's signing scheme, keyed by `kid`) and legacy **HS256**. `require_user` /
`require_owner` / new `optional_user`. Role resolved from `profiles`. RLS-scoped
user client for user-owned reads/writes; service key for system work.

### Seeding (`seed.py` + `seed_data.py`)
Three verticals (fleet / oneToOne / group) ported verbatim from the frontend
mock seeds: providers (with generated SVG avatars, seeded rating/reviewCount),
services (per-service rules), resources (attributes), **DST-aware slot grids**,
real occupancy edge cases (blocked / full / one-left via a hidden "holds"
customer), and the demo user's lifecycle bookings + a review + a follow. A demo
auth user is provisioned via the admin API. `active_vertical()` infers the
current vertical from a service's booking model.

## Frontend — what exists and how
- **Auth**: `src/lib/supabase.ts`, `src/lib/auth.tsx` (`AuthProvider`/`useAuth`/
  `getAccessToken`), `src/app/login/page.tsx` (login/sign-up + owner role
  toggle), `src/components/auth-gate.tsx` (redirects anonymous → `/login`). Root
  layout wraps `AuthProvider`; the `(app)` group is gated; owners are routed to
  `/owner`; Account has Sign out.
- **Seam**: `src/api/index.ts` rewritten as real HTTP — attaches the Bearer
  token, returns the domain shapes, maps errors to `ApiError` codes. Function
  signatures unchanged, so no page/component changed. Owner writes added
  (`getMyProviders`, `createProvider`, `createService`, `createResource`,
  `createSlot`).
- **Owner area** (`src/app/owner/`): role-gated dashboard to set up a business
  end to end — create provider → service (per-service rules) → units → open
  slots — and monitor it: per-unit occupancy + an expandable bookings list
  (reference/client/date/status, owner-scoped by `_owned_resource`). An
  owner-created business is immediately in the customer catalog.
- **Mock deleted**: `mockStore.ts`, `latency.ts`, `storeTypes.ts`, `seed/*`.
  `verticals.ts` is now pure UI vocabulary.

## Verified
- **Live backend** (real token): `/me`, `/bookings` (RLS scopes demo to its own
  6, holds excluded), create/reschedule/cancel with correct `CUTOFF_PASSED`
  enforcement, follow/unfollow, `PATCH /me`.
- **Live serialization**: providers (blended ratings, `Vistula 4.7/319`),
  services, resources, availability (blocked/full days), month-density.
- **Browser click-through** (headless Chrome, `demo@codaro.app`): login →
  `/search` (7 providers, follow state, geo) → `/bookings` (real refs/statuses)
  → `/account` (`/me` email). `tsc --noEmit` clean.

## Pre-existing issues fixed along the way
- Root `frontend/app/` was shadowing `frontend/src/app/` (Next uses root `app/`
  when both exist) → moved to `frontend/_legacy/root-app/`.
- `node_modules` was stale (Tailwind 3, no `@tailwindcss/postcss`) vs a Tailwind
  v4 `package.json` → reinstalled; app now builds.
- `SUPABASE_JWT_SECRET` / `SUPABASE_ANON_KEY` were missing from `backend/.env`
  (added by the operator); auth then verified end-to-end.

## Tests
Regenerated for the new contract (was 128 targeting the retired flat engine):

- **`python -m pytest test/backend -q` → 227 passed** (offline, in-memory
  `FakeSupabase`). Covers: pure-unit serializers + slot-status/completed
  derivation, `effective_service_rules`/`within_cutoff`, `_resolve_selection`
  every branch (asserting the raised `ApiError` code), `api_error` mapping,
  auth-gated integration tests for providers/services/resources/slots/
  availability/bookings/me, and the owner-gated provider/service create+update
  endpoints — with the fake occupancy view now summing `party_size` via
  `booking_slots` and enforcing composite-PK idempotency.
- **`python -m pytest test/e2e -q` → 8 passed** against the live Supabase
  project (signs in `demo@codaro.app` for a real JWT, then drives providers/
  by-code/services/availability/me/bookings + create→reschedule→cancel +
  follow/unfollow). Skips cleanly when `SUPABASE_URL`/`SUPABASE_ANON_KEY` are
  unset.

Deferred to the live suite (can't be faithfully faked offline): real ES256/JWKS
+ HS256 signature verification, `_resolve_role` from `profiles`, and live RLS
isolation. See `test/CLAUDE.md` for run instructions.
