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
| `app/config.py` | Loads → normalizes → **validates** → `lru_cache`s `domain.config.json`; `load_config()` (uncached, raises `ConfigError`), `get_raw_config()` |
| `app/config_schema.py` | Config **v2**: `DEFAULTS`, `normalize()` (defaults + v1 `rules`/`search` aliasing), `validate()`, the enum vocabularies |
| `app/pricing.py` | `quote(pricing, ctx)` — config-driven totals (rate/tiers/fees/caps/deposit) |
| `app/db.py` | `get_supabase()` (service key, bypasses RLS) + `get_user_client(token)` (JWT-scoped, RLS applies); `maybe_row()` (normalises PGRST116 **and** malformed-uuid `22P02` → None) |
| `app/schema_setup.py` | Idempotently applies `supabase/schema.sql` on startup (guarded) |
| `app/auth.py` | Verifies the Supabase JWT (ES256 via JWKS **and** legacy HS256); `require_user` / `require_owner` / `optional_user`; role from `profiles` |
| `app/serialize.py` | Row → **camelCase** domain shapes; server-side slot-status + completed-in-past derivation; `iso_utc` (UTC `Z`) |
| `app/rules.py` | Per-service rule resolver (`effective_service_rules`, `within_cutoff`) + the legacy event-keyed registry (still used by `slots.py`) |
| `app/errors.py` | `api_error(code, message, details)` → HTTPException carrying the frontend's `ApiError` envelope |
| `app/models.py` | Pydantic envelopes; the new request models accept camelCase (`CamelModel`) |
| `app/meta.py` | Config-driven `metaFields` validator |
| `app/discovery.py`, `app/users.py` | Aggregation helpers (rating/link arrays) and `User` assembly |
| `app/routers/*.py` | `providers`, `services`, `resources`, `slots`, `availability`, `bookings`, `me`, `owner`, `demo` |
| `app/routers/owner.py` | Business-mode aggregation: `/owner/dashboard` `/owner/services` `/owner/requests` `/owner/calendar` (owner-gated, scoped to the caller's providers) |
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

## Config v2 (`config_schema.py`)

`domain.config.json` grew from 5 sections to 20. The new blocks — `capabilities`,
`booking`, `pricing`, `payments`, `inventory`, `location`, `prerequisites`,
`timing`, `recurrence`, `entitlements`, `discovery` — are what let the *shape* of
the offering pivot, not just its vocabulary. Three rules hold:

- **Additive.** Nothing was removed. `rules` and `search` survive as deprecated
  aliases that `normalize()` keeps in sync with `timing` and `discovery` **in both
  directions**, so a v1 file boots unchanged and a v1 reader never sees a stale
  number. Precedence: explicit v2 path → explicit v1 path → default.
- **Validated at load, not at request.** `load_config()` raises `ConfigError`
  listing *every* problem. This file gets hand-edited under time pressure; a typo
  must fail at the edit, not on whichever booking reads it first.
- **Config is defaults; the service row is the override.** See below.

## Rules — per service (`rules.py`)

`effective_service_rules(service)` is still the single merge point for the seven
scalar rules, but the config side now takes a **dotted path** into the whole tree
(`"priceMinorUnits": ("price_minor_units", "pricing.rate.amountMinorUnits", 0)`),
so price, currency and min/max slots finally have a global default — in v1 they
had none and could only come from the column.

`effective_service_config(service)` lifts that idea from single keys to whole
blocks: `services.metadata.<block>` deep-merges over the global block for every
name in `OVERRIDABLE_BLOCKS`. That is what makes a marketplace work — two
businesses on one deployment can price and gate differently without either
touching `domain.config.json`. `effective_service_pricing()` folds the legacy
`price_minor_units`/`currency` columns in (they still win unless
`metadata.pricing` declares them), and `effective_auto_approve()` lets
`timing.confirmation` supply the default the owner's per-service toggle overrides.

**Overrides are validated on both paths.** `validate()` runs on the global file
at load, which for a while left per-service blocks reaching the pricing path
unchecked — a service could carry a `pricing` block that quoted real money with
no schema check. Now:

- **Write** — `POST`/`PATCH /services` take a `config` object keyed by block name
  and run `config_schema.validate_overrides()`; a bad block is a **422** naming
  the problem, so a business that mistypes its own pricing is told rather than
  quietly billed at the platform default. Config blocks replace **wholesale per
  block** on PATCH (a partial deep-merge would make removing a key impossible).
- **Read** — `effective_service_config` drops an invalid block and falls back to
  the global one, logging a warning. Only the offending block is dropped: a valid
  `timing` override survives alongside a rejected `pricing` one. This exists for
  seeded rows and direct DB edits, not as a substitute for the write gate — a
  customer's booking must not 500 over a business's typo.
- **`tenancy` is deliberately not overridable.** Commission and tenant
  verification are platform terms; a tenant setting its own `commission.rateBps`
  would be privilege escalation. It is rejected as an unknown block.

`service_override_problems(service)` returns one service's own errors, so an
owner-facing surface can show a business its bad config instead of it living only
in a server log.

The **event-keyed registry** (`apply_rules`) is the escape hatch: adding a
validator + a `timing` key makes a rule enforce, deleting the config key disables
it, and no router changes either way. It now declares `booking.create`,
`booking.change`, `booking.approve`, `booking.cancel`, `slot.create`,
`inventory.reserve`, `inventory.return` and `payment.due`; empty maps are live
extension points. `apply_rules` reads `timing`. `advanceBookingWindowDays` sits in
`UNDISPATCHED` on purpose — the seed lays slots 56 days out while the config
allows 30, so enforcing it today would make half the seeded calendar unbookable.
Parse all timestamps through `parse_ts()` / `serialize._parse` — never compare
naive to aware.

## Declared but NOT enforced

v1's real failure was config that looked live and did nothing (`copy`, `theme`
and `advanceBookingWindowDays` had zero readers). Keep that honest — if a key
lands in `DEFAULTS` before its enforcement does, say so here and in a comment
next to it:

| Key | Why not yet | Needs |
|-----|-------------|-------|
| `timing.advanceBookingWindowDays` | seed lays slots 56 days out, config allows 30 | reconcile the seed horizon, then move out of `rules.UNDISPATCHED` |
| `pricing.caps.perDayMinorUnits` | needs the customer's other bookings that day | a query, not arithmetic |
| `payments.noShowFee` | no payments table exists | the `PaymentAdapter` layer |
| `timing.approvalWindowHours` | nothing expires a stale request | a scheduled job |
| `pricing.tiers[].quantityCap` | needs a sold-count | a query |

`rules.UNDISPATCHED` also holds `maxBookingsPerSlot` **deliberately**: capacity is
enforced upstream by `_resolve_selection` + `slot_occupancy`, which understand
party size and multi-slot holds. Re-registering it under `booking.create` would
re-apply `min(capacity, maxBookingsPerSlot)` and cap every shared-capacity slot at
the global default of 1, breaking group bookings. There is a regression test.

## Pricing (`pricing.py`)

v1 priced every booking with one expression inlined in `bookings.py`
(`priceMinorUnits * len(rows) * party`) — exactly one model, and the reason a
per-hour/per-night/tiered niche needed code. `quote(pricing, ctx)` replaces it:
tier match → base (`rate.per` × quantity × party factor) → secondary rate → fees
→ caps → deposit, returning a total plus an itemised `breakdown`. **The defaults
reproduce the v1 expression exactly**, so an un-pivoted service prices
identically. `tiers[].quantityCap` validates and round-trips but does not gate
yet — it needs a sold-count query, which is a database question.

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
  `GET /resources?service_id` (active-only). Services carry `autoApprove` (from
  `metadata.auto_approve`, default `true`); owner create/PATCH set it (a
  non-column field routed to `services.metadata`, like `imageUrl`).
- **Availability:** `GET /availability?service_id&resource_id&from&to` →
  `DayAvailability[]` grouped in the viewer's timezone;
  `GET /month-density?...&month` → `MonthDensityCell[]`. Status/occupancy derived
  server-side; occupancy already sums party size.
- **Bookings (`require_user`, RLS-scoped user client):** multi-slot + party-size
  create; `GET /bookings?scope=upcoming|past|all` (RLS scopes to own/owner,
  completed-in-past derived); `GET /bookings/{id}`; reschedule (`newSlotIds`,
  atomic slot swap + change history); idempotent cancel; `POST /{id}/review`.
  Create honours the service's `autoApprove`: `true` (default) → `confirmed`
  immediately; `false` → `pending` (a request the owner acts on). Owner-only
  `POST /{id}/approve` (pending→confirmed, capacity re-checked; pending holds
  none) and `POST /{id}/reject` (pending→rejected, idempotent) gate on the
  booking's provider being the caller's.
- **Booking status.** Wire `BookingStatus` is now
  `confirmed | cancelled | completed | pending | rejected`. `pending`/`rejected`
  pass through `effective_booking_status` unchanged (a pending request is never
  auto-completed by elapsed time); `slot_occupancy` still counts only
  `confirmed`, so pending never holds a seat.
- **Owner / business dashboard (`require_owner`, scoped to the caller's own
  providers):** `GET /owner/dashboard` (badge provider, three glanceable
  numbers — upcoming-by-service, month-over-month satisfaction delta, revenue
  this month — this week's bookings, top pending requests); `GET /owner/services`
  (each service + `stats`: upcoming/past/total bookings, pending, revenue,
  avgRating); `GET /owner/requests` (every pending request + a `client`
  screening card: member-since, history, cancels); `GET /owner/calendar?from&to`
  (confirmed/completed bookings in a window, default current month). Reads use
  the service key (system aggregation); shapes are additive owner-only envelopes.
- **Account:** `GET /me`, `PATCH /me` (writes editable fields to
  `user_metadata`); `DELETE /me` (GDPR erasure — `app.gdpr.erase_user` removes
  the user's bookings/follows/`client_reviews`, their avatar, and — for owners —
  their owned providers + every booking under them, then deletes the auth
  account; idempotent, service-key, returns 204); `GET /me/reputation` (the
  customer's rating + the reviews businesses left them, from `client_reviews`);
  `POST /providers/{id}/follow` + `/unfollow` (return the User).
- **Client reputation:** `POST /bookings/{id}/client-review` (owner, completed
  bookings only) records a rating of the customer in `client_reviews`; it feeds
  `GET /me/reputation` and the owner Requests screening card's `rating`.
  `GET /providers/{id}/reviews` (public) lists a provider's recent reviews for
  the Profile tab.
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
cases (blocked / full / one-left via a hidden "holds" auth user), the demo
user's lifecycle bookings + a review + a follow, and **pending requests** on the
manual-approve primary service (`_seed_requests`) so the owner's Requests tab is
populated. Auth users provisioned via the admin API: `demo@codaro.app` (client),
the holds user, `owner@codaro.app` (owns the demo provider — the business login),
and `prospect@codaro.app` (a fresh client whose request is pending).
`seed_if_empty()` runs on startup when no providers exist; `active_vertical()`
infers the current vertical from a service's booking model.

## Don't

- Touch `supabase/schema.sql`'s base tables (frozen) or add columns to them —
  new fields go in `metadata`, new entities are new tables.
- Hand-roll auth — verify the Supabase JWT (ES256/JWKS or HS256); read roles from
  `profiles`. No parallel users/passwords table.
- Break the frontend contract in `frontend/src/api/index.ts` — keep paths/params
  and the camelCase shapes; only add.
- Ship a config-driven *default* `"pending"` booking status. `pending` is a
  **per-service opt-in** (`autoApprove=false`) for the Requests-tab flow, not a
  global default — auto-approve stays the default and `slot_occupancy` counts
  only `confirmed`, so a pending request holds no capacity (re-checked at
  approval).

## Testing

Don't write tests here. API tests live in `test/` (owned by `test-writer`):
`test/backend` runs offline (in-memory `FakeSupabase` + a `dependency_overrides`
auth stub); `test/e2e` runs the full stack against live Supabase. If you change a
route's contract, note it for `test-writer`. See [test/CLAUDE.md](../test/CLAUDE.md).

**Contract changes for `test-writer` (business mode):**
- `serialize_service` gained `autoApprove` → update `SERVICE_KEYS` in
  `test_serialize.py` (and the two `test_services.py` key-set asserts).
- `BookingStatus` gained `pending`/`rejected` (`effective_booking_status` passes
  them through) — add cases; frontend `domain.ts` needs the union widened too.
- New endpoints to cover: `POST /bookings/{id}/approve` + `/reject`
  (owner-gated, ownership check, pending-only, capacity re-check on approve) and
  the `/owner/*` router.
- `DELETE /me` (GDPR erasure, `app/gdpr.py`): 204; idempotent (second call no-ops);
  removes the caller's bookings/follows/`client_reviews`; owner variant also drops
  their owned providers + those providers' bookings. `erase_user` is best-effort
  (each step wrapped in try/except), so it degrades cleanly on the offline fake.
- `GET /providers/{id}/reviews` `author` is now the reviewer's **display name**
  (`user_metadata`), falling back to `"Guest"` — never the email local-part.
- `app/routers/owner.py` does `from app.db import get_supabase`, so add
  `owner_router` to `conftest._SUPABASE_MODULES` (it needs no user client) before
  its endpoints can be exercised offline. `_client_profile` calls
  `db.auth.admin.get_user_by_id`, which `FakeSupabase` lacks — it degrades
  gracefully (screening fields fall back), so no fake change is required.
