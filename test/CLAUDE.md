# test/, stack + API tests

## Role

This directory is the **exclusive write workspace of the `test-writer`
agent** (`.claude/agents/test-writer.md`). It reads the rest of the repo but
only ever creates/modifies files here. `test-runner`
(`.claude/agents/test-runner.md`) executes what's in here and reports
results, it never modifies anything, including inside this folder. See the
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
    fakes.py                # FakeSupabase: fluent PostgREST chain (incl. .is_/multi-key .order),
                            #   all tables (+ entitlements/waitlist_entries/conversations/messages),
                            #   party-size occupancy view, the messages insert-trigger, and a
                            #   seedable auth.admin stub (seed_auth_user)
    helpers.py              # row builders (make_provider/service/resource/slot/booking/
                            #   entitlement/catalog)
    # --- pure unit tests (no Supabase, no network, the backbone) ---
    test_serialize.py       # serialize.py: every serializer's key set; slot/booking status; iso_utc
    test_resolve_selection.py  # bookings._resolve_selection: all branches -> ApiError code
    test_errors.py          # errors.api_error status/code mapping
    test_rules.py           # rules.py: window/capacity + effective_service_rules/config/pricing
                            #   + effective_auto_approve + within_cutoff
    test_config_schema.py   # config_schema: normalize (defaults, v1 aliasing) + validate
    test_pricing.py         # pricing.quote/match_tier: v1 parity, periods, tiers, fees, caps, deposit
    # --- integration tests (real endpoints, fake Supabase, stubbed auth) ---
    test_health_config.py   # /health, /config (normalized tree), owner-gated /config/reload
    test_resources.py       # /resources reads + owner CRUD + analytics (owner-scoped) + /{id}/bookings
    test_slots.py           # /slots + /slots/occupancy + owner CRUD + buffer rule
    test_bookings.py        # create/list(scope)/get/reschedule/cancel/review + cutoff/capacity
    test_providers.py       # /providers discovery (search/by-code) + follow/unfollow + owner create/patch/mine
    test_services.py        # /services reads + derived resourceIds + owner create/patch
    test_service_config_overrides.py  # per-service config overrides:
                            #   validate_overrides + surviving_overrides +
                            #   effective_service_config/_pricing's drop-invalid-block,
                            #   POST/PATCH /services `config` (422), auto_approve vs
                            #   timing.confirmation, + a real booking priced by the
                            #   service's own pricing
    test_availability.py    # /availability + /month-density
    test_me.py              # GET/PATCH /me
    test_messages.py        # /conversations: start (client+owner directions, 403), inbox with
                            #   unread counts + trigger-stamped ordering, thread view, send
                            #   (empty=400), list order + mine flags, mark-read, soft-delete +
                            #   preview repoint. Non-participant scoping is RLS (live suite only).
    test_waitlist.py        # /slots/{id}/waitlist join/leave/my-place (capability + enabled
                            #   gates, bookable/past-slot refusals, idempotent join, queue cap)
                            #   + promote_from_waitlist through the real cancel (pending head-of-
                            #   queue booking; autoPromote:false records only)
    test_frontend_contract.py  # frontend/src/api paths + error codes vs the live route table
                            #   (PATH_LITERAL now also matches /conversations + /owner paths)
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

`require_owner` is **not** stubbed, it depends on the overridden `require_user`,
so the real owner-gating (`is_owner`) still runs; only token verification is
replaced. Tests that omit the `auth` fixture hit the real `require_user`, which
returns 401 for the missing header (used to assert the 401 path). The
user-scoped RLS client (`get_user_client`) is patched to the same in-memory
`FakeSupabase`, RLS itself is not simulated offline; it's covered by the live
suite.

## How to run (update this section whenever the suite changes)

**Backend suite (offline). CI runs `pytest test -q` with coverage:**

```bash
python -m pip install -r backend/requirements.txt -r test/requirements-test.txt
python -m pytest test/backend -q          # from the repo root
```

No Supabase, no network and CI sets dummy `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` so `get_supabase()` does not KeyError on import: the
suite injects an in-memory fake Supabase client and neutralises the
FastAPI startup hook (`create_tables_if_configured`); `seed_if_empty` is no
longer called on startup but is kept inert on the seed module too.
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
(`import seed; seed.seed_vertical("fleet")`, `backend/` is already on
`sys.path`) and only *after* the tests (they assert against the current seed
counts, so it must not run up front). It is gated on the same
`SUPABASE_URL` + `SUPABASE_ANON_KEY` env, so it is a no-op when the live suite is
skipped and never fails collection when the env is absent.

In the dev container the env lives in the backend container, so run e2e there:

```bash
docker exec -w /workspace/test arbor-backend-1 python3 -m pytest e2e -q
docker exec -w /workspace/backend arbor-backend-1 \
  python3 -c "import seed; print(seed.active_vertical())"   # -> fleet after the run
```

**Frontend unit tests:** none, the frontend has no test runner wired up
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
  the SQL view, **summing `party_size` across confirmed bookings via
  `booking_slots`**, so multi-slot + shared-capacity behaviour is genuinely
  exercised rather than stubbed. It also enforces composite primary keys
  (`follows`, `booking_slots`) so router idempotency is real.
- Rule values come from a per-test copy of the config: use the
  `domain_config(rules={...})` fixture to prove behaviour is config-driven,
  and `use_real_config` to assert against the repo's actual
  `domain.config.json`. The fixture writes a **raw** file, so it goes through
  `config_schema.normalize()` + `validate()` on load, a section it sets must be
  a *valid* config, and `domain_config()` returns the raw dict, not the resolved
  tree (wrap it in `normalize()` when you need the resolved one).
- This directory must not modify anything outside `test/`.

## Coverage target (from the root `CLAUDE.md` Track B checklist)

- Resource and Slot: CRUD via `/resources`, `/slots`
- Booking and Confirmation: `POST /bookings`
- Change and Cancellation: `/bookings/{id}/reschedule`, `/bookings/{id}/cancel`
- Availability View: `/slots/occupancy`
- Status and History: `bookings.status` + append-only `bookings.history`
- Config-driven behavior, `GET /config` reflects `domain.config.json`, and
  rule values (e.g. `cancellationWindowHours`) are actually enforced, not
  just returned.
- **Auth (branch `16-auth-system`)**: protected endpoints reject a missing
  token (401, asserted by omitting the `auth` fixture), owner endpoints reject
  a non-owner role (403, `auth(role="client")`), and identity is read from the
  verified token rather than the body (create asserts `booking.userId ==` the
  token user). JWT signature verification and live RLS are stubbed offline and
  covered against a real project by the e2e suite.

## Current state

`python -m pytest test/backend -q` from the repo root: **1260 passed**
(0 failures, **no xfails left**, and **no known gaps pinned**, the four that
were are now asserted as fixed behaviour, see below). `python -m pytest test/` adds the 8 live e2e
tests, which skip without `SUPABASE_URL`/`SUPABASE_ANON_KEY`.

Second review-pass pins (August 2026, +9 tests): `test_waitlist.py`, a skipped
promotion (`metaFields.bookings` requires a field) leaves the head WAITING with
no booking minted (was: stamped `promoted` with `booking_id` None); one freed
seat does not promote a party of 3; a capacity-0 slot refuses the queue
("blocked"); a party larger than the REMAINING seats may join while a party
that still fits is told to book it instead. `test_bookings.py`, reschedule
keeps the `entitlement_id` consume receipt and the plan discount (a pass whose
LAST credit the booking spent still prices it at 0, and cancel still refunds);
approve of a cancelled booking is 400 INVALID_RANGE, not 403; two sequential
`/pay` calls accumulate (precondition matches the prior amount) and a third is
refused; `/return` twice is 400 "already marked returned" with the stamp and
history untouched; a legacy row (`client_id` NULL + `metadata.user_id`) still
lists in GET /bookings, scoped to that user only.

Review-pass regression pins (August 2026), spread across the per-router files:
`_assert_owns_booking` now runs on cancel/reschedule (unrelated owner → 403).
Owner powers hinge on owning the booking's PROVIDER, not the role bit: the
own-provider cutoff waiver covers a walk-in booking the owner recorded under
their own account on their own business (cancel inside the cutoff → 200), while
an owner acting on a booking they made as a customer of ANOTHER owner's business
is a client (cutoff → 409 `CUTOFF_PASSED`), both pinned in `test_bookings.py`;
reschedule repricing keeps `booking.options` add-on lines and refuses a new date
inside `timing.blackouts`; metaFields 422s carry the full ApiError envelope
(`test_resources.py`); `validate()` rejects junk in the three pricing money
paths (`caps.perBookingMinorUnits` / `deposit.value` /
`secondaryRate.amountMinorUnits`); `serialize_service` serves `prerequisites: []`
when the capability is off; entitlement credits are consumed at create and
refunded exactly once on reject/cancel (`credit_refunded` stamp); and
`payment_state` derives a missing currency from the effective pricing chain, not
a hard-coded EUR (`test_rules.py` + an endpoint pin). The `FakeSupabase` grew the
four new tables, the `messages` insert trigger, `.is_`/chained-`.order`, and a
seedable `auth.admin` stub, unknown users still raise, so every degrade path
other tests pin ("Guest" authors, `memberSinceUtc: None`) behaves exactly as
before.

The former `strict=True` xfail pair (`config_schema._enum` raising `TypeError`
on an unhashable value) is **gone**: `_enum` now type-guards
(`isinstance(value, (dict, list, set, bytearray)) or value not in allowed`), so
those cases are asserted as real behaviour instead of pinned as a gap, see
"Enum type-guard + distanceBand shape checks" below.

## Per-service config overrides (`test_service_config_overrides.py`, 169 tests)

`validate()` only ever ran on the global `domain.config.json` at load, so the
per-service override blocks (`services.metadata.<block>`, consumed by
`rules.effective_service_config`) reached the pricing and scheduling paths
unvalidated, a service could carry a `pricing` block that quoted real money with
no schema check, and the feature was unreachable anyway, because the API only
wrote `image_url`/`auto_approve` into service metadata. One file covers the whole
seam, schema -> rules -> route -> booking:

- **`config_schema.validate_overrides`**: a valid block in each of the nine
  overridable blocks reports `[]`; `None`/`{}`/unknown top-level keys report `[]`
  without suppressing a sibling block's errors; every enum position, the
  `"percentage"` fee-kind typo, malformed fee descriptors (missing `rateBps` /
  `amountMinorUnits` / `bands`, non-object entry), a bad `booking.party` range and
  a choice-less select option are reported with their path (indexed errors keep
  their `[i]`); all problems come back in one pass; a partial block merges over
  the base instead of replacing it; neither DEFAULTS nor the argument is mutated.
  Also pinned: the function validates any block that exists in `DEFAULTS`
  (including `terms`/`tenancy`), restricting the set is the *router's* job.

  **Attribution is a diff, not a path filter.** `validate_overrides(overrides,
  base=None)` merges onto the deployment's resolved config (`get_config()`,
  passed by `rules.service_override_problems`, `rules.surviving_overrides` and
  `services._config_overrides`; DEFAULTS is only the no-config fallback) and
  keeps exactly the errors the override *introduces*, those `validate(base)`
  does not already produce. Both halves are covered:
  - *Already in the base ⇒ blamed on nobody.* Proved by breaking the base
    (`monkeypatch.setitem(DEFAULTS["tenancy"], "mode", "single")`, and a
    malformed `DEFAULTS["timing"]["blackouts"]`): a `pricing`-only override hears
    nothing about `tenancy.providerCode`, and **neither does a caller that
    declares `tenancy` itself**, a pre-existing defect of the deployment is not
    the override's fault (the load path is what must catch it, re-asserted in the
    same test). New problems raised by the same call still surface.
  - *Introduced by the override ⇒ reported even when it names another block.*
    The motivating case: on a `capabilities.payments: false` +
    `payments.flow: "none"` deployment, an override declaring only
    `payments.flow: "prepay"` produces the `capabilities.payments is false ...`
    error. The old leading-segment filter dropped it as "undeclared", so the
    write gate accepted the contradiction `validate()` exists to prevent. Covered
    at unit level and through the real `POST /services` (422 naming it, nothing
    written; the same block is a 200 on a payments-enabled deployment), plus the
    reverse direction (declaring `capabilities` alone) and a broken-base window
    whose *new* bad entry, a different list, or index 1 of the same list, is
    still reported.
  - *An explicit `base` differs from the DEFAULTS fallback.*
    `location.modes: ["remote"]` is rejected against DEFAULTS (whose
    `location.default` is `on_site`) and clean against a deployment that is
    already remote-first; passing `DEFAULTS`/`None` explicitly reproduces the
    fallback.
- **`rules.service_overrides` / `service_override_problems`**: only dict-valued
  keys in `OVERRIDABLE_BLOCKS` count (`image_url`, `auto_approve`, a `tenancy` or
  `terms` block and a non-dict `pricing` are all ignored, and an ignored block is
  neither validated nor merged).
- **`rules.surviving_overrides`**: the single source of truth for "which of a
  service's overrides actually apply", read by BOTH `effective_service_config`
  and `effective_service_pricing` (they used to decide independently and
  disagreed). Covered directly: a clean service gets every declared block back
  (identical to `service_overrides`), an invalid one loses only the offending
  block (including when the error is indexed, `pricing.fees[0].kind`), a service
  declaring nothing returns `{}` **without calling the validator at all** (spy,
  it runs twice per booking; the spies take `(overrides, base=None)` since the
  resolvers pass the deployment config), the drop is logged once naming the
  service, and
  stubbing the function moves both resolvers at once (the regression guard).
- **`rules.effective_service_config`**: per-block isolation (an invalid
  `pricing` is dropped while a valid `timing` in the SAME service still applies),
  the fallback equals `get_config()[block]` exactly (equal to, not identical
  with), a clean override still merges, `service_override_problems` matches
  exactly the set of dropped blocks, the warning is emitted once on the
  `app.rules` logger naming the service id + the problem (`caplog`), a clean
  service logs nothing, and a service declaring **no** blocks never calls the
  validator at all (spy on `app_rules.validate_overrides`, it runs on the hot
  booking path). The cost invariant is the zero-call one only: a *declaring*
  service is no longer pinned to an exact call count (`validate()` legitimately
  runs twice per `validate_overrides`, baseline + merged); the spy asserts the
  arguments instead, i.e. that the resolver passes `get_config()` as the base.
- **Routes**: `POST /services` with a valid `config` persists the blocks into
  metadata alongside `image_url`/`auto_approve` without widening the wire
  `Service` shape; an invalid block is a **422** `VALIDATION_ERROR` with the
  problems in `detail.details.problems` and **nothing written**; an unknown block
  is a 422 listing the allowed set; **`tenancy` is rejected as an unknown block**
  (a tenant must not set its own commission), including next to a valid block;
  401/403 gating still applies and runs *before* config validation. `PATCH`
  replaces a block **wholesale** (a removed key really goes) while untouched
  blocks, `image_url` and `auto_approve` survive, config can be patched alongside
  columns, and a 422 leaves the row byte-identical (not even the valid `name` in
  the same request lands).
- **The marketplace claim, end to end**: two services created through the API
  with identical `priceMinorUnits` columns, one declaring
  `pricing.rate.per: "night"`, produce bookings of 9900 vs 1000 minor units
  through the real `POST /bookings`; a configured flat fee + percent deposit show
  up in `price_breakdown`/`deposit_minor_units`; PATCHing a new pricing block
  reprices the *next* booking while the earlier one keeps its quote; and a
  service written with a bad block *before* the gate existed is still bookable,
  priced by the global block.

### The four former known gaps, now asserted as FIXED

They used to be pinned as warts with a docstring saying what to change; the
backend changed, so each is a positive assertion now (the docstrings say what the
old behaviour was, so a regression is recognisable):

1. **Season/blackout errors carry a dotted path.** `validate` walks `seasons` and
   `blackouts` separately and emits `timing.<list>[i] needs startDate and
   endDate` (it used to be one pathless sentence covering both lists, which the
   block-attribution filter dropped). Covered in
   `test_service_config_overrides.py`, both lists x seven malformed shapes,
   per-entry indices in a multi-entry list, the two lists indexed independently,
   a malformed window not suppressing the block's other problems, and a
   `monkeypatch`ed broken DEFAULTS proving the error is still only blamed on a
   caller that declared `timing`, and at the load path in
   `test_config_schema.py` (same matrix through `validate` + `load_config`
   raising `ConfigError`). `POST /services` with a malformed `seasons`/
   `blackouts` window is now one of the 422 cases.
2. **`effective_service_pricing` reads the SURVIVING block.** A service with
   `price_minor_units = 4500` and a typo'd `pricing` block prices at **4500**,
   pinned as exactly that, and explicitly not 0 (the old silent-zero: the
   rejected block's `rate.amountMinorUnits` suppressed the legacy-column
   fold-in) and not the block's bogus 9900. Siblings: no column → the global
   amount (the fix must not invent a price), a *valid* block still beating the
   columns, and the legacy-row booking test now pins `priceMinorUnits == 1000`
   instead of merely `!= 9900`.
3. **`auto_approve` is only written when it is sent.**
   `ServiceCreate.auto_approve` is `bool | None = None`, so a bare `POST
   /services` writes `metadata == {}` (it used to stamp `auto_approve: true`,
   which shadowed `timing.confirmation` forever), an explicit `true`/`false`
   writes the key, and a service created with
   `config={"timing": {"confirmation": "request_approve"}}` and no `autoApprove`
   lands a real booking as **`pending`**. An explicit `autoApprove: true`
   alongside the override still wins.
4. **`serialize_service` uses `effective_auto_approve(row)`.** Wire and booking
   path agree: `timing.confirmation: request_approve` + no `auto_approve` key →
   `autoApprove: false`; an explicit key still wins; a plain service is still
   `true`; an *invalid* `timing` override falls back to `true`. Same three cases
   at unit level in `test_serialize.py` (plus the global-`confirmation` case via
   `domain_config`), and a subprocess test pinning that `app.serialize`'s new
   `from app.rules import ...` is not a circular import.

**The 3+4 pairing, end to end** (`test_the_wire_and_the_booking_path_agree_on_a_by_request_service`)
- a service created with only the confirmation override reports
`autoApprove: false` on `GET /services/{id}` **and** produces a `pending`
booking through the real `POST /bookings` (persisted as `pending`, holding no
capacity per `/slots/occupancy`). Before the fix both halves were wrong in the
same direction, so neither alone would have caught it.

## Domain config v2 coverage

v2 (`backend/app/config_schema.py` + `backend/app/pricing.py`) made three
deliberate contract changes; the suite was updated to reflect them rather than
to preserve the old assertions.

1. **`/config` serves the NORMALIZED tree, not the file verbatim.**
   `test_health_config.py` no longer asserts dict equality against the raw file.
   `test_config_serves_the_normalized_tree_of_the_file_it_was_pointed_at` walks
   the declared file recursively and asserts every value *survives*
   normalization (normalization may only add defaults), plus that every
   `DEFAULTS` block got filled in for the v1 fixture.
   `test_repo_config_endpoint_matches_the_file_on_disk` compares against
   `normalize(json.load(file))` with the derived `search`/`discovery` facet maps
   stripped from both sides, and a sibling test pins that `domain.config.json`
   is a **normalize fixpoint** (so the file an operator reads is exactly what
   the engine resolves).
2. **`POST /config/reload` is owner-gated and validates before swapping.**
   The two reload tests now take the `auth` fixture and run `auth(role="owner")`.
   New: 401 with no token, 403 for a signed-in client, 200 for an owner, and a
   422 `VALIDATION_ERROR` for a broken file, asserting every problem is listed
   at once AND that the previously cached good config is still served afterwards
   (a bad file must not take the app down). Malformed JSON is a 422 too, not a 500.
3. **`maxBookingsPerSlot: 0` is now an invalid config.** The parametrized
   `test_capacity_uses_min_of_row_capacity_and_config` case that wrote 0 into a
   config file was split in two: one test calls `config_schema.validate` directly
   to prove 0 is rejected at load, the other calls the `rules._capacity`
   validator directly to keep pinning the `min(capacity, max_per_slot)`
   arithmetic without an unloadable file.

New coverage added for v2:

- **`test_config_schema.py`** (235 tests), `normalize`: a v1-only file resolves
  and stays valid, every v2 block is filled from `DEFAULTS`, partial blocks merge
  key-by-key, **lists replace rather than merge**, `DEFAULTS`/input are never
  mutated, and `normalize` is idempotent on `{}`, the fixture and both shipped
  configs (which are also asserted to be fixpoints). The `rules` <-> `timing`
  alias is pinned **in both directions** for all five keys with the precedence
  explicit-`timing` -> explicit-`rules` -> default, and `search.facets` (3 keys)
  <-> `discovery.facets` (5 keys) likewise, including that a v2-only facet never
  leaks into the v1 shape. `tenancy.selfOnboarding` defaults to `mode == "multi"`
  and an explicit value is never overwritten. `validate`: reports **all**
  problems at once, every enum path, non-IANA `location.timezone`,
  `location.default` outside `location.modes`, non-3-letter currency,
  `tenancy.mode == "single"` without `providerCode`, `capabilities.payments:false`
  with a non-`none` `payments.flow`, bad/`select`-without-options/missing-key
  metaFields, `"string"` accepted as an alias for `"text"`, and the numeric
  guards (including `maxBookingsPerSlot >= 1`).
- **`test_pricing.py`** (189 tests), `quote`/`match_tier`. v1 parity is
  parametrized over slots x party x price so a refactor cannot silently reprice
  the catalog. Then: every `rate.per` (`booking`/`slot`/`hour`/`day`/`night`/
  `week`/`month`/`person`/`unit`), whole-unit periods billing by **started**
  unit while `hour` stays fractional, `per: "person"` not double-counting,
  `chargePerPerson:false` as the shared-unit case, weighted `person_units`;
  tiers by `partySize`/`timeOfDay` (including a window that **wraps midnight**)/
  `zone`/`bookingIndex`/`subjectField`, config order as precedence, an unknown
  `appliesWhen` clause failing **closed**, and `validFrom`/`validUntil` sales
  windows; secondary rate; fees flat/percent(bps)/distanceBand incl. compounding
  order; `caps.perBookingMinorUnits` (applied after fees, with the negative
  `cap` breakdown line); deposits percent/flat, derived from the *capped* total,
  with **`refundable` selecting how they clamp** (see below); plus coercion robustness (string/null
  amounts, non-dict entries, unknown period) so a hand-edited config cannot 500
  the booking path.
  **Period vs. unit separation** (a fixed bug, re-pinned as the new contract):
  `day`/`night`/`week`/`month` derive their quantity from `duration_minutes`
  ALONE, a `unit_count` in the ctx is ignored (parametrized over all four
  periods x four counts, asserting an identical total *and* breakdown with and
  without it, and that a zero/absent duration still floors at one unit rather
  than falling back to `unit_count`). `per: "unit"` is the only reader of
  `unit_count` (and defaults to 1), and it ignores `duration_minutes` in turn.
  The regression that motivated it, warehouse pallet-space, `rate` 300/unit +
  `secondaryRate` 1000/week, ctx `unit_count=20, duration_minutes=40320`, pins
  BOTH breakdown lines (`base` 6000, `secondary` 4000) and the 10000 total,
  because the old behaviour (20 pallets billed as 20 weeks) can be invisible in
  the total alone.
- **`test_rules.py`**: `effective_service_config` (returns the nine overridable
  blocks and no presentation blocks; `services.metadata.<block>` deep-merges over
  the global block; lists replace; the cached global config is never mutated),
  `effective_service_pricing` (the `price_minor_units`/`currency` columns still
  win, a declared `metadata.pricing` beats them, a partial one lets the columns
  supply the rest), the new dotted config paths behind `_SERVICE_RULE_MAP`
  (price/currency/min/max slots), and `effective_auto_approve`
  (`timing.confirmation` as the default, `metadata.auto_approve` and a
  per-service `metadata.timing.confirmation` as overrides).
- **`test_bookings.py`**: the router's pricing seam through the real endpoint:
  `price_breakdown` (list) + `deposit_minor_units` (int) stamped into booking
  metadata on create, default pricing still matching the v1 formula end to end,
  a service pricing per night / with `chargePerPerson:false` / with a tier /
  with a fee via `services.metadata.pricing`, the global `pricing` block applying
  when the service columns are null, and **reschedule re-quoting** (price,
  currency rewritten over a stale value, breakdown replaced, deposit
  recomputed). Plus `timing.confirmation: "request_approve"` making every new
  booking `pending`, with `metadata.auto_approve` still overriding it.
- **`test_availability.py`**: the `?tz=` -> user timezone ->
  **`location.timezone`** -> UTC fallback chain, using a 23:00 UTC slot that
  lands on the next local day in `Asia/Tokyo`: an anonymous viewer gets the
  business's day, an explicit `?tz=` and a signed-in user's timezone each win
  over it, `/month-density` uses the same chain, a config with no `location`
  block still groups in UTC, a bogus `location.timezone` cannot even load
  (validation), and an unparseable `?tz=` (raw user input) degrades to UTC
  rather than 500.
- **`test_slots.py`**: `slots.py` reads `get_config()["timing"]` now, so
  declaring the slot defaults/buffer on either the v1 `rules` path or the v2
  `timing` path must produce identical slots.

Enforcement coverage added after the v2 pass (three behaviours that were
declared-but-dead and are now live):

- **`timing.leadTimeMinutes` (minimum notice)**: `test_rules.py` unit-tests
  `rules._lead_time` (0/None disables it, a start inside the window raises with
  the configured number **and** the config's `terms.slot` vocabulary in the
  message, a start outside it and a past start), then the same verdicts through
  `apply_rules("booking.create", ...)` parametrized over four config/offset
  pairs, plus that the untouched fixture config leaves the event a no-op and
  that declaring the key on the deprecated v1 `rules` path does **not** enforce
  it (it is not one of the five aliased keys). `test_bookings.py` drives the
  real `POST /bookings`: a 10-minutes-out slot still books on the default
  config (0 = off, so the rule is not a silent behaviour change), a booking
  inside the window is **400 / `INVALID_RANGE`** with the number in the
  message, one outside it is 200, a rejected attempt persists no booking /
  `booking_slots` / occupancy, the same slot flips verdict when only the config
  changes, and `leadTimeMinutes` does **not** gate `/reschedule` (that event
  owns `cancellationWindowHours`).
- **`maxBookingsPerSlot` is `rules.UNDISPATCHED`, not a `booking.create` rule**
 , `test_rules.py` pins `RULES["booking.create"] == {"leadTimeMinutes":
  _lead_time}`, that no event's map contains `maxBookingsPerSlot`, the exact
  contents of `UNDISPATCHED`, that dispatched and undispatched keys are
  disjoint, and the arithmetic that makes the exclusion necessary
  (`_capacity(1, {booked_count: 4, capacity: 8})` raises). `test_bookings.py`
  is the regression that actually protects it: with the shipped
  `maxBookingsPerSlot: 1`, a party of 5 books a capacity-8 slot, and two
  different customers put 4 + 3 heads into the same capacity-8 slot (the second
  is what fails if `_capacity` is ever re-registered), while a party of 8 into
  a 7-seat slot is still `CAPACITY_EXCEEDED`, the row's capacity binds, the
  config number does not.
- **`validate()` now checks the list-of-descriptor blocks**,
  `test_config_schema.py` covers `pricing.fees` (every valid kind; unknown kind
  incl. the motivating `"percentage"` typo; `percent` without/with a negative
  `rateBps`; `distanceBand` with missing/empty `bands`; `flat` with a
  missing/negative `amountMinorUnits`; an omitted kind defaulting to flat;
  non-object entries; every bad entry reported with its index),
  `pricing.deposit.kind`, `payments.schedule[i]` (key/kind/value + non-object),
  `booking.options[i]` (key/type/`select`-without-`choices` + the boolean
  default), `recurrence.patterns[i]`, `entitlements.plans[i]`, and
  `booking.party.min > max`; plus one test that every one of those problems is
  reported in a single pass, and equality assertions pinning `FEE_KINDS` /
  `DEPOSIT_KINDS` / `OPTION_TYPES` / `RECURRENCE_PATTERNS`.
  `test_pricing.py` supplies the motive: `_fee_amount`/`quote` show a
  `kind: "percentage"` fee contributing **0** with no breakdown line (and that
  no unrecognised kind ever fails loudly), so the validator is the only thing
  between a typo and a permanently under-charged booking. `test_health_config.py`
  proves the checks are wired into the load path, not just callable: a fee typo
  + a choice-less select option make `POST /config/reload` a 422 naming both
  entries while the last good config keeps serving.
- **Declared-but-unenforced inventory**: `pricing.caps.perDayMinorUnits`,
  `payments.noShowFee` and `timing.approvalWindowHours` are deliberately inert.
  `test_config_schema.py` pins the *list* rather than any behaviour: each key is
  declared in `DEFAULTS`, is mentioned by **no** non-comment line in
  `backend/app/**` outside `config_schema.py`, and carries an "enforc…" comment
  within the five lines above its declaration. Two controls
  (`timing.leadTimeMinutes` → `rules.py`, `pricing.caps.perBookingMinorUnits` →
  `pricing.py`) prove the source scan can actually see enforcement. If one of
  the three gets wired up the test fails, the signal to move it out of the list
  and write real behaviour tests.

Enum type-guard + `distanceBand` shape checks (two validator fixes made after
the first pass; the tests that encoded the old behaviour were rewritten, not
kept):

- **`_enum` type-guards before the membership test.** `test_config_schema.py`
  asserts the real behaviour now: a dict/list in a *list* enum position
  (`recurrence.patterns: [{"every": "week"}]`) and in a *scalar* one
  (`booking.unitKind`, `pricing.rate.per`, `pricing.model`,
  `booking.granularity`, `payments.flow`, `location.modes[i]`, `tenancy.mode`)
  is a normal listed error naming the path, the guard does not short-circuit the
  rest of the pass, and `config.load_config` raises **`ConfigError`, not
  `TypeError`**, for a file containing one. `test_health_config.py` covers the
  endpoint half: `POST /config/reload` on such a file is the documented **422
  `VALIDATION_ERROR`** (was a 500) with the last-good config still served.
- **`pricing.fees[i].bands` is shape-checked.** `bands` must be a **non-empty
  list**, missing / `None` / `[]` / `"10km"` / `0` / a bare object all produce
  `pricing.fees[i].bands must be a non-empty list for a distanceBand fee` (the
  truthy non-list cases used to pass validation and then price as 0, because
  `pricing._fee_amount` iterates `fee.get("bands") or []`). Each entry must be
  an object with `feeMinorUnits` (int >= 0) and an optional `maxKm` (int >= 0 or
  `null`); every bad entry is reported with its index. A valid multi-band ladder
  ending in the `{"maxKm": null, ...}` catch-all validates clean **and** is
  priced through `pricing.quote` in the same test, a distance beyond every
  numbered band charges the catch-all, a distance inside one charges that band.

**Deposit clamping is branch-selected by `refundable`** (`pricing._deposit`, a
deliberate behaviour change, the old code clamped both kinds to the total). A
NON-refundable deposit is a *prepayment*, so it can never exceed the price; a
refundable one is a *damage bond*, which routinely can (a 300 bond on a 200 tool
hire). `test_pricing.py`'s deposit section covers both: `refundable: False`
clamps a 150% percent and an above-total flat value down to the total (and every
share at or below 100% is untouched by the clamp), while `refundable: True`
returns a 30000 flat bond on a 20000 hire and 1.5x the total for a 150% bond.
Both branches floor at 0 for a negative/unparseable `value` (parametrized over
kind x refundable), `enabled: False` wins over both, and one test pins the
**default** explicitly, `DEFAULTS["pricing"]["deposit"]["refundable"]` is
`true`, so a config enabling a deposit without naming `refundable` gets the
unclamped bond branch (it normalizes, validates clean and prices 30000 on a
20000 total). No booking-level assertion in `test_bookings.py` crosses the
clamp (its deposits are 20% and 50% of the total), so those were left alone.

The point-2 finding is deliberately left pinned as-is: `pricing._fee_amount`
treats a falsy `kind` as flat while `validate` rejects it, the validator is
intentionally stricter than the pricer.

Search-facets coverage (the resolved `search.facets` block on `GET /config` +
`POST /config/reload`, from `main._config_with_facets` → `discovery.search_facets`):
the endpoint resolves each facet as `derived AND declared.get(key, True)`, live
catalog derivation decides what's *possible*, and `domain.config.json`'s optional
`search.facets` can only force a facet OFF (a declared `true`/omitted defers to
derivation). `test_discovery.py` (new) unit-tests `search_facets(db)` against the
offline `FakeSupabase`, empty catalog → `{price:False, distance:False,
rating:True}`, priced service + real coords → all-True, all-free → `price:False`,
missing/zero `metadata.location` → `distance:False`, `any`-semantics over
services/providers, null price treated as free, and `rating` always True.
`test_health_config.py` covers it through the real endpoints: the two config
tests that formerly asserted full file equality now strip the `search` block from
BOTH sides (the on-disk config carries its own `search` now) and assert the three
boolean facet keys separately; `/config` and `/config/reload` expose the map; a
live-catalog test flips `price`/`distance` on by seeding a priced service and a
provider with coordinates; and two override tests prove the AND-merge, a
declared `distance:false` vetoes distance while an omitted `price` still reflects
derivation, and declaring every facet `true` against an empty catalog cannot
conjure price/distance on. Those endpoint tests need the app to read the fake db,
so `app_main` is in `conftest._SUPABASE_MODULES` (main.py does
`from app.db import get_supabase`; without the patch the endpoint hit the invalid
URL and fell back to all-True).

Provider price-from coverage (the `priceFromMinorUnits`/`currency` keys added to
`serialize_provider`): `PROVIDER_KEYS` in both `test_serialize.py` and
`test_providers.py` now include the two keys. `test_serialize.py` asserts the
defaults (`None`/`""` with no aggregate, `0`/`""` for a falsy currency), the
pass-through of `price_from=`/`currency=`, and a discovery-level case that
`discovery.price_from_by_provider` picks the cheapest service's price+currency
across multiple services and `build_provider` threads it onto the wire shape
(absent provider → `None`/`""`). `test_providers.py` covers the same via the real
`/providers` route (cheapest service wins; `null`/`""` for a provider with no
services).

Client-reputation coverage (the `client_reviews` table + businesses rating
customers): `FakeSupabase.BASE_TABLES` now includes `client_reviews` (defaults +
required cols + booking/provider delete-cascade), and `helpers.make_client_review`
builds rows. `test_bookings.py` covers `POST /bookings/{id}/client-review`,
owner rates a completed booking (200 + one persisted row), rating clamp (9→5),
404 for an upcoming booking, 401/403(client)/403(other-owner) gating, and a
re-review replacing the prior row. `test_me.py` covers `GET /me/reputation`,
empty default `{score:0,count:0,reviews:[]}`, two reviews aggregated to the mean
`score` with `author`=provider name newest-first, and scoping to the signed-in
user. `test_owner.py`'s request `client` card asserts the two new keys
(`rating`/`reviewCount`, defaulting to `None`/`0`) and reflects a present
`client_review`. `test_providers.py` covers the public `GET /providers/{id}/reviews`
(newest-first, author from the reviewer's self-chosen public display name in
Supabase `user_metadata`, falling back to `"Guest"` when unknown, never the
email; offline yields `"Guest"` because the `FakeSupabase` has no `auth.admin`).

Business-mode (owner/provider) coverage:
- `test_serialize.py`: `serialize_service` now emits `autoApprove`
  (`SERVICE_KEYS` updated; default `True`, `False` from `metadata.auto_approve`,
  and, since the fix, `False` from a `timing.confirmation: request_approve`
  override with no `auto_approve` key, because it delegates to
  `rules.effective_auto_approve`);
  `effective_booking_status` passes `pending`/`rejected` through unchanged
  (a past-end pending is NOT auto-completed).
- `test_services.py`: `SERVICE_KEYS` updated; owner create with
  `autoApprove:false` serializes back false and persists to `services.metadata`
  (not a column); PATCH toggling `autoApprove` merges metadata (keeps
  `image_url`).
- `test_bookings.py`: create on a manual-approve service (`auto_approve=false`)
  lands `pending` (holds no capacity); owner `POST /bookings/{id}/approve`
  (pending→confirmed, re-checks capacity → `SLOT_UNAVAILABLE`, 400 if not
  pending) and `/reject` (pending→rejected, idempotent, 400 if confirmed), each
  gated 401/403(client)/403(other-owner); a rejected future booking is excluded
  from `scope=upcoming` but present in `scope=all`.
- `test_owner.py` (new), `/owner/dashboard` (shape + per-currency revenue
  buckets with a dominant-currency headline, count-weighted satisfaction pooled
  across all the owner's providers, pending count/requests, own-provider scope),
  `/owner/services` (serialized Service + `providerName` + `stats`),
  `/owner/requests` (pending-only + `client` screening card, degrading to the
  email-local-part display name / `memberSinceUtc=None` since `FakeSupabase` has
  no `auth.admin`), `/owner/calendar` (confirmed/completed only, sorted, default
  current month), all 401/403-gated. `owner_router` is wired into
  `conftest._SUPABASE_MODULES`.

Owner/admin DELETE coverage (the metadata-linked cascade + the PATCH-merge fix):
- `test_providers.py`: `DELETE /providers/{id}`: 401/403(client)/404/403(other
  owner) gating, 204 happy path, FK cascade to services/follows, and the
  router-driven removal of the provider's **metadata-linked** resources (no FK)
  taking their slots→bookings→booking_slots with them; a second owned provider's
  resources are left intact.
- `test_services.py`: `DELETE /services/{id}`: same gating matrix + 204, and the
  metadata-linked resource (+ slot/booking cascade) removed while an unrelated
  service's resource survives.
- `test_resources.py`: `DELETE /resources/{id}`: gating matrix + 204 + FK
  cascade to slots/bookings; plus `update_resource` PATCH now **merges** metadata
  (`{"capacity": 4}` keeps owner_id/service_id) rather than replacing it.

Note: `services.py` does a user-scoped write (`get_user_client`) for owner
create/patch, so `services_router` is registered in `conftest._USER_CLIENT_MODULES`
alongside the other RLS-writing routers, without it the fake user client isn't
injected and the owner-write tests hit the network.

Rewritten for the richer `Provider → Service → Resource → Slot → Booking → User`
domain and the camelCase wire shapes (the frontend contract in
`frontend/src/types/domain.ts`), and for Supabase-Auth gating.

**Pure unit tests (offline backbone, ~90 tests):**
- `serialize.py`: every serializer's exact key set + shape (Provider/Service/
  Resource/Slot/Booking/User), the `derive_slot_status` ladder
  (past→blocked→full→partial→available), `effective_booking_status`
  (past-confirmed→completed, cancelled sticks, rescheduled→confirmed), and
  `iso_utc` trailing-`Z`/millisecond formatting + offset normalisation.
- `bookings._resolve_selection`: every branch, asserting the raised
  `HTTPException.detail['code']`: empty/`INVALID_RANGE`, unknown/`NOT_FOUND`,
  cross-resource, min/max count, non-contiguity, past/blocked slot, party>cap
  (`CAPACITY_EXCEEDED`), slot-just-taken (`SLOT_UNAVAILABLE` + `slotId` detail),
  and the reschedule credit-back path.
- `errors.api_error`: code→status mapping + `{code,message,details?}` envelope.
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
