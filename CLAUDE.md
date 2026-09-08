# Codaro Booking Engine — root guide

## Token budget (read first)

Work to finish the task in as few tokens as possible — tokens are the user's
usage limit. **Screenshots/images are the #1 cost**; prefer text tools and take
at most one, only when a visual result must be shown. Read narrow (`grep` +
`sed -n` ranges, not whole files), don't re-read after editing, batch tool
calls, verify once, and keep prose/commit messages terse. Full rules:
[.claude/token-budget.md](.claude/token-budget.md). This applies to every agent.

## What this is

A generic booking engine — `provider → service → resource → slot → booking →
user` — built so a completely different niche can be adopted via config +
seed data instead of a rewrite. Multi-slot bookings, party size, reviews,
follows, search, day-availability and month-density all ride on that neutral
spine. Stack: **Next.js 14 + Tailwind** frontend, **FastAPI** backend, hosted
**Supabase (Postgres + Auth)**. Startup applies the schema; demo data is seeded
on demand with `make reseed`.

The product shape: a public landing page showcasing what's on offer, and a
gated dashboard with a customer view and a business-owner view. Customers view
available slots, book them, and change or cancel. Owners edit slots, add items,
confirm/cancel bookings, view all bookings, and read per-item analytics.

The pivot mechanism: `domain.config.json` (now **v2**, `configVersion: 2`) holds
the engine's **vocabulary + global defaults**. v1's five sections (`terms`,
`copy`, `theme`, `metaFields`, `rules`) only ever described one kind of business —
a time-slot calendar with a price per slot. v2 adds the blocks that let the
*shape* of the offering pivot too: `capabilities`, `booking`, `pricing`,
`payments`, `inventory`, `location`, `prerequisites`, `timing`, `recurrence`,
`entitlements`, `discovery`. It is strictly additive — `rules` and `search`
survive as deprecated aliases kept in sync with `timing` and `discovery`, so a v1
file still boots. The one *subtractive* change: v1's `theme` block is gone. The
frontend owns its palette (its own Tailwind tokens plus the site's light/dark
toggle), so a `theme` key in an old pivot file is silently dropped at load. The backend normalizes and **validates** it at load
(`app/config_schema.py`), so a typo fails at the edit rather than on the next
booking, and serves it at `GET /config`.

**Config is the default; the service row is the override.** A service's own
columns (duration, min/max slots, cutoff, price, booking model) win over the
config globals via `rules.py` `effective_service_rules`, and
`effective_service_config` lifts the same precedence to whole blocks through
`services.metadata.<block>` — which is what lets two businesses on one
marketplace deployment price and gate completely differently. The frontend renders
vertical vocabulary from `src/config/verticals.ts` (pure UI labels/nouns/copy).
New domain-specific data goes in each base table's `metadata jsonb` column — no
migrations at pivot time. `supabase/schema.sql` is treated as frozen/idempotent
once the event starts (new *entities* are added as new tables, base tables stay
frozen). On the backend, the pivot is enforced by the per-service rule resolver,
the legacy event-keyed rules registry (still used by `slots.py`), and a
config-driven `metaFields` validator — see [backend/CLAUDE.md](backend/CLAUDE.md).

### Surviving an *unknown* pivot

Two escape hatches absorb a surprise rule announced on-site:

1. **`metadata jsonb`** on every table → any new field needs no migration.
2. **Data-driven rules engine** (`backend/app/rules.py`) → a new constraint is
   one config key + one small validator function, never a refactor.

### What's configurable

| Block | Controls |
|-------|----------|
| `terms` / `copy` | vocabulary, CTAs, empty states |
| `capabilities` | on/off spine — payments, inventory, waitlist, quotes, reviews… |
| `booking` | unit kind, granularity, duration mode, party rules, add-on options |
| `pricing` | rate + tiers + fees + caps + deposit (per-hour, per-night, per-person, tiered…) |
| `payments` | flow, payer, schedule, billing cycle, no-show fee |
| `inventory` | none / finite / rentable / consumable / serialised |
| `location` | on-site / at-customer / remote / delivery / pickup, **business timezone**, service area |
| `prerequisites` | ID checks, intake forms, waivers, memberships, approvals |
| `timing` | instant vs request-approve, waitlist, seasons, blackouts, lead time |
| `metaFields` | custom fields per entity — **no migration** |

Every block is overridable **per service** via `services.metadata.<block>`, so one
deployment can host businesses that work completely differently.

**The config flow.** The backend reads `domain.config.json` once, fills in
defaults, folds in the deprecated v1 `rules`/`search` aliases, **validates** the
result, and caches it (`app/config.py` + `app/config_schema.py`). It exposes that
resolved tree at `GET /config`. The frontend fetches it on load and renders every
label through `<Term>` and every number from the config. So editing the file →
`make reload` → refresh the browser = the whole app speaks the new domain.
Nothing in code hard-codes a term or a magic number.

A bad edit fails loudly *at the edit*: `load_config()` raises with every problem
listed at once, and `POST /config/reload` (owner-gated) validates the new file
**before** dropping the cached one, so a typo mid-pivot returns a 422 instead of
taking the running app down.

**Reference:** [docs/PIVOT-SYSTEM.md](docs/PIVOT-SYSTEM.md) documents every block,
the precedence model, and exactly which keys the engine enforces today versus
which are declared-and-validated but still waiting on a reader.
[docs/PIVOT-COVERAGE.md](docs/PIVOT-COVERAGE.md) is the evidence: 100 deliberately
different businesses expressed as real configs and run through the validator and
pricing engine (`python3 scripts/check_pivots.py`), plus every issue that
exercise found and how it was resolved.

**The database never changes at the pivot — on purpose.** Tables are neutral and
`schema.sql` is fully idempotent (`create table if not exists`, `create or
replace view`, no `DROP`/`ALTER`). A backend restart re-runs it, but existing
tables are left untouched and **no data is lost**. New domain fields go into the
`metadata` jsonb column, so a pivot needs no migration. Treat `schema.sql` as
frozen during the event.

> The database is **hosted Supabase (remote)**, not a Docker volume.
> `make reset` (`docker compose down -v`) only wipes the local `node_modules` /
> `.next` volumes — it does **not** clear your Supabase data.

## Auth (Supabase Auth)

Implemented on this branch (`16-auth-system`); it reverses the engine's
original "no auth" stance. Identity moved from *"trust the `client_email` in
the request body"* to **Supabase Auth**: Supabase handles email/password
sign-up + login and issues a JWT. The frontend attaches that JWT as
`Authorization: Bearer <token>`; the backend verifies it against the project's
**JWKS** (**ES256/RS256**, keyed by `kid`) and reads the user (`sub`, `email`)
from the token instead of trusting the body. Symmetric **HS256** is not
accepted — supporting it let the token header pick the weaker scheme.

- **Roles stay config-driven.** The owner/client split keeps using
  `terms.admin` / `terms.client`; the `actor` concept became a *verified* role,
  trusted from a `profiles` row rather than an unchecked flag.
- **Per-user isolation via Supabase RLS** (see
  [supabase/CLAUDE.md](supabase/CLAUDE.md)): clients see only their own
  bookings, owners manage only their own providers/resources. Every user-owned
  read/write goes through a JWT-scoped Supabase client so RLS applies live; the
  service key is kept for system/cross-user work.
- Auth is a cross-cutting layer on top of the engine — it does **not** change
  the pivot design. `domain.config.json` still owns vocabulary/defaults; no
  domain term or magic number moves into auth code.

Each subdir's `CLAUDE.md` records what's actually implemented.

## Repo layout

| Path | Owns | Detail |
|------|------|--------|
| `backend/` | FastAPI engine: config + per-service rules, camelCase serialization, `/providers` `/services` `/resources` `/slots` `/availability` `/bookings` `/me` `/demo` routers, auth, three-vertical seeding | [backend/CLAUDE.md](backend/CLAUDE.md) |
| `frontend/` | Next.js app (`frontend/src/`): public landing page at `/`, login + gated `(app)` group (search / calendar / bookings / provider / account), real HTTP API seam | [frontend/CLAUDE.md](frontend/CLAUDE.md) |
| `supabase/` | `schema.sql` — neutral base tables + extended entities (providers/services/booking_slots/reviews/follows), occupancy view, RLS | [supabase/CLAUDE.md](supabase/CLAUDE.md) |
| `test/` | Stack + API tests (owned exclusively by the `test-writer` agent, see below) | [test/CLAUDE.md](test/CLAUDE.md) |
| `domain.config.json` | The pivot file (v2) | [docs/PIVOT-SYSTEM.md](docs/PIVOT-SYSTEM.md) |
| `scripts/check_pivots.py` | 100 pivots run through the real validator + pricing engine | [docs/PIVOT-COVERAGE.md](docs/PIVOT-COVERAGE.md) |
| `pivots/` | The same 100 pivots as complete, drop-in `domain.config.json` files (generated) | [pivots/CLAUDE.md](pivots/CLAUDE.md) |

```
domain.config.json          # THE pivot file (edit only this at pivot time)
domain.config.medical.example.json
supabase/schema.sql         # neutral tables + occupancy view + RLS
backend/                    # FastAPI generic engine
  app/config.py             #  loads the pivot file (+ POST /config/reload)
  app/config_schema.py      #  normalize() + validate() for the whole v2 tree
  app/db.py                 #  Supabase client + maybe_row not-found guard
  app/models.py             #  Pydantic request envelopes
  app/meta.py               #  config-driven metaFields validator
  app/rules.py              #  per-service resolver + event-keyed rules engine
                            #  <-- add a surprise rule here
  app/routers/              #  /providers /services /resources /slots /availability
                            #  /bookings /me /messages /owner /waitlist
  seed.py                   #  demo data (run `make reseed`)
frontend/                   # Next.js 14 + Tailwind — the app lives in src/
  src/config/verticals.ts   #  UI vocabulary per vertical (useVertical())
  src/api/index.ts          #  typed backend client (the HTTP seam)
  src/app/page.tsx          #  public marketing landing page (root /)
  src/components/landing/   #  landing page sections (hero, nav, footer, …)
  src/app/login/page.tsx    #  Supabase Auth sign-in / sign-up
  src/app/(app)/            #  gated customer tabs: search / provider / calendar
                            #  / bookings / account
  src/app/owner/            #  business mode: dashboard, calendar, requests,
                            #  services, profile, settings
```

`backend/`, `frontend/`, and `supabase/` are built out **independently** —
each has its own `CLAUDE.md` with the requirements and conventions for that
piece. Read this file first, then the relevant subdirectory's file, before
working in it.

## Run it (Docker — one command)

Everything runs in two containers. Both env files must exist first — each
service declares its own `env_file` in `docker-compose.yml`, so `make start`
fails on a fresh clone without them.

```bash
cp backend/.env.example backend/.env            # SUPABASE_URL + SERVICE_KEY + ANON_KEY (+ DB_URL)
cp frontend/.env.local.example frontend/.env.local  # NEXT_PUBLIC_API_BASE + Supabase anon key
make start                                      # frontend :3000, backend :8000
```

Supabase (Postgres) stays hosted — no DB container. Backend startup creates the
tables (if `SUPABASE_DB_URL` is set). It does **not** seed: run `make reseed`
once to fill an empty database with demo data.

**At pivot time:** edit `domain.config.json` (and UI files), then `make reload`
— the backend caches config, so reload it to pick up the change. The frontend
hot-reloads on its own; no reload needed for UI edits.

Config, `supabase/`, and both app trees are bind-mounted, so edits are live —
no rebuild. Rebuild (`docker compose up --build`) only when dependencies change.

## Run it (native, no Docker)

**1. Database** — create a Supabase project. The backend creates the tables for
you on startup (from `supabase/schema.sql`) if you give it `SUPABASE_DB_URL`;
otherwise run `supabase/schema.sql` yourself in the SQL editor.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill SUPABASE_URL + SERVICE_KEY (+ DB_URL to auto-create tables)
uvicorn app.main:app --reload   # creates tables (no seeding; see `make reseed`)
```

Startup does two things, both idempotent and guarded (won't crash the server):

1. **Create tables** — runs `supabase/schema.sql` over a direct Postgres
   connection (`SUPABASE_DB_URL`). Uses `IF NOT EXISTS`, safe every boot.
2. **Seed demo data** — only when the DB has no resources yet.

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                 # http://localhost:3000 (landing page is the app root /)
```

## Demo data and reseeding after a pivot

Seeding is domain-aware: `seed_from_config()` reads the **current** config and names rows
from it — medical config → `Doctor 1..3`, restaurant config → `Table 1..3`, each
with upcoming slots sized by the config's duration and capacity.

- **First boot:** nothing is seeded. Startup only applies `supabase/schema.sql`,
  so a fresh database has the tables and no rows. Run `make reseed` once to fill
  it. (`seed_if_empty()` still exists in `backend/seed.py` but is no longer
  wired into startup.)
- **After a pivot:** your old rows are still there (`Doctor 1`…), so the demo
  data no longer matches the new domain. To get fresh, matching data you must
  **clear then reseed**:

  ```bash
  make reload    # backend now serves the new terms/rules
  make reseed    # DELETE all rows + insert demo data named from the new config
  ```

`make reseed` (backend `reseed.py`) truncates the base tables (via
`SUPABASE_DB_URL`, cascading), then re-runs `seed_from_config()`. **It deletes all existing
data** — run it only when you want a clean demo for the new domain. To keep real
data you entered, skip it and add rows normally.

## Development workflow — the 3-agent verification pipeline

To check the state of the codebase (what's built, whether it works, what's
left) without doing that analysis by hand every time, use the three custom
agents in `.claude/agents/`, run in this order:

1. **`codebase-analyst`** (read-only, full repo) — reads the root and every
   nested `CLAUDE.md` plus the actual code, and reports back a structured
   understanding: architecture, config flow, implemented endpoints/routes,
   schema shape, and gaps vs. the Track B checklist below. It never edits
   anything.
2. **`test-writer`** (reads anywhere, writes only inside `test/`) — takes the
   analyst's findings and authors test plans/automated tests for the stack
   and the API endpoints under `test/`. It must never create or modify files
   outside `test/`.
3. **`test-runner`** (execute-only — no `Write`/`Edit`/`NotebookEdit`) — runs
   whatever `test-writer` produced (`pytest`, `npm test`, etc.) and reports
   pass/fail results. It cannot modify any file, including its own results.

The orchestrating session runs these three in sequence (each depends on the
previous one's output) and can write the combined result to `REPORT.md` (what
exists and how it's implemented) and `TODO.md` (what's missing or broken, and
what to do next). **Both are gitignored on purpose.** They are point-in-time
snapshots that go stale within a commit or two, and a public repo carrying a
machine-generated defect list reads as an unmaintained project. Regenerate them
locally whenever you want a fresh read.

## Working on the code

The repository is not accepting contributions and has no issue tracker. What
follows is for the owner, and for anyone working in a fork.

Work lands through pull requests: a branch is PR'd into `develop` (staging), and
`develop` is PR'd into `main` (production). Squash-merge into `develop`, but use
a **merge commit** for a back-merge of `main` into `develop` and for the
`develop` into `main` release, or `main` drops out of `develop`'s ancestry and
the next release conflicts. CI runs three gates, worth running before you push:

```bash
python -m pytest test -q
python .github/scripts/validate_domain_config.py
cd frontend && npm ci && npx tsc --noEmit && npm run build
```

Two rules the codebase lives by, and the reason most review comments exist:

- **No hard-coded domain words.** Say `resource`, never `room` or `doctor`. In
  the frontend labels come from `useVertical()` (`src/config/verticals.ts`);
  backend-side copy comes from `domain.config.json`'s `terms`/`copy`.
- **No magic numbers.** Business values live in the `domain.config.json` v2
  blocks (`timing`, `booking`, `pricing`, …), not the deprecated v1 `rules`
  alias. A service row's own columns/`metadata` override the global default via
  `rules.effective_service_rules`, so read the resolved value, never a literal.

`supabase/schema.sql` is frozen; new domain data goes in `metadata jsonb`.
See **[DEPLOY.md](DEPLOY.md)** for hosting.

## Track B checklist (what the base covers)

- [x] Resource and Slot — `resources`, `slots`
- [x] Booking and Confirmation — `POST /bookings`, `confirmTitle`
- [x] Change and Cancellation — `/bookings/{id}/reschedule`, `/bookings/{id}/cancel`
- [x] Availability View — `slot_occupancy` view + `/slots/occupancy` + UI grid
- [x] Status and History — `status` + append-only `history` jsonb
- [x] Customer app — `src/app/(app)/` (search / calendar / book / reschedule / cancel)
- [x] Owner dashboard — `src/app/owner/`: services, requests, calendar, analytics
- [x] Owner: approve/reject bookings — `POST /bookings/{id}/approve`, `POST /bookings/{id}/reject`
- [x] Owner: view all bookings + filter — `GET /bookings` (`?scope=`)
- [x] Owner: per-item analytics — `GET /resources/{id}/analytics`
- [x] Config-driven behavior — `GET /config` + rules actually enforced (not just returned)

## Commands

```bash
cp backend/.env.example backend/.env   # SUPABASE_URL + SERVICE_KEY + ANON_KEY (+ DB_URL)
make start                             # frontend :3000, backend :8000
make reload                            # re-read domain.config.json after an edit
make reseed                            # wipe + rebuild demo data from the current config
make checkseed                         # report where the seeded data and the config disagree
make logs / make stop / make reset     # see `make` with no args for the full list
```
