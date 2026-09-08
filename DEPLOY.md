# Deployment — Vercel (frontend) + Railway (backend) + Supabase

The app splits across three managed platforms:

| Layer | Platform | Source |
|-------|----------|--------|
| Frontend (Next.js) | **Vercel** | `frontend/` |
| Backend (FastAPI) | **Railway** | `backend/` (Dockerfile) |
| Postgres + Auth | **Supabase** | hosted project |

`main` is the production branch. Merge a PR into `main` → both platforms
redeploy automatically.

---

## 0. Prerequisites — a production Supabase project

Use a **separate** Supabase project for production (don't share your dev one —
seeding/reset are destructive). From **Settings → API** and **Connect** collect:

- Project URL (`SUPABASE_URL`)
- `anon` public key (`SUPABASE_ANON_KEY`)
- `service_role` key (`SUPABASE_SERVICE_KEY`)
- Session-pooler connection string (`SUPABASE_DB_URL`)

The backend applies `supabase/schema.sql` on first boot, so the project can
start empty (seed it afterwards with `make reseed`) — **but only if `SUPABASE_DB_URL` is set** (see below).
Table creation runs DDL over a direct Postgres connection, which is impossible
through the REST key alone; without `SUPABASE_DB_URL` the app boots with no
tables. Startup logs `Schema applied from …` on success, or a loud
`SUPABASE_DB_URL not set` / `Schema setup FAILED` warning otherwise.

---

## 1. Backend → Railway

1. **New Project → Deploy from GitHub repo**, pick this repo.
2. Open the service → **Settings → Source** → leave **Root Directory** as the
   **repo root** (empty / `/`), **not** `backend`. The backend reads two
   repo-root files (`domain.config.json`, `supabase/schema.sql`) that only exist
   in the image when the build context is the whole repo. Railway reads
   `railway.json` at the root, which points the build at `backend/Dockerfile`.
   There is deliberately only **one** `railway.json`, at the repo root. Setting
   Root Directory to `backend` does not just read a different config — it breaks
   the build outright, because `backend/Dockerfile` copies `backend/…`,
   `supabase/` and `domain.config.json`, none of which exist inside `backend/`.
3. **Settings → Networking → Generate Domain** to get a public URL
   (e.g. `https://codaro-backend.up.railway.app`).
4. **Variables** — add:
   ```
   SUPABASE_URL=...
   SUPABASE_SERVICE_KEY=...
   SUPABASE_ANON_KEY=...
   SUPABASE_DB_URL=...
   CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
   WEB_CONCURRENCY=1
   ```
   Do **not** set `PORT` — Railway injects it and the container binds `$PORT`.
5. **Region:** set the service region to match your Supabase project's region
   (Settings → Region) so every backend→DB query stays same-region. This is the
   single biggest latency win and costs nothing.
6. Deploy. Health check hits `/health`; the deploy goes live only once it passes.

> You'll set `CORS_ORIGINS` again after step 2 once you know the real Vercel URL.

## 2. Frontend → Vercel

1. **Add New → Project**, import this repo.
2. Set **Root Directory = `frontend`** (Vercel auto-detects Next.js).
3. **Environment Variables:**
   ```
   NEXT_PUBLIC_API_BASE=https://<your-railway-backend-domain>
   NEXT_PUBLIC_SUPABASE_URL=https://<your-project>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon public key>
   ```
4. Deploy. Note the production URL (`https://<app>.vercel.app`).

## 3. Close the loop

- Put the Vercel URL into Railway's `CORS_ORIGINS` and redeploy the backend.
- In **Supabase → Authentication → URL Configuration**, add the Vercel URL to
  **Site URL / Redirect URLs** so email/password auth redirects resolve.

---

## Showcase-only: the frontend on its own

Arbor's hosted demo is retired. If you want the project *visitable* without
paying for a backend, deploy the frontend alone in showcase-only mode: `/` and
`/showcase` are presentational and render with no API behind them.

On Vercel, set one variable and redeploy:

```
NEXT_PUBLIC_SHOWCASE_ONLY=1
```

`NEXT_PUBLIC_API_BASE` is then unused and can be dropped. No backend, no
Supabase, no `CORS_ORIGINS`.

What the flag changes ([`src/config/showcase.ts`](frontend/src/config/showcase.ts)):

| | Normal | Showcase-only |
|---|---|---|
| `/showcase` catalogue | `GET /services` + `GET /providers` | the generated snapshot, no request made |
| Sign-in CTAs | `/login` | the source repository |
| `/login`, `/search`, `/bookings`, `/owner/*` | served | redirect to `/` |

The redirect is the point. Left reachable, those routes load and then fail every
request, which reads as a broken app rather than a deliberately static one.

The catalogue is generated from `backend/seed_data.py`, so it lists what the
seeded app lists rather than a hand-written copy that would drift:

```bash
python3 scripts/gen_showcase_snapshot.py           # regenerate
python3 scripts/gen_showcase_snapshot.py --check   # CI-friendly: fails if stale
```

CI runs the `--check`, so editing the seed data without regenerating fails the
build rather than silently shipping a stale catalogue.

Unset the flag and everything behaves normally; this is a deployment mode, not a
fork.

## Continuous deployment

Both platforms watch GitHub:

- **PR opened** → Vercel builds a **preview URL**; your existing `.github/
  workflows/ci.yml` runs tests/typecheck/build as the quality gate.
- **Merge to `main`** → Vercel promotes production, Railway redeploys the
  backend. No extra pipeline YAML needed.

(Optional) In Railway, enable **PR environments** if you want a throwaway
backend per PR — off by default because it multiplies usage.

---

## Notes & gotchas

- **`WEB_CONCURRENCY=1` is deliberate.** `create_tables_if_configured()` runs
  in the FastAPI lifespan, i.e. once *per worker*, so more than one worker
  applies the DDL concurrently on a cold start. To scale out, move schema setup
  into a Railway **pre-deploy command** (or a one-off job) and then raise
  `WEB_CONCURRENCY`. (No seeding runs on startup.)
- **Local dev is unchanged.** `docker-compose.yml` overrides the container
  command with `--reload`; the image's default `CMD` is the production command.
- **Build context is the repo root, not `backend/`.** The backend resolves
  `domain.config.json` and `supabase/schema.sql` relative to the repo root
  (`parents[2]` of `backend/app/*.py`), so the Dockerfile copies them in and the
  image must be built from the root. Keep Railway's Root Directory empty.
- **Don't hardcode URLs.** Frontend reads `NEXT_PUBLIC_API_BASE`; backend CORS
  reads `CORS_ORIGINS`. Everything else is Supabase config.
