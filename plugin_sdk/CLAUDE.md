# plugin_sdk/ — embeddable booking widget

## Role

Turns the booking engine into something a *third-party business's own
website* can drop in with one `<script>` tag, instead of something a
customer only reaches as a standalone app. See
[README.md](README.md) for the adopter-facing quick start and
[example.html](example.html) for a runnable, framework-free demo page.
[TODO.md](TODO.md) tracks current status and open follow-ups.

Grounded in [pivot_plans/Pivot_Compatibility_Report.md](../pivot_plans/Pivot_Compatibility_Report.md)
§4 ("The plugin question: delivery fit"), which scored three delivery tiers
against what the engine already does. This folder covers Tiers 1 and 2 —
Tier 0 (a plain link-out button) needs nothing beyond `tenancy.mode: single`,
which already worked before this folder existed.

| Tier | What it is | Status |
|---|---|---|
| 0 — Link-out | `tenancy.mode: single` + a "Book Now" link to the deployed instance | Works today, zero code |
| 1 — Themed iframe embed | `/embed`, a chromeless route the widget's iframe points at | **Shipped** |
| 2 — JS widget SDK | `frontend/public/embed.js` — the actual `<script>` snippet | **Shipped, button and buttonless modes** |

## How it works

**One deployment = one business.** Every adopter runs their own deployment
pinned via `tenancy.mode: "single"` + `tenancy.providerCode`. That's what
lets the widget script carry zero business/provider identifier — its own
`src` origin *is* the business — and it's why `/embed` needs no dynamic
route segment; it always resolves the one pinned provider the same way the
main app's `(app)` group already does.

1. A business pastes `<script src="https://<their-deployment>/embed.js" async></script>`
   into their site.
2. The script (`frontend/public/embed.js`, plain vanilla JS, no build step,
   no dependencies) injects a floating launcher button. Nothing else loads
   until it's clicked.
3. Clicking it lazily creates a backdrop + modal with an
   `<iframe src="<origin>/embed">` inside — the same booking flow the main
   app uses (`ProviderProfile`/`BookingFlow`, reused as-is, not forked),
   just chromeless (`frontend/src/app/embed/{layout,page}.tsx`,
   `embed/calendar/page.tsx`).
4. The iframe posts `{type: "codaro:resize", height}` to its parent via a
   `ResizeObserver` (`embed/layout.tsx`); the widget script listens and
   resizes the modal to fit real content, not a fixed guess.
5. An unauthenticated visitor sees an in-frame login panel
   (`components/embed/login-panel.tsx`) instead of a redirect to `/login`
   (`AuthGate`'s `fallback` prop) — an iframe must never navigate its own
   top-level location out.

## Auth: two paths, one identity model

Both produce a normal, permanent, real-email Supabase session by the time a
booking is created — there's no separate "guest" identity tier, just two
ways in:

- **Email one-time code (default, shown first)** —
  `components/embed/guest-otp-form.tsx`, backed by `sendOtp`/`verifyOtp` on
  `useAuth()` (`frontend/src/lib/auth.tsx`). No password; an account is
  created automatically on first verification.
- **Password sign-in** — `components/auth-form.tsx`, the same component the
  main app's `/login` page uses (extracted once so both share one
  implementation instead of two that could drift), behind a
  "Already have an account? Sign in" toggle.

**Why not Supabase anonymous auth**, which was the original plan: two hard
blockers, not just an auth-layer gap. `create_booking`
(`backend/app/routers/bookings.py`) rejects a user with no email, and
`bookings.client_email` is `NOT NULL` in the frozen schema — this app's whole
identity model is email-centric by design (`supabase/schema.sql`, "no
passwords: users are identified by email/userid only"). Closing that gap for
true zero-email checkout would need either an email-linking step before
every booking or an exception to the "frozen schema" rule. Email OTP
sidesteps both — a real, verified email from the first step — and needed
**zero backend or schema changes**: `_resolve_role`'s insert-if-missing
`profiles` seeding and `create_booking`'s email check already handle it
correctly, since it's just a different sign-in method on the same identity
model, not a second one.

## Theming

`theme.primaryColor`/`radius`/`logoUrl`/`fontFamily` in `domain.config.json`
apply inside the iframe (`embed/layout.tsx`), scoped to the embed tree only —
the main `(app)` tree never applied `theme.*` either (still true; see
`backend/CLAUDE.md`'s "Declared but NOT enforced" table), so this doesn't
change existing behavior anywhere else. The widget script itself carries no
`data-primary-color`/`data-provider-code` attributes — both would duplicate
information that already lives in one place (the script's own `src` origin,
and the deployment's own config), and two sources of truth for the same
thing is worse than one, not more flexible. The widget-level attributes are
`data-label` (launcher button text) and `data-mode` (see below).

## Dogfooding: the project's own landing page runs the widget

The project's own public site is `frontend/src/app/page.tsx` — back inside
`frontend/` as a single Next.js app again (see root [CLAUDE.md](../CLAUDE.md)).
It loads `embed.js` with `data-mode="buttonless"` whenever the deployment is
single-tenant (the same `getTenancy()` check `/login`'s business-signup link
already used), and its own Login / Get Started / Sign in buttons call
`window.Arbor.open()` to raise the widget modal instead of navigating away —
falling back to a plain `href="/login"` navigation if the script hasn't
loaded yet (no-JS, middle-click, open-in-new-tab). This proves the widget end
to end on a real page the project actually ships, not just a throwaway test
host. [`example.html`](example.html) remains the *third-party* proof: a
plain, framework-free page with zero relationship to this repo, using the
default floating-button mode — the more honest demonstration of "any
business's site can embed this" than the project's own site would be on its
own, which is why both exist rather than just one.

(An earlier version of this project air-gapped the landing page into its own
deployable specifically so it would *not* load `embed.js` — see
`docs/issues/97-air-gapping-the-landing-page-from-the-rest-of-the-app.md` for
that design and why it was later reverted.)

## Conventions

- **This folder is additive.** No changes to `backend/app/routers/*`,
  `supabase/schema.sql`, or any existing `(app)` route's behavior for a
  non-embedded visitor. The only exceptions, both additive: the
  `theme.logoUrl`/`theme.fontFamily` config keys, and the new `/embed` tree
  itself.
- **The embed route is a *consumer* of existing components, not a fork.**
  If a component can't be reused as-is because it assumes `(app)` layout
  context, fix that assumption in place (an additive prop, an injectable
  dependency) rather than copy the component. `AuthGate`'s `fallback` prop
  and `ProviderProfile`'s `calendarHref`/`showMessage` props exist because of
  this rule.
- **No new backend auth model.** Bearer-token JWT, same as the main app — no
  cookie session, no separate API key system. This is what makes cross-site
  embedding possible without a third-party-cookie workaround in the first
  place; don't reintroduce that problem.
- **`embed.js` stays dependency-free at the consumer end.** Hand-written
  vanilla JS, no bundler — a business should be able to read the whole file
  before pasting it into their site.
- **No `frame-ancestors` restriction, deliberately.** This route is meant to
  be embedded by any third-party site with zero config — a fixed domain
  allowlist would defeat that unless a business also registers its domain
  somewhere first, which nothing here requires. The real security boundary
  is bearer-token auth + RLS, not who's allowed to iframe the page.
- **`window.Arbor` is the public open/close API** (`{ open, close }`), set
  unconditionally once `embed.js` runs — a host page checks `if
  (window.Arbor)` before calling it (covers the brief window before the
  script has parsed) rather than assuming it's always present.
  `data-mode="buttonless"` skips the floating launcher but still sets
  `window.Arbor` and runs the same modal/iframe/resize machinery; use it
  when the host page supplies its own buttons instead of the default one.

## Don't

- Don't add a second booking UI. The embed renders the *same* booking flow
  the main app uses, just chromeless — two implementations of "pick a slot
  and confirm" will drift.
- Don't add `data-provider-code`/`data-primary-color` (or similar) to the
  widget script — both would duplicate what the script's `src` origin and
  the deployment's own config already carry.
- Don't scope `booking.options[]` (add-ons/insurance, declared in config, no
  reader) or recurring weekly opening hours (no schema representation at
  all, `timing.blackouts[]` is date-range only) into this folder's work —
  they're `backend/`-owned config/rules gaps that recur across many pivot
  ideas, not embed-specific; fixing them happens in
  `backend/app/config_schema.py`/`app/rules.py` if a pilot adopter blocks on
  either.
- Don't touch `supabase/schema.sql` or any base table for anything here —
  nothing in this folder needs a new table or column.

## Not built (deliberate cuts, not gaps)

- **`data-mode="inline"`** (render into a host-page container instead of a
  floating button) — button mode covers the "one script tag, nothing else to
  configure" ask directly; inline is a plausible fast-follow, not attempted.
- **Escape-to-close is best-effort.** It's a `keydown` listener on the
  parent document; a keydown fired while focus is inside the iframe's own
  document (e.g. mid-form-fill) doesn't bubble to the parent — a real,
  confirmed cross-frame keyboard-event limitation. The × button and
  backdrop-click both work regardless of focus and are the reliable paths.

## Testing

`frontend/` has its own Vitest + React Testing Library harness (`npm test`,
config at `frontend/vitest.config.mts`) — not `test/` (that tree is
Python/pytest, owned by `test-writer`; frontend test tooling is a decision
for whoever owns `frontend/`, made and documented in `test/CLAUDE.md`).
Covered: `AuthGate`'s `fallback` prop, `AuthForm`, `GuestOtpForm`, and
`EmbedLayout`'s `ResizeObserver`/postMessage wiring (mocked `useAuth()`/
`next/navigation`/`@/api`/`AppProvider`, a `ResizeObserver` stub, a
deliberately-overridden `window.parent`) — 17 tests, no network dependency.
**Not covered**: `/embed`'s `page.tsx`/`calendar/page.tsx` themselves (need
a real DOM/router integration harness, bigger lift than component tests)
and a real `verifyOtp` code round-trip (blocked by this Supabase project
having no production email provider configured — see [TODO.md](TODO.md)).
