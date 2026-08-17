# benchmark/ — performance benchmark suite

## Role

Self-contained: this folder has its **own `Makefile`** and its own
`docker-compose.yml`. It never edits the root `Makefile`/`docker-compose.yml`
— both targets here work from *inside* `benchmark/` (`cd benchmark && make
<target>`), so this whole subtree can be developed without touching, and
therefore without merge-conflicting on, root-level files other branches also
touch.

The Makefile has four targets:

```bash
make start                 # start frontend :3000 + backend :8000 (same containers the
                            # root Makefile's `make start` manages — see the comment
                            # atop Makefile)
make benchmark              # ensure the stack + benchmark customer account exist, then
                            # run BOTH the k6 load test + Playwright device/network
                            # matrix into one combined results folder/report
make benchmark-k6           # run ONLY the k6 backend load test, into its own results folder
make benchmark-playwright   # run ONLY the Playwright device/network matrix, into its own results folder
```

`make benchmark`/`make benchmark-k6`/`make benchmark-playwright` (`run.sh` /
`run-k6.sh` / `run-playwright.sh`) run in the foreground — you watch them
live, **Ctrl+C stops them** (no separate stop/logs targets needed). All three
source the same `lib.sh` (stack startup, `wait_for`, bench-user
provisioning, run-folder setup) so the shared setup logic can't drift
between them; each just adds its own tool invocation(s) around that. No tool
here is installed on the host — both benchmarks run as one-off Docker
containers (built from official images), so it's reproducible on any machine
with Docker.

Running the two separately gives each its own `results/<run-name>/` folder
(a new `<seq>`, per the naming scheme below) containing only that tool's raw
file — `k6-events.jsonl` or `playwright-results.json`, never both.
`report/generate_report.py` names its output by which raw files are present
in the folder, so the three modes never collide even if someone later copies
files between run folders by hand: `k6.html` (k6 only), `playwright.html`
(Playwright only), or `combined.html` (`make benchmark` — both raw files,
one report, for comparing backend and frontend numbers from the exact same
run).

1. **Backend load test** (`k6/api-load-test.js`, run via the official
   `grafana/k6` image), **two scenarios in the same run**:
   - `api_browse` — ramps virtual users (0→`PEAK_VUS`, default 10) against the
     read path a search/browse session hits: `/config → /providers →
     /services → /resources → /availability → /slots`, plus (once logged in)
     the authenticated reads a signed-in session also makes: `/me` and
     `/bookings?scope=upcoming`. `providers_search` rotates through a few real
     query shapes each iteration (unfiltered / `category_id=` / `text=`,
     built in `setup()` from the actual seeded providers) instead of always
     hitting the same unfiltered URL.
   - `booking_write` — the write path: create a booking against a real seeded
     slot (`POST /bookings`), then cancel it (`POST /bookings/{id}/cancel`),
     back to back, at a low, separately-tuned VU count (`BOOKING_WRITE_VUS`,
     default `min(5, ceil(PEAK_VUS/10))`) — this is heavier than a read
     (multiple inserts + RLS-scoped writes) and exists to exercise
     slot-capacity locking under concurrency, not to be scaled up with the
     read path. `setup()` only picks slots starting **≥72h out**, comfortably
     past `cancellationCutoffHours` (24h default), so the immediate
     create→cancel round trip is never itself blocked by the cutoff rule. A
     `409` here (`SLOT_UNAVAILABLE`) can be a real, expected signal — two VUs
     landing on the same slot (seeded at `capacity: 1`) is exactly the
     contention this scenario probes, not automatically a bug. `teardown()`
     sweeps every `confirmed` booking left on the bench account at the end of
     the run — an iteration cut off mid-flight by scenario ramp-down (create
     succeeds, cancel never fires) would otherwise permanently consume a
     slot's one seat and degrade every subsequent run; sweeping unconditionally
     is safe because the bench account never carries real bookings of its own
     (see **Test users** below).

   Both scenarios' `setup()` discovers real seeded IDs first, so `make
   reseed` (root Makefile) needs to have run at least once, and both log in
   as the bench customer via a direct Supabase GoTrue password-grant call
   (`POST {SUPABASE_URL}/auth/v1/token?grant_type=password` — the same call
   the frontend's Supabase JS client makes; the backend only *verifies*
   tokens, per `backend/app/auth.py`, it never issues them) — needs
   `SUPABASE_URL`/`SUPABASE_ANON_KEY` in the k6 container's env, which
   `docker-compose.yml`'s `k6` service gets via `env_file: ../backend/.env`
   (same file the backend container itself uses). **This exercises your real,
   hosted Supabase project** (not a local DB) via the backend, which is why
   `PEAK_VUS` defaults to a deliberately modest **10**: past ~20 concurrent
   VUs on the read path alone, Supabase starts terminating HTTP/2 connections
   under load, and the backend's shared `httpx` client surfaces that as a mix
   of `httpx.RemoteProtocolError: ConnectionTerminated`, `WriteError: Broken
   pipe`, and even internal `httpcore`/`h2` `KeyError`s from corrupted stream
   bookkeeping — a real ceiling in the current stack, not a bug in the
   benchmark (or in `bookings.py`/`serialize.py` — the KeyErrors trace
   entirely inside `h2/connection.py`'s stream-id table). `booking_write`'s
   extra write pressure and `api_browse`'s 2 extra authenticated reads per
   iteration both push toward that same ceiling, so it's easier to hit at a
   given `PEAK_VUS` than before. Raise `PEAK_VUS` deliberately
   (`PEAK_VUS=50 make benchmark`) if you want to find/confirm that ceiling
   rather than get a clean run — this is itself a useful data point about the
   stack's current capacity.
2. **Frontend device/network matrix** (`playwright/benchmark.js`, run via a
   small image built from `Dockerfile.playwright`, based on Microsoft's
   `mcr.microsoft.com/playwright` image which ships Chromium prebuilt) —
   loads `/login`, then (after signing in — see **Test users** below)
   `/search`, `/calendar`, `/bookings`, `/account`, across 3 device emulations
   (Desktop, iPhone 13, Pixel 5) × 3 network throttle presets (No throttle,
   4G, Slow 3G — the same numbers as Chrome DevTools' presets), recording
   navigation timing (TTFB, DOMContentLoaded, full load, first contentful
   paint) for each combination.

`report/generate_report.py` (stdlib-only Python) reads whichever raw result
file(s) are in a run folder and writes `combined.html` / `k6.html` /
`playwright.html` (see above) into that **same** folder. Charts are bar
charts (latency percentiles + throughput per endpoint, load time per
device × network per page) plus raw data tables, styled per the repo's
`dataviz` chart conventions (fixed categorical color order, one axis per
chart, light/dark via `prefers-color-scheme`). Chart.js loads from a CDN
inside that file — fine since it's opened locally in a normal browser, never
published anywhere.

## One folder per run — comparing builds

Each run gets its own folder, named for what was actually running:
`results/<commit-date>-<branch>-<short-sha>-<seq>[-dirty]/`, e.g.
`results/2026-08-17-develop-39d7183-001/combined.html`. `report/run_context.py`
computes this once per run (`git log`/`git rev-parse`/`git status` against
the repo — not the current wall-clock time) and writes it to that folder's
`meta.json`, so k6, Playwright, and the report generator all agree on the
same folder for the whole run, and the report's own header always describes
the commit the data was actually collected under (reading `meta.json`, never
re-deriving from current `HEAD` — those can differ if you've committed since).
`<seq>` (`001`, `002`, ...) is the highest existing sequence number for that
exact commit/branch/sha plus one, so running the benchmark several times
against the same commit — nothing new committed in between — still gets a
folder per run instead of colliding on one. A dirty working tree at run time
gets a `-dirty` suffix (and a note in the report header) so a report from
uncommitted changes is never mistaken for a committed state.

Benchmarking a few commits over time leaves a row of distinct folders in
`results/` instead of each run overwriting the last — open two report files
side by side to compare. They aren't committed (`results/*` is gitignored) —
local comparison scratch space, not tracked history. Copy specific ones out
(or drop the gitignore rule) if you want to keep one long-term.

To regenerate a report without re-running the benchmarks (e.g. after tweaking
`generate_report.py`), run it directly — with no argument it regenerates the
most recently modified run folder; give it a path to target an older one:

```bash
python3 report/generate_report.py                       # most recent run
python3 report/generate_report.py results/2026-08-15-develop-abc1234-001
```

## Test users — why a separate account, and how it's created

**The Playwright matrix does NOT log in as `demo@codaro.app`.** That account
is the one seeded by `backend/seed.py` for actual product demos — it owns
real seed bookings, a review, a follow. Logging the benchmark into it would
mix benchmark session activity into that data, and if the benchmark ever
grows write flows (creating/cancelling a booking) it would mutate the demo
account other people look at.

Instead, `create_bench_users.py` provisions a dedicated, blank-slate
**customer** account — `bench-customer-1@codaro.bench` /
`Codaro-Bench-2026` — the same way `seed.py` creates the demo user (same
Supabase admin-API call, `db.auth.admin.create_user(...)`, same
`user_metadata.role` field the backend's role check reads), just with
`role: "client"` always. It never creates an `owner`/business account —
there's no benchmark scenario that needs one yet, since nothing here drives
the owner dashboard.

It's idempotent (checks `auth.admin.list_users()` for the email first) and,
unlike `seed.py`'s reseed behaviour, **never resets an existing bench user's
metadata** on its own — if the account already exists, it's left alone.
`lib.sh`'s `ensure_bench_user` wraps the call; every entry script (`run.sh`,
`run-k6.sh`, `run-playwright.sh`) calls it right after confirming the app
stack is up (so whichever tool runs next has an account to log into), and
`run.sh`/`run-k6.sh` call it again right after the k6 step — `booking_write`'s
`teardown()` (`k6/api-load-test.js`) erases the account entirely via `DELETE
/me` at the end of every run (so cancelled-booking history from
create→cancel round trips never survives past one run, see **Caveats**
below), so the account genuinely doesn't exist afterwards until something
calls `ensure_bench_user` again — either that second call in the same
script, or the next script's own call at startup (a `make
benchmark-playwright` run right after a `make benchmark-k6` run still finds
the account there). There's no separate Makefile target for any of this,
it's just part of what `make benchmark`/`make benchmark-k6`/`make
benchmark-playwright` do.

It runs inside the **backend container** (`docker compose exec backend
python /workspace/benchmark/create_bench_users.py`) because that's where the
`supabase` Python package and `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` (from
`backend/.env`) already are — no new dependencies, no separate credentials
file.

Multiple bench accounts: set `BENCH_USER_COUNT=3` before running
`create_bench_users.py` directly (`docker compose -f ../docker-compose.yml
--project-directory .. exec backend python /workspace/benchmark/create_bench_users.py`)
to provision `bench-customer-1/2/3@codaro.bench` — only useful if you
parallelize the Playwright matrix across devices later (right now devices
run sequentially and share one account fine). `playwright/benchmark.js`
picks which one via `BENCH_EMAIL`/`BENCH_PASSWORD` (defaults to customer 1).

## Caveats

- **Slow 3G against the dev bundle will often time out at the default 45s**
  (`NAV_TIMEOUT_MS`) — the unminified Next dev bundle is large enough that
  500Kbps genuinely can't load it that fast. That's a real finding (shown as
  a "FAILED" row + counted in the failure note under the frontend table), not
  a bug in the benchmark. Raise the timeout (`NAV_TIMEOUT_MS=120000 make
  benchmark`) if you'd rather see the actual tail load time than a cutoff —
  it trades a longer run for that.
- `network_mode: host` (in `docker-compose.yml`) is how the containers reach
  `localhost:8000`/`:3000` as a real client would — this is native Linux
  Docker networking and does **not** work unmodified on Docker Desktop
  (Mac/Windows).
- `make start` (root or here) runs the frontend with `npm run dev`
  (hot-reload dev server, not a production build), so absolute numbers here
  reflect dev-mode performance, not what a deployed build would measure.
  Comparisons *between* devices/networks/endpoints within one report are
  still meaningful; comparing across a rebuild of the frontend/backend images
  is not, since Next dev compiles routes lazily (`benchmark.js` warms every
  route once before timing to avoid conflating "slow network" with
  "first-time compile").
- The bench customer account has no seed data of its own (no bookings/
  follows) — `/bookings` renders its empty state for Playwright, which is
  fine for measuring load time but means it isn't testing a populated
  dashboard. Use `BENCH_USER_COUNT` + a small setup script if a
  populated-account scenario is ever needed.
- `bookings.client_id` has no DB-level FK/cascade (`supabase/schema.sql`), so
  a cancelled booking's row is never actually removed — only the app-level
  `DELETE /me` GDPR erasure (`backend/app/gdpr.py`) hard-deletes a user's
  bookings. `booking_write`'s create→cancel round trip would otherwise leave
  the bench account's booking history growing by ~2 rows per iteration,
  forever, across every future run — and since `GET /bookings` batches its
  enrichment queries (slot times, provider/service names, reviews) over
  *every* booking the caller has, not just the ones the requested `scope`
  returns, a growing history directly inflates `bookings_list`'s cost and
  failure rate on every subsequent run, silently making runs incomparable
  over time. `teardown()` erasing the account each run is what prevents this
  — don't remove it without another way to reclaim that history.
- The results directory (and each run's subfolder) is `chmod 777`'d by
  `lib.sh`'s `new_run_dir` (called by all three entry scripts) before the
  containers touch it — the k6 and Playwright images run as non-root,
  host-UID-agnostic users, and this is disposable, gitignored output, so
  world-writable is fine here.

## Extending

- New read endpoint to cover: add a `[name, url, params]` triple to the
  `reqs` array in `browse()` (`k6/api-load-test.js`) — `params` is `{}` for a
  public read or `authHeaders` for one that needs the bench user's token.
  `report/generate_report.py`'s `ENDPOINT_LABELS` falls back to the raw tag
  name for anything not in `ENDPOINT_ORDER`; add an entry there for a nicer
  label.
- New write flow to benchmark: add an `exec`-mapped function alongside
  `bookingWrite()` and a matching entry in `options.scenarios` — keep its VU
  count low and separately tunable (env var, like `BOOKING_WRITE_VUS`) rather
  than scaling it with `PEAK_VUS`, and if it leaves any mutable state behind,
  sweep it in `teardown()` the same way `bookingWrite()`'s stray `confirmed`
  bookings are swept.
- New frontend page/device/network: edit the arrays at the top of
  `playwright/benchmark.js`; the report groups by whatever `page`/`device`/
  `network` values actually appear in the results, so no report change is
  needed.
