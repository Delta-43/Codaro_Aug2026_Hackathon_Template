# TODO — after the frontend⇄backend wiring

_Prioritised. Snapshot, not a living doc — regenerate via the pipeline._

## P0 — correctness / must-know
- [x] **Tests regenerated & green**: `test/backend` → 203 passed (offline);
  `test/e2e` → 8 passed against live Supabase. _(Remaining: decide whether CI
  runs the opt-in live suite or stays offline-only.)_
- [ ] **The live e2e suite mutates the real project** — it switches the demo
  vertical and creates/cancels a booking, and does not restore `fleet` on exit.
  After running it, reseed (`docker exec … python3 -c "import seed;
  seed.seed_vertical('fleet')"`). Consider making the suite reseed-on-teardown,
  or point it at a throwaway Supabase project.
- [ ] **Seeded providers have no `owner_id`** (they're created via the service
  key). By design they can't be edited via an owner token (RLS
  `providers_write_own`). If an owner-admin UI is added, either stamp `owner_id`
  on seed or provide an owner-claim path. Same caveat the engine already had for
  seeded resources.
- [ ] **`POST /demo/vertical` / `/demo/reset` are destructive** (truncate all
  catalog + booking data, including any real users' bookings) and take ~10–15s.
  They require an authenticated user but not an owner. Consider gating on owner
  or disabling outside demo mode before any real multi-tenant use.

## P1 — docs drift (the code moved; docs didn't)
- [x] `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`, `supabase/CLAUDE.md`
  updated to the Provider→Service→Resource domain, per-service rules, camelCase
  contract, new tables/endpoints, and ES256+JWKS auth. (`frontend/CLAUDE.md` now
  points at `src/` + the retired `_legacy/` files.)
- [x] Account page copy fixed ("in-memory"/"no password auth" → real auth +
  backend persistence).

## P2 — completeness / stretch
- [ ] **Owner/admin UI** in the new frontend — the backend has provider/service/
  resource/slot management surface only partially exposed (no provider/service
  *create* endpoints were added; seeds populate data). Add owner endpoints +
  screens if owner self-service is needed.
- [ ] **Provider search `near`** is a case-insensitive city substring computed in
  Python over all providers (fine at demo scale). Add real geo/pagination if the
  catalog grows.
- [ ] **Reviews**: one per booking; re-review replaces via the service key (no
  user-update RLS policy on `reviews`). Add an update policy if in-place edits
  are wanted.
- [ ] **Month density** shows only 0/3 for unit-selection verticals (a unit is
  free or taken — no fractional day). Expected; revisit only if a richer heat
  scale is desired.
- [ ] **N+1 enrichment**: `/bookings` list resolves provider/service names client
  side per card. Fine now; a batch/embed endpoint would cut round-trips at scale.
- [x] **Favicon** added (`src/app/icon.svg`, served 200) — the tab icon renders
  and the `/favicon.ico` probe is resolved via `<link rel="icon">`.
- [ ] **`npm audit`: 2 high-severity advisories** — both are **Next.js 14
  inherent** (DoS/SSRF/cache-poisoning classes) plus a transitive **postcss**
  XSS. npm's only offered fix is `next@16.3.1` — a **two-major-version breaking
  upgrade** (would very likely break the react-aria UI + app-router usage). Left
  as-is deliberately; treat a Next 14→latest migration as its own tracked,
  tested task rather than `npm audit fix --force`.

## Environment / ops
- [ ] `backend/.env` now needs `SUPABASE_JWT_SECRET` + `SUPABASE_ANON_KEY` (in
  addition to URL/service key/db url). `frontend/.env.local` needs
  `NEXT_PUBLIC_SUPABASE_URL/ANON_KEY` and `NEXT_PUBLIC_API_BASE`. Keep
  `.env.example` in sync.
- [ ] Demo login: `demo@codaro.app` / `Codaro-Demo-2026` (provisioned by the
  seed). A hidden `holds@codaro.app` user owns the "already booked" occupancy.
