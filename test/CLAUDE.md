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
  backend/                  # offline API tests (FastAPI TestClient + in-memory Supabase)
    conftest.py             # fakes wiring, config override, startup neutralisation
    fakes.py                # FakeSupabase: the fluent PostgREST chain, in memory
    helpers.py              # row builders (make_resource / make_slot / make_booking)
    test_health_config.py   # /health, /config, config-pivot behaviour
    test_rules.py           # rules.py unit tests (cancellation window, capacity)
    test_resources.py       # /resources CRUD
    test_slots.py           # /slots + /slots/occupancy
    test_bookings.py        # create / cancel / reschedule / list + end-to-end flow
    test_frontend_contract.py  # frontend/lib/api.ts paths + types vs the live route table
  e2e/
    test_live_api.py        # opt-in smoke tests against a running stack
```

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

**Live e2e suite (opt-in, needs a running stack + real Supabase):**

```bash
make start
E2E_BASE_URL=http://localhost:8000 python -m pytest test/e2e -q
```

Without `E2E_BASE_URL` these tests skip, so `pytest test/` stays green
offline.

**Frontend unit tests:** none — the frontend has no test runner wired up
(`frontend/package.json` has no `test` script). The practical part of the
stack check is automated instead in `test/backend/test_frontend_contract.py`,
which parses `frontend/lib/api.ts` / `lib/domain.tsx` and asserts every path
and response field the UI expects actually exists on the FastAPI app.

## Conventions for this suite

- Tests hit the **real endpoints** through `TestClient`; only the Supabase
  client is faked. Never re-implement router or rules logic in a test.
- `fakes.FakeSupabase` recomputes `slot_occupancy` from `slots` + `bookings`
  on every read, exactly like the SQL view — capacity behaviour is therefore
  genuinely exercised rather than stubbed.
- Rule values come from a per-test copy of the config: use the
  `domain_config(rules={...})` fixture to prove behaviour is config-driven,
  and `use_real_config` to assert against the repo's actual
  `domain.config.json`.
- Known backend bugs are pinned with `@pytest.mark.xfail(reason=...)` (never
  deleted or "fixed" in the test), and each is paired with a
  `*_current_behaviour` test documenting what the API does today. This
  directory must not modify anything outside `test/`.

## Coverage target (from the README's Track B checklist)

- Resource and Slot — CRUD via `/resources`, `/slots`
- Booking and Confirmation — `POST /bookings`
- Change and Cancellation — `/bookings/{id}/reschedule`, `/bookings/{id}/cancel`
- Availability View — `/slots/occupancy`
- Status and History — `bookings.status` + append-only `bookings.history`
- Config-driven behavior — `GET /config` reflects `domain.config.json`, and
  rule values (e.g. `cancellationWindowHours`) are actually enforced, not
  just returned.

## Current state

`python -m pytest test/backend -q` from the repo root: **97 passed,
13 xfailed** (0 failures, exits 0). `python -m pytest test/` adds the 4
live e2e tests, which skip without `E2E_BASE_URL`.

Covered: `/health`, `/config` (including a config pivot mid-test),
`rules.py` (window boundary + `min(capacity, maxBookingsPerSlot)`),
`/resources` list/create/get, `/slots` list/filter/create,
`/slots/occupancy` (counts, cancelled bookings excluded, resource filter),
`/bookings` create/409-at-capacity/404-unknown-slot, cancel (status +
append-only history, 409 inside the window), reschedule (slot move, history
append, 409 on full target / inside window, 404s), `client_email` filtering,
and a full config -> resource -> slot -> book -> reschedule -> cancel flow.

The 13 `xfail`s are **real backend gaps**, not flaky tests — they are the
prioritised input for `TODO.md`:

1. `.single()` on zero rows raises `PGRST116` against real PostgREST, so the
   `if x is None: raise HTTPException(404)` branches in
   `bookings.py` / `resources.py` are unreachable in production (needs
   `maybe_single()` or an `APIError` guard). 3 tests.
2. Raw `dict` payloads (no Pydantic models) turn missing required fields
   into `KeyError`/DB 500s instead of 422s. 4 tests.
3. `datetime.fromisoformat(slot["starts_at"])` yields a naive datetime for a
   timestamp with no offset, and `check_cancellation_window` then raises
   `TypeError`. 2 tests.
4. No status guard on cancel/reschedule — an already-cancelled booking can
   be cancelled again, and rescheduling a booking onto its own slot counts
   the booking against itself and 409s. 2 tests.
5. `POST /slots` doesn't derive `ends_at` from `rules.slotDurationMinutes`,
   and `metaFields` are never validated against payloads. 2 tests.
