# TODO — plugin_sdk

Current status only — see [CLAUDE.md](CLAUDE.md) for how it works and why,
and `git log -- plugin_sdk/` for the decision history if it's ever needed.

---

## Done

- **`/embed` route** (Tier 1) — chromeless, reuses `ProviderProfile`/
  `BookingFlow`/`AppProvider` unmodified. In-frame auth (no redirect to
  `/login`), `postMessage`-based iframe resizing, `theme.*` applied inside
  the iframe only.
- **`frontend/public/embed.js`** (Tier 2, button and buttonless modes) —
  vanilla JS, no build step. `data-label`, `data-mode="buttonless"`, and the
  public `window.Arbor.open()`/`close()` API. Floating launcher (default) or
  buttonless (host page supplies its own buttons) → lazy modal → real
  booking flow. Close via × or backdrop (reliable); Escape is best-effort
  only (cross-frame keyboard limitation, not fixable from this side).
  Dogfooded on the project's own landing page (`frontend/src/app/page.tsx`,
  buttonless mode) as well as `example.html` (default button mode).
- **Guest checkout** — email one-time-code sign-in (`sendOtp`/`verifyOtp`),
  not Supabase anonymous auth (blocked by `create_booking`'s email
  requirement + the frozen schema's `NOT NULL client_email` — see
  `CLAUDE.md`). Zero backend changes needed.
- **Docs** — `README.md` (quick start, attribute reference, the "no widget,
  just the API" alternative) and `example.html` (runnable, framework-free).
- **`frame-ancestors`** — deliberately left unrestricted; not a gap, see
  `CLAUDE.md`'s Conventions section for why.
- **Frontend test coverage** — Vitest + RTL in `frontend/` (`npm test`):
  `AuthGate` fallback, `AuthForm`, `GuestOtpForm`, and `EmbedLayout`'s
  `ResizeObserver`/postMessage wiring (17 tests).

Live-verify against the real deployed stack (Docker `make start` + the real
Supabase project) before calling any of the above shipped for a given
change, not just `tsc`/`eslint`/build.

## Next

- **`/embed`'s `page.tsx`/`calendar/page.tsx` still have no automated test
  coverage** (the layout's resize wiring is now covered) — they need a real
  DOM/router integration harness, a bigger lift than component-level tests.
  Not started.
- **Real `verifyOtp` round-trip unverified** — not a code problem. This
  Supabase project needs a real SMTP/email provider configured (Resend,
  Postmark, SES, etc.) under Auth → Email before OTP codes actually reach an
  inbox; the default Supabase sender isn't meant for production. Unblocks in
  minutes once someone with dashboard access adds one.
- **`data-mode="inline"`** — a plausible fast-follow (render into a
  host-page container instead of a floating button), not started; button
  mode covers the core ask.

## Explicitly out of scope for this folder

Recurring gaps flagged by `pivot_plans/Pivot_Compatibility_Report.md` that
every real adopter hits eventually, but owned by `backend/`, not here:

- `booking.options[]` (add-ons/insurance) — declared in config, no reader.
- Recurring weekly opening hours — no schema representation at all,
  `timing.blackouts[]` is date-range only.

## Not planned (deliberate, not deferred)

- Tier 0 (link-out button) — already works today via `tenancy.mode: single`,
  no build needed. Every logged-out CTA's `href="/login"` fallback (see
  `CLAUDE.md`'s dogfooding section) is a live example of the pattern, even
  though those same buttons now also open the Tier-2 widget when it's loaded.
- A fixed `frame-ancestors` allowlist — would break the "embeddable by any
  site with zero config" design; see `CLAUDE.md`.
