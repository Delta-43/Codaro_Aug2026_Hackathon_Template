# 97 — Air-gapping the landing page from the rest of the app

Splits the public marketing landing page out of `frontend/` into its own
standalone deployable, `landing/` — zero shared imports between the two going
forward, integrating only through a plain cross-origin link.

## Why

`frontend/`'s root `/` used to render the marketing page directly, importing
`useAuth()`/`getTenancy()` and living in the same file tree as the gated app.
That coupling meant landing-page redesigns and app-internal work could touch
the same files, causing avoidable merge conflicts as both kept evolving. This
is prep work for a follow-up plugin/embed effort, which needs a clean,
low-conflict base to build on.

## What changed

**New `landing/` app** — its own Next.js 14 + Tailwind v4 deployable (own
`package.json`, `Dockerfile`, `next.config.mjs`, `tsconfig.json`,
`eslint.config.mjs`), served on `:3001`.

- **Moved as-is**: `frontend/src/app/page.tsx` →
  `landing/src/app/page.tsx`, `frontend/src/components/landing/*` →
  `landing/src/components/landing/*`. Same visuals, same section order (Hero
  → How it works → Calendar demo → Testimonials → Docs CTA → Business CTA →
  Footer).
- **Decoupled**: removed `useAuth()`/`authed` from `page.tsx`, `nav-bar.tsx`,
  `hero.tsx`, `business-cta.tsx`, `footer.tsx` — landing can't see a
  visitor's session on a different origin, so CTAs always render their
  logged-out copy now (this is the one deliberate, visible behavior change).
  In-app `next/link` navigations to `/login`, `/docs`, `/search`, `/privacy`
  became plain cross-origin `<a href="${NEXT_PUBLIC_APP_URL}/...">`.
- **Copied, frozen on purpose** (pure/presentational, no auth/data
  dependency, confirmed via import tracing before copying):
  `components/calendar/{month-view,week-view,day-view,slot-pill}.tsx` (feed
  the landing `CalendarDemo`'s static preview), `theme-toggle.tsx`,
  `ui/button.tsx`, `lib/{calendar,format,utils}.ts`, `types/domain.ts`. Not
  shared as a package on purpose — see `landing/CLAUDE.md`'s "Why air-gapped"
  section for why that would recreate the exact conflict surface this split
  removes.
- `frontend/`'s root `/` now just `redirect("/login")`.

**Infra/docs**: `docker-compose.yml`/`Makefile` gained a `landing` service;
`.github/workflows/ci.yml` gained a `landing` job (lint + typecheck + build,
mirroring the `frontend` job); root `README.md`/`CLAUDE.md`, `frontend/CLAUDE.md`
updated; new `landing/CLAUDE.md` added.

## Verified

- `make start`/`make stop`/`make reload` all work correctly with the new
  3-service layout (backend :8000, frontend :3000, landing :3001).
- Landing's rendered HTML has every original section/anchor
  (`#how`/`#calendar`/`#reviews`/`#docs`) and the Month/Week/Day calendar
  toggle intact; `landing/globals.css` and `theme-toggle.tsx` are
  byte-identical to `frontend/`'s copies (dark/light theming unchanged).
  Landing's CTA/footer links resolve to real cross-origin URLs on
  `frontend`'s origin (`/login`, `/docs`, `/privacy`), and those routes still
  work normally.
- `python .github/scripts/validate_domain_config.py` passes.
- `frontend`: `npx tsc --noEmit` + `npm run build` clean (root `/` now a
  154 B redirect page).
- `landing`: `npx tsc --noEmit` + `npm run build` clean.
- `npx eslint .` on both packages: 0 errors (only pre-existing warnings
  already treated as non-blocking per `eslint.config.mjs`'s own policy).
- Backend `pytest` suite not run locally (no Python deps installed in this
  sandbox) — no backend code was touched by this branch, so no regression
  risk there; CI covers it.

## Not in this branch

Multi-tenant widget support, and the actual plugin/embed work
(`plugin_sdk/`, `/embed`, `embed.js`) — that's a separate follow-up planned
on top of this once merged, targeting the now-air-gapped `frontend/` with
`landing/`'s cross-origin link as the base to upgrade.
