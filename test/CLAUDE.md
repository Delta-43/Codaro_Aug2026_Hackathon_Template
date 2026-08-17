# test/ — stack + API tests

## Role

This directory is the **exclusive write workspace of the `test-writer`
agent** (`.claude/agents/test-writer.md`). It reads the rest of the repo but
only ever creates/modifies files here. `test-runner`
(`.claude/agents/test-runner.md`) executes what's in here and reports
results — it never modifies anything, including inside this folder. See the
3-agent pipeline described in the root [CLAUDE.md](../CLAUDE.md).

If you're a human (or any other session) adding tests by hand, follow the
same structure so the pipeline keeps working.

## Structure

```
test/
  conftest.py               # puts backend/ on sys.path so `from app.db import ...` resolves
  pytest.ini                # rootdir marker for the suite (testpaths = backend e2e)
  requirements-test.txt     # test-only deps (pytest, httpx, anyio)
  fixtures/
    domain.config.test.json # neutral pivot file used instead of the repo's real one
  backend/                  # offline tests (pure units + FastAPI TestClient + in-memory Supabase)
    conftest.py             # fakes wiring, config override, startup neutralisation, AUTH override
    fakes.py                # FakeSupabase: fluent PostgREST chain, all tables + party-size occupancy
    helpers.py              # row builders (make_provider/service/resource/slot/booking/catalog)
    # --- pure unit tests (no Supabase, no network — the backbone) ---
    test_serialize.py       # serialize.py: every serializer's key set; slot/booking status; iso_utc
    test_resolve_selection.py  # bookings._resolve_selection: all branches -> ApiError code
    test_errors.py          # errors.api_error status/code mapping
    test_rules.py           # rules.py: window/capacity + effective_service_rules + within_cutoff
    # --- integration tests (real endpoints, fake Supabase, stubbed auth) ---
    test_health_config.py   # /health, /config, config-pivot behaviour
    test_resources.py       # /resources reads + owner CRUD + analytics (owner-scoped) + /{id}/bookings
    test_slots.py           # /slots + /slots/occupancy + owner CRUD + buffer rule
    test_bookings.py        # create/list(scope)/get/reschedule/cancel/review + cutoff/capacity
    test_providers.py       # /providers discovery (search/by-code) + follow/unfollow + owner create/patch/mine
    test_services.py        # /services reads + derived resourceIds + owner create/patch
    test_availability.py    # /availability + /month-density
    test_me.py              # GET/PATCH /me
    test_frontend_contract.py  # frontend/src/api paths + error codes vs the live route table
  e2e/
    conftest.py             # session-scoped autouse teardown: reseeds the default `fleet` vertical after the e2e session (gated on SUPABASE_URL + SUPABASE_ANON_KEY)
    test_live_api.py        # opt-in smoke tests against a running stack + real Supabase Auth
```

### Auth in the offline suite

Endpoints are now gated by Supabase-JWT dependencies (`require_user`,
`require_owner`, `optional_user`). Real verification needs the project's JWT
secret and a JWKS fetch, so the `auth` fixture in `backend/conftest.py` overrides
those FastAPI dependencies via `app.dependency_overrides` and lets a test run as
a chosen identity:

```python
def test_x(client, db, auth):
    auth(role="owner")           # or auth(role="client"), auth(anon=True), auth(email=...)
```

`require_owner` is **not** stubbed — it depends on the overridden `require_user`,
so the real owner-gating (`is_owner`) still runs; only token verification is
replaced. Tests that omit the `auth` fixture hit the real `require_user`, which
returns 401 for the missing header (used to assert the 401 path). The
user-scoped RLS client (`get_user_client`) is patched to the same in-memory
`FakeSupabase` — RLS itself is not simulated offline; it's covered by the live
suite.

## How to run (update this section whenever the suite changes)

**Backend suite (offline — this is what CI runs):**

```bash
python -m pip install -r backend/requirements.txt -r test/requirements-test.txt
python -m pytest test/backend -q          # from the repo root
```

No Supabase, no network and no `SUPABASE_*` credentials are needed: the
suite injects an in-memory fake Supabase client and neutralises the
FastAPI startup hooks (`create_tables_if_configured`, `seed_if_empty`).
`backend/` is put on `sys.path` by `test/conftest.py`, so the backend's
absolute imports (`from app.db import ...`, `from seed import ...`) resolve
no matter which directory pytest is invoked from. Running `pytest` from
inside `test/`, or `pytest /abs/path/to/test`, works too.

A ready-made virtualenv lives at `test/.venv` (git-ignored); recreate it with:

```bash
python3 -m venv test/.venv
test/.venv/bin/pip install -r backend/requirements.txt -r test/requirements-test.txt
test/.venv/bin/python -m pytest test/backend -q
```

**Live e2e suite (opt-in, needs a running stack + real Supabase Auth):**

```bash
make start
export SUPABASE_URL=... SUPABASE_ANON_KEY=...          # to mint a real JWT
E2E_BASE_URL=http://localhost:8000 python -m pytest test/e2e -q
```

The suite signs the seeded demo user in through Supabase Auth
(`demo@codaro.app` / `Codaro-Demo-2026`, override with `E2E_DEMO_EMAIL` /
`E2E_DEMO_PASSWORD`), attaches the returned JWT as `Authorization: Bearer`, and
then drives `/providers` (7 in the fleet seed, incl. `VISTULA-4471`),
`/services`, `/availability`, `/me`, `/bookings?scope=all` (6 seeded for the demo
user), a create → reschedule → cancel lifecycle on a far-future slot, and
follow/unfollow. It **skips unless both `SUPABASE_URL` and `SUPABASE_ANON_KEY`
are set** (the backend base URL defaults to `http://localhost:8000`; override
with `E2E_BASE_URL`), so `pytest test/` stays green offline.

The e2e suite **mutates the real Supabase project** (it can switch the demo
vertical and create/cancel a booking). `test/e2e/conftest.py` installs a
`scope="session", autouse=True` teardown that reseeds the default `fleet`
vertical *after* the whole e2e session, so the project is always left clean even
if a test switched verticals mid-run. It reseeds by importing the backend seeder
(`import seed; seed.seed_vertical("fleet")` — `backend/` is already on
`sys.path`) and only *after* the tests (they assert against the current seed
counts, so it must not run up front). It is gated on the same
`SUPABASE_URL` + `SUPABASE_ANON_KEY` env, so it is a no-op when the live suite is
skipped and never fails collection when the env is absent.

In the dev container the env lives in the backend container, so run e2e there:

```bash
docker exec -w /workspace/test codarohackathon-backend-1 python3 -m pytest e2e -q
docker exec -w /workspace/backend codarohackathon-backend-1 \
  python3 -c "import seed; print(seed.active_vertical())"   # -> fleet after the run
```

**Frontend unit tests:** none — the frontend has no test runner wired up
(`frontend/package.json` has no `test` script). The practical part of the
stack check is automated instead in `test/backend/test_frontend_contract.py`,
which parses `frontend/src/api/index.ts` + `src/api/errors.ts` and asserts every
path the UI calls exists on the FastAPI app (method-aware) and that the
`ApiErrorCode` union matches the backend's `app.errors`.

## Conventions for this suite

- **Pure unit tests** (`test_serialize.py`, `test_resolve_selection.py`,
  `test_errors.py`, and the `effective_service_rules`/`within_cutoff` parts of
  `test_rules.py`) are the backbone: they import the functions directly, touch
  no Supabase and no network, and MUST stay green. Keep them independent of
  `domain.config.json` specifics (or use the `domain_config` override) so they
  don't drift on a pivot.
- **Integration tests** hit the **real endpoints** through `TestClient`; only
  the Supabase client and the auth dependencies are faked. Never re-implement
  router or rules logic in a test.
- `fakes.FakeSupabase` recomputes `slot_occupancy` on every read exactly like
  the SQL view — **summing `party_size` across confirmed bookings via
  `booking_slots`** — so multi-slot + shared-capacity behaviour is genuinely
  exercised rather than stubbed. It also enforces composite primary keys
  (`follows`, `booking_slots`) so router idempotency is real.
- Rule values come from a per-test copy of the config: use the
  `domain_config(rules={...})` fixture to prove behaviour is config-driven,
  and `use_real_config` to assert against the repo's actual
  `domain.config.json`.
- This directory must not modify anything outside `test/`.

## Coverage target (from the README's Track B checklist)

- Resource and Slot — CRUD via `/resources`, `/slots`
- Booking and Confirmation — `POST /bookings`
- Change and Cancellation — `/bookings/{id}/reschedule`, `/bookings/{id}/cancel`
- Availability View — `/slots/occupancy`
- Status and History — `bookings.status` + append-only `bookings.history`
- Config-driven behavior — `GET /config` reflects `domain.config.json`, and
  rule values (e.g. `cancellationWindowHours`) are actually enforced, not
  just returned.
- **Auth (branch `16-auth-system`)** — protected endpoints reject a missing
  token (401 — asserted by omitting the `auth` fixture), owner endpoints reject
  a non-owner role (403 — `auth(role="client")`), and identity is read from the
  verified token rather than the body (create asserts `booking.userId ==` the
  token user). JWT signature verification and live RLS are stubbed offline and
  covered against a real project by the e2e suite.

## Current state

`python -m pytest test/backend -q` from the repo root: **311 passed**
(0 failures, 0 xfail). `python -m pytest test/` adds the 8 live e2e tests, which
skip without `SUPABASE_URL`/`SUPABASE_ANON_KEY`.

Client-reputation coverage (the `client_reviews` table + businesses rating
customers): `FakeSupabase.BASE_TABLES` now includes `client_reviews` (defaults +
required cols + booking/provider delete-cascade), and `helpers.make_client_review`
builds rows. `test_bookings.py` covers `POST /bookings/{id}/client-review` —
owner rates a completed booking (200 + one persisted row), rating clamp (9→5),
404 for an upcoming booking, 401/403(client)/403(other-owner) gating, and a
re-review replacing the prior row. `test_me.py` covers `GET /me/reputation` —
empty default `{score:0,count:0,reviews:[]}`, two reviews aggregated to the mean
`score` with `author`=provider name newest-first, and scoping to the signed-in
user. `test_owner.py`'s request `client` card asserts the two new keys
(`rating`/`reviewCount`, defaulting to `None`/`0`) and reflects a present
`client_review`. `test_providers.py` covers the public `GET /providers/{id}/reviews`
(newest-first, author from the reviewer's self-chosen public display name in
Supabase `user_metadata`, falling back to `"Guest"` when unknown — never the
email; offline yields `"Guest"` because the `FakeSupabase` has no `auth.admin`).

Business-mode (owner/provider) coverage:
- `test_serialize.py` — `serialize_service` now emits `autoApprove`
  (`SERVICE_KEYS` updated; default `True`, `False` from `metadata.auto_approve`);
  `effective_booking_status` passes `pending`/`rejected` through unchanged
  (a past-end pending is NOT auto-completed).
- `test_services.py` — `SERVICE_KEYS` updated; owner create with
  `autoApprove:false` serializes back false and persists to `services.metadata`
  (not a column); PATCH toggling `autoApprove` merges metadata (keeps
  `image_url`).
- `test_bookings.py` — create on a manual-approve service (`auto_approve=false`)
  lands `pending` (holds no capacity); owner `POST /bookings/{id}/approve`
  (pending→confirmed, re-checks capacity → `SLOT_UNAVAILABLE`, 400 if not
  pending) and `/reject` (pending→rejected, idempotent, 400 if confirmed), each
  gated 401/403(client)/403(other-owner); a rejected future booking is excluded
  from `scope=upcoming` but present in `scope=all`.
- `test_owner.py` (new) — `/owner/dashboard` (shape + per-currency revenue
  buckets with a dominant-currency headline, count-weighted satisfaction pooled
  across all the owner's providers, pending count/requests, own-provider scope),
  `/owner/services` (serialized Service + `providerName` + `stats`),
  `/owner/requests` (pending-only + `client` screening card, degrading to the
  email-local-part display name / `memberSinceUtc=None` since `FakeSupabase` has
  no `auth.admin`), `/owner/calendar` (confirmed/completed only, sorted, default
  current month), all 401/403-gated. `owner_router` is wired into
  `conftest._SUPABASE_MODULES`.

Owner/admin DELETE coverage (the metadata-linked cascade + the PATCH-merge fix):
- `test_providers.py` — `DELETE /providers/{id}`: 401/403(client)/404/403(other
  owner) gating, 204 happy path, FK cascade to services/follows, and the
  router-driven removal of the provider's **metadata-linked** resources (no FK)
  taking their slots→bookings→booking_slots with them; a second owned provider's
  resources are left intact.
- `test_services.py` — `DELETE /services/{id}`: same gating matrix + 204, and the
  metadata-linked resource (+ slot/booking cascade) removed while an unrelated
  service's resource survives.
- `test_resources.py` — `DELETE /resources/{id}`: gating matrix + 204 + FK
  cascade to slots/bookings; plus `update_resource` PATCH now **merges** metadata
  (`{"capacity": 4}` keeps owner_id/service_id) rather than replacing it.

Note: `services.py` does a user-scoped write (`get_user_client`) for owner
create/patch, so `services_router` is registered in `conftest._USER_CLIENT_MODULES`
alongside the other RLS-writing routers — without it the fake user client isn't
injected and the owner-write tests hit the network.

Rewritten for the richer `Provider → Service → Resource → Slot → Booking → User`
domain and the camelCase wire shapes (the frontend contract in
`frontend/src/types/domain.ts`), and for Supabase-Auth gating.

**Pure unit tests (offline backbone, ~90 tests):**
- `serialize.py` — every serializer's exact key set + shape (Provider/Service/
  Resource/Slot/Booking/User), the `derive_slot_status` ladder
  (past→blocked→full→partial→available), `effective_booking_status`
  (past-confirmed→completed, cancelled sticks, rescheduled→confirmed), and
  `iso_utc` trailing-`Z`/millisecond formatting + offset normalisation.
- `bookings._resolve_selection` — every branch, asserting the raised
  `HTTPException.detail['code']`: empty/`INVALID_RANGE`, unknown/`NOT_FOUND`,
  cross-resource, min/max count, non-contiguity, past/blocked slot, party>cap
  (`CAPACITY_EXCEEDED`), slot-just-taken (`SLOT_UNAVAILABLE` + `slotId` detail),
  and the reschedule credit-back path.
- `errors.api_error` — code→status mapping + `{code,message,details?}` envelope.
- `rules.effective_service_rules` (service-wins > global-wins > hard-default) and
  `within_cutoff` (boundary inclusive), plus the retained `check_capacity` /
  `check_cancellation_window` config-driven tests.

**Integration tests (real endpoints, fake Supabase, stubbed auth):**
`/health` + `/config` (pivot mid-test + `POST /config/reload`); `/resources`
(public reads, service filter/active, owner create returning a **serialized
single Resource** with the `owner_id` stamp asserted via the stored row,
`PATCH` returning a serialized object incl. the empty-patch path, `analytics`,
401/403 gating); `/slots` (reads, `/occupancy` summing
party size + excluding cancelled, owner create deriving `ends_at`/`capacity`
from config, buffer rule 409, metadata 422, `PATCH`, `DELETE` 204 + cascade);
`/bookings` (create → single camelCase Booking scoped to the token, capacity
`SLOT_UNAVAILABLE`/`CAPACITY_EXCEEDED`, unknown slot/service 404, multi-slot
contiguity + price, `scope=upcoming|past|all`, get, reschedule incl. cutoff +
credit-back, idempotent cancel, owner cutoff override, review only when
completed); `/providers` (search text/category/rating, by-code, follow/unfollow
idempotent + pin-to-top; owner `POST` returning a serialized Provider that
stamps `owner_id` from the token, `PATCH` of columns + presentational metadata,
`GET /mine` filtered to the owner's own providers, 401/403 gating);
`/services` (derived `resourceIds`; owner `POST` under a provider with the
per-service rule columns persisted, `PATCH` of columns + `imageUrl`→metadata,
401/403 gating); `/availability` +
`/month-density`; `/me` (GET/PATCH). `test_frontend_contract.py` checks the
`frontend/src/api` paths + error-code union against the live route table.

The live e2e suite signs in the demo user via Supabase Auth and drives the real
stack (providers/services/availability/me/bookings + a create→reschedule→cancel
lifecycle + follow/unfollow); see the run section above.
