# TODO — Data-loading performance

Snapshot from a read-only analysis of why pages are slow to load **even in
production**. The root problem is **round-trip amplification to hosted
Supabase**: nearly every page fans one user action into many *sequential*
PostgREST / GoTrue calls over the internet. The backend uses the *synchronous*
`supabase-py` client, so independent calls inside a single request run serially,
each paying a full internet RTT. Production doesn't help because the bottleneck
is network waterfalls, not CPU.

Prioritized by impact. Each item lists the evidence and the concrete fix. No
code has been changed yet.

---

## P1 — Every authenticated request makes an extra `profiles` round trip
**File:** `backend/app/auth.py:71-84` (`_resolve_role`)

`_resolve_role()` runs on every request through `require_user` / `require_owner`
— and on public reads too when a token is present (`optional_user`). It does a
blocking `profiles.select("role").eq("id", sub)` to Supabase *before the route
handler starts*, with no caching. This is a latency tax on literally every page.

**Fix:** cache the role with a short TTL keyed by `sub` (in-process dict or
`cachetools.TTLCache`), or trust the role from the JWT claims on the hot path and
reconcile with `profiles` lazily. Removes one internet RTT from every request.

**Not a cause (already good):** JWKS is `lru_cache`d with a 300s lifespan
(`auth.py:115-126`) and `/config` is `lru_cache`d (`config.py`), so neither
JWKS nor `domain.config.json` is refetched/re-read per request.

---

## P2 — Bookings page N+1 (frontend)
**File:** `frontend/src/app/(app)/bookings/page.tsx:34-47`

After `getBookings(scope)`, the page loops every unique `providerId` and
`serviceId` and fires a separate `getProvider(id)` / `getService(id)` HTTP call
each — just to resolve a display name. Each of those is a multi-query aggregate
on the backend:
- `getProvider` → `providers.py:193-201` → `review_aggregates` +
  `service_ids_by_provider` + provider row (3 queries) + P1.
- `getService` → `services.py:120-127` → `resource_ids_by_service` + service row
  (2 queries) + P1.

A list with 2 providers + 3 services ≈ **~22 Supabase round trips**, most
serialized behind the initial `getBookings`.

**Fix:** embed provider/service `name` in the bookings payload server-side, or
add a batch endpoint (`getProviders(ids)` / `getServices(ids)`) so it's one call
each instead of N. Combine with P6 (client cache).

---

## P3 — Owner dashboard / requests N+1 on client screening
**File:** `backend/app/routers/owner.py:213-216`, `_client_profile` at
`owner.py:168-189`

`/owner/requests` calls `_client_profile()` per unique pending client, and each
does **two** remote calls: `db.auth.admin.get_user_by_id(client_id)` (a GoTrue
admin round trip) **plus** a `bookings.select(...).eq("client_id", ...)` query.
5 pending clients = 10 extra serial round trips — on top of the ~7 that
`_Scope.__init__` (`owner.py:87-113`) already costs (providers + services + full
`resources` scan + full `bookings` scan + enrich).

**Fix:** batch — one `bookings.in_("client_id", [...])` for all pending clients,
and either read member-since from a single query or loop admin lookups only when
strictly needed. Overlaps with P5 (stop full-table scans).

---

## P4 — Redundant GoTrue admin-API calls where the JWT already has the data
**File:** `backend/app/users.py:15-26` (`user_metadata`)

`user_metadata()` calls `get_supabase().auth.admin.get_user_by_id(user.id)` to
read metadata that is **already in the verified JWT** (`user.claims`, used only
as a fallback at line 26). It fires on `GET /me`, `PATCH /me`, follow, unfollow,
and inside `load_user` — which logged-in `searchProviders` calls for every
search (`providers.py:52`). So a logged-in search ≈ P1 + 3 discovery queries +
admin call + follows query ≈ 6 round trips.

**Fix:** read `user_metadata` from `user.claims["user_metadata"]` by default;
only hit the admin API right after a `PATCH /me` when you need the just-written
value (or return the patched value directly from the PATCH handler).

---

## P5 — Full-table scans filtered in Python instead of at the DB
Because domain foreign keys live in `metadata jsonb`, hot paths fetch whole
tables and filter in Python. Grows linearly with catalog size.

- `availability.py:47-52` (`_resource_ids`) — fetches **all** `resources` on
  every `/availability` and `/month-density`, filters `metadata->>service_id` in
  Python.
- `discovery.py:13-41` — `resource_ids_by_service`, `resource_ids_by_provider`,
  `review_aggregates` each pull full tables.
- `owner.py:101-112` — pulls **all** `resources` and **all** `bookings`, filters
  by provider in Python.
- `providers.py:57-63` (`get_provider_by_code`) — serializes **every** provider
  to find one by `public_code`, though that column is unique + indexed.

**Fix:** persist `provider_id` / `service_id` as real (indexed) columns or add
functional indexes on `metadata->>'...'` so PostgREST can filter server-side;
filter `by-code` directly on `public_code`.

---

## P6 — No client-side caching; redundant/repeated fetches (frontend)
**File:** `frontend/src/hooks/use-async.ts`, `.../search/page.tsx:42-53`,
`.../context/app-context.tsx:71-83`

`use-async` re-runs `fn()` on every mount / dependency change with no shared
cache, so every tab switch refetches from scratch. Amplifiers:
- Search page issues **two** `searchProviders` calls on mount (filtered results +
  a second unfiltered call to populate QR targets); both re-fire on
  follow/unfollow and on debounced keystrokes.
- `app-context` boots with `getActiveVertical()` + `getCurrentUser()` (the latter
  hits P4's admin API) before `ready` flips — gating first paint of the whole
  `(app)` group.

**Fix:** add a client cache (React Query / SWR) so tab switches and duplicate
calls are deduped/served from cache; drop the second unfiltered search (derive QR
targets from the first result or a dedicated lightweight endpoint).

---

## P7 — Availability view has no index for its time-window filter
**File:** `supabase/schema.sql` (`slot_occupancy` view),
`availability.py:81-90` and `:132-141`

`/availability` and `/month-density` filter `slot_occupancy` by
`resource_id IN (...)` (can use `idx_slots_resource_id`) **and** a `starts_at`
range — which has no supporting index, so the time window isn't cheaply
selective. See P8.

---

## P8 — Missing indexes for common filters
**File:** `supabase/schema.sql:36-114`

- **`slots(starts_at)`** — every availability / month-density / calendar query
  filters a `starts_at` range; only `slots(resource_id)` is indexed. **Most
  impactful missing index.**
- **`bookings(client_id)`** — `_client_profile` filters `client_id`
  (`owner.py:185`); only `client_email` is indexed.
- Functional index on `resources((metadata->>'service_id'))` — only helps once
  the P5 full-table scans are replaced with real filters.

**Fix:** add `idx_slots_starts_at` and `idx_bookings_client_id` (idempotent,
schema is add-only for new indexes).

---

## P9 — Fresh Supabase client per request; serial sync calls
**File:** `backend/app/db.py:19-32` (`get_user_client`)

`get_user_client(token)` builds a brand-new `create_client(...)` (new httpx
client) on every authenticated read/write — correct to not cache (carries the
user token), but combined with the sync client, the independent `.execute()`
calls within a handler run serially, each a blocking HTTPS round trip with no
HTTP/2 multiplexing (e.g. `providers.py:21-25` reviews→services→providers;
`bookings.py:166-191` booking_slots→slots→reviews).

**Fix (larger):** move hot read paths to `httpx.AsyncClient` + async supabase (or
raw async PostgREST) so independent queries within a request run concurrently;
reuse a pooled connection for service-key reads.

---

## Recommended order (highest leverage first)

1. **P1** — cache the role lookup. One RTT off *every* request, small change.
2. **P8** — add `idx_slots_starts_at` + `idx_bookings_client_id`. Cheap,
   high-value for calendar/availability.
3. **P2 + P6** — kill the bookings N+1 (embed names / batch) and add a client
   cache; also drop the double search call.
4. **P4** — read `user_metadata` from the JWT instead of the admin API.
5. **P3 + P5** — batch owner-screening queries and end the full-table scans.
6. **P9** — async/parallel the in-request query fan-out (biggest change, do last).
