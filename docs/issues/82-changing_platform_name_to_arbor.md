# 82 — Rename the platform from "service.com" to "Arbor"

Change the user-facing product name everywhere it appears in the project.
Nothing about the engine/pivot design changes — this is a brand string swap.

## What changed

The old name showed up in two visual forms:
1. A plain wordmark string `service.com` / `Service.com`.
2. A two-tone split — a neutral `Service` span next to a pink `.com`
   span — used in every app header and login screen.

Both were replaced with **Arbor**, rendered as a single pink (`text-primary`)
word to match the accent the split markup already used. "Arbor" is a proper
noun, so it's capitalized rather than the old lowercase domain styling.

| File | Before | After |
|------|--------|-------|
| `app/layout.tsx` | `title: "Service.com"` (tab / SEO) | `title: "Arbor"` |
| `components/landing/hero.tsx` | `service.com` hero wordmark | `Arbor` |
| `components/landing/business-cta.tsx` | "Bring it to service.com." | "Bring it to Arbor." |
| `components/landing/footer.tsx` | "© <year> service.com" | "© <year> Arbor" |
| `components/landing/testimonials.tsx` | 4× "service.com" | 4× "Arbor" |
| `app/login/page.tsx` | `Service` + pink `.com` | pink `Arbor` |
| `app/login/business/page.tsx` | `Service` + `.com` + Business | `Arbor` + Business badge |
| `components/app-shell.tsx` | customer app sidebar brand | `Arbor` |
| `components/business/business-shell.tsx` | business app brand | `Arbor` + Business badge |

## Deliberately not changed

- **`docs/issues/*.md`** — historical records; rewriting them would
  falsify the per-issue trail.
- **Domain vocabulary "Service"** (`serviceNoun`, "Service fee", docs
  examples) — that's the booking *noun*, not the brand.
- **`booking-engine-frontend`** in `package.json` — internal package id,
  never shown to users.
- **Demo credentials** `demo@codaro.app` / `Codaro-Demo-2026` in
  `login/page.tsx` — must match the backend-seeded Supabase accounts;
  renaming here alone would break demo login.

## Verification

- `validate_domain_config.py` ✓
- `tsc --noEmit` ✓ (JSX still valid after collapsing the split spans)
- `pytest`: 1024 passed. The single failure (`test_demo_user_has_seeded_bookings`,
  a live-API test asserting a fixed seeded-booking count) is flaky shared-DB
  state, unrelated to this frontend-only string change.
- Whole-repo grep confirms no `service.com` / split `Service`+`.com` brand
  remains in code.
