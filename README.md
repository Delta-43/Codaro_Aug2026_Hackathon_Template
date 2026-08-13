# Codaro Coding Challenge II — Track B base

A **generic booking engine** (resource → slot → booking) built so that **it can be changed very fast based on a surprise pivot using a config edit rather than a rewrite**. The tech stack: Next.js 14 + Tailwind
frontend, FastAPI backend, Supabase (Postgres). Demo data is **seeded
automatically** on first backend start. The general features to be expected are a landing page to showcase the resources offered and a side board to login to a dashboard with either a customer view or the resource owner view. This dashboard should allow an user to view available slots, book/rent them, change/cancel it. The business owner should be able to edit slots or add new items, confirm/cancel bookings, view all bookings and analytics per item. The database need not implement passwords but identify and track users based on email or userid. 

## The whole idea: one pivot file

`domain.config.json` is the **single source of truth** for everything that changes
based on repurpose needs:

| Axis | Where | Example pivot |
|------|-------|---------------|
| **Terminology** | `terms` | resource→Doctor, slot→Appointment, client→Patient, admins→Owner|
| **Business rules** | `rules` | cancellation window, capacity, buffer, advance window, info, |
| **Copy** | `copy` | CTAs, confirmation text, empty states|
| **Theme** | `theme` | colors, radius |
| **Custom fields** | `metaFields` + `metadata` jsonb | specialty, reason — **no migration** |

The backend serves this file at `GET /config`; the frontend fetches it and renders
every label via `<Term>` and every rule from `rules`. **Nothing hard-codes a
domain term or a magic number.** At 16:00:

```bash
cp domain.config.medical.example.json domain.config.json   # or edit in place
# restart backend (config is cached) — done. New niche, ~20 min.
```

## Why this survives an *unknown* pivot

The tracks warn: some assumptions stop being true, plus a **secret rule announced
on-site**. Two escape hatches absorb that:

1. **`metadata jsonb`** on every table → any new field needs no migration.
2. **Data-driven rules engine** (`backend/app/rules.py`) → a new constraint is
   one config key + one small validator function, never a refactor.

## Layout

```
domain.config.json          # THE pivot file (edit only this at 16:00)
domain.config.medical.example.json
supabase/schema.sql         # neutral tables: resources / slots / bookings (+ occupancy view)
backend/                    # FastAPI generic engine
  app/config.py             #  loads the pivot file
  app/db.py                 #  Supabase client
  app/rules.py              #  data-driven rules engine  <-- add secret rule here
  app/routers/              #  /resources /slots /bookings (+ /slots/occupancy)
  seed.py                   #  demo data (auto-seeds on first start; run manually to add more)
frontend/                   # Next.js 14 + Tailwind
  lib/domain.tsx            #  <Term>, useDomain(), fetchConfig()
  lib/api.ts                #  typed backend client
  app/page.tsx              #  occupancy view + booking demo (fully config-driven)
```

## Run it (Docker — one command)

Everything runs in two containers; only `backend/.env` needs filling in first.

```bash
cp backend/.env.example backend/.env    # fill SUPABASE_URL + SUPABASE_SERVICE_KEY (+ SUPABASE_DB_URL to auto-create tables)
make start                              # frontend :3000, backend :8000
```

`make` (no args) lists every shortcut: `start`, `stop`, `logs`, `reload`
(below), and `reset` (wipe + start fresh if something breaks).

Supabase (Postgres) stays hosted — no DB container. Backend startup still
creates tables (if `SUPABASE_DB_URL` is set) and seeds demo data on an empty DB.

**The 16:00 pivot:** edit `domain.config.json` (and UI files), then:

```bash
make reload   # backend caches config, so reload it to pick up the change
# the frontend hot-reloads on its own; no reload needed for UI edits
```

Config, `supabase/`, and both app trees are bind-mounted, so edits are live —
no rebuild. Rebuild (`docker compose up --build`) only when dependencies change.

## Run it (native, no Docker)

**1. Database** — create a Supabase project. The backend creates the tables for you
on startup (from `supabase/schema.sql`) if you give it `SUPABASE_DB_URL`; otherwise
run `supabase/schema.sql` yourself in the SQL editor.

**2. Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill SUPABASE_URL + SUPABASE_SERVICE_KEY (+ SUPABASE_DB_URL to auto-create tables)
uvicorn app.main:app --reload   # creates tables (if SUPABASE_DB_URL set) + seeds demo data on first start
# python seed.py              # optional: force-insert another demo batch
```

Startup does two things, both idempotent and guarded (won't crash the server):
1. **Create tables** — runs `supabase/schema.sql` over a direct Postgres connection
   (`SUPABASE_DB_URL`). Uses `IF NOT EXISTS`, so it's safe to run every boot.
2. **Seed demo data** — only when the DB has no resources yet.

**3. Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                 # http://localhost:3000
```

## How the pivot works (and the database)

**The config flow.** The backend reads `domain.config.json` once and caches it
(`@lru_cache` in `app/config.py`). It exposes the raw file at `GET /config`. The
frontend fetches that on load and renders every label through `<Term>` and every
number from `rules`. So editing the file → `make reload` (restart backend to drop
the cache) → refresh the browser = the whole app speaks the new domain. Nothing
in code hard-codes a term or a magic number.

**The database never changes at the pivot — on purpose.** Tables are neutral
(`resources` / `slots` / `bookings`) and `schema.sql` is fully idempotent
(`create table if not exists`, `create or replace view`, no `DROP`/`ALTER`). A
backend restart re-runs it, but existing tables are left untouched and **no data
is lost**. New domain fields go into the `metadata` jsonb column, so a pivot
needs no migration. Treat `schema.sql` as frozen during the event.

> Note: the database is **hosted Supabase (remote)**, not a Docker volume.
> `make reset` (`docker compose down -v`) only wipes the local `node_modules` /
> `.next` volumes — it does **not** clear your Supabase data.

### Demo data and reseeding after a pivot

Seeding is domain-aware: `seed()` reads the **current** config and names rows
from it — medical config → `Doctor 1..3`, restaurant config → `Table 1..3`, each
with 5 upcoming slots sized by `slotDurationMinutes` / `maxBookingsPerSlot`.

- **First boot:** `seed_if_empty` runs automatically — but **only when the DB has
  zero resources**. It fills an empty database and then never touches it again.
- **After a pivot:** your old rows are still there (`Doctor 1`...), so the
  auto-seed does nothing and the demo data no longer matches the new domain. To
  get fresh, matching demo data you must **clear then reseed**:

  ```bash
  # 1) edit domain.config.json to the new domain, then:
  make reload    # backend now serves the new terms/rules
  make reseed    # DELETE all rows + insert demo data named from the new config
  ```

  `make reseed` (backend `reseed.py`) truncates `resources`/`slots`/`bookings`
  (via `SUPABASE_DB_URL`, cascading), then re-runs `seed()`. **It deletes all
  existing data** — run it only when you want a clean demo for the new domain. If
  you'd rather keep real data you entered, skip it and just add rows normally.

## Contributing

All work lands through pull requests: an issue becomes a branch, the branch is
PR'd into `develop` (staging), and `develop` is PR'd into `main` (production).
Every PR runs backend tests, a frontend typecheck + build, and a
`domain.config.json` validation. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for
the exact commands and branch naming.

## Track B checklist (what the base covers)

- [x] Resource and Slot — `resources`, `slots`
- [x] Booking and Confirmation — `POST /bookings`, `confirmTitle`
- [x] Change and Cancellation — `/bookings/{id}/reschedule`, `/bookings/{id}/cancel`
- [x] Availability View — `slot_occupancy` view + `/slots/occupancy` + UI grid
- [x] Status and History — `status` + append-only `history` jsonb
