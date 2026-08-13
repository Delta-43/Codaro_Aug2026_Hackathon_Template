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

## Suggested structure

```
test/
  backend/     # API tests against backend/app/routers/* (pytest + FastAPI TestClient or httpx)
  frontend/    # component/unit tests (if any)
  e2e/         # full-stack flows: config fetch -> book -> cancel/reschedule
```

## How to run (update this section whenever the suite changes)

- Backend: `pytest test/backend` (requires the backend's dependencies —
  either run inside `backend/.venv` or install `backend/requirements.txt` +
  a test-only `requirements-test.txt` under `test/`).
- Frontend / e2e: not yet defined — add the command here once `test-writer`
  creates suites, so `test-runner` (and any human) can invoke them without
  guessing.

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

Empty — no tests exist yet. This is `test-writer`'s job; nothing here should
be treated as authoritative until it has run.
