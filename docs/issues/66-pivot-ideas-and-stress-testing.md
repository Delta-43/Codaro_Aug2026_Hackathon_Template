# 66 — Plug-and-play: the embeddable booking widget

Rebuilds the plugin/embed feature (`plugin_sdk/`, `/embed`, `embed.js`) on
this branch, then merges the standalone `landing/` deployable (#97) back into
`frontend/` and wires the landing page's own login buttons to the widget.
Two phases, described in order below.

## Phase 1 — rebuilding the plugin/embed feature

Targeted the `landing/`/`frontend/` air-gapped layout (#97) at the time.
The previous implementation on this branch was preserved at git tag
`archive/66-pivot-ideas-pre-reset` before the branch was reset to `develop`'s
tip, and served as the design blueprint here — but was re-derived against
today's `frontend/`, not reapplied as a patch, since several of the files it
touched (`api/index.ts`, `config_schema.py`, `/login`) had gained real,
unrelated features since (`capabilities` on `PivotConfig`, `config/buttons.ts`,
a redesigned login page) that a literal patch would have regressed.

## What changed

**Backend — additive config only**: `theme.logoUrl`/`theme.fontFamily` added
to `config_schema.py`'s `DEFAULTS` and both shipped config files
(`domain.config.json`, `domain.config.medical.example.json` — the latter
needed updating too, or the existing
`test_both_shipped_config_files_are_normalize_fixpoints_and_valid` test would
have broken).

**`frontend/src/api/index.ts`**: `PivotConfig` gained a `theme: ThemeConfig`
field, added alongside the existing `tenancy`/`location`/`capabilities` —
not replacing them.

**Small additive props on existing shared components** (the "consumer, not
fork" rule `plugin_sdk/CLAUDE.md` sets out): `AuthGate` gained an optional
`fallback` prop (render in place instead of redirecting — an iframe must
never navigate its own top-level location out); `ProviderProfile` gained
`showMessage`/`calendarHref`; `useAuth()` gained `sendOtp`/`verifyOtp`
(passwordless email-code sign-in, no backend/schema changes needed — see
`plugin_sdk/CLAUDE.md`'s "Why not Supabase anonymous auth").

**Extracted `frontend/src/components/auth-form.tsx`** from `/login`'s
sign-in/sign-up form body, so both `/login` and the embed's login panel share
one implementation. Re-derived against `/login`'s current state (which had
grown a glass background, `buttonFx`, and demo-mode shortcuts since the
archived version) rather than the old diff.

**New, net-new files** (no conflicts possible): `frontend/src/app/embed/`
(chromeless `/embed` + `/embed/calendar`, reusing `ProviderProfile`/
`BookingFlow`/`AppProvider` unmodified), `frontend/src/components/embed/`
(`login-panel.tsx`, `guest-otp-form.tsx`), `frontend/public/embed.js` (the
adopter-facing widget script, vanilla JS, no build step), and `plugin_sdk/`
itself (`README.md`, `CLAUDE.md`, `TODO.md`, `example.html`).

**`plugin_sdk/CLAUDE.md`'s "dogfooding" section was rewritten**, not just
ported: at this point in the branch `landing/` was still air-gapped with zero
API calls, so loading `embed.js` there would have reintroduced coupling for a
weaker demo than the alternative — `landing/` stayed the live Tier-0
(link-out) example and `plugin_sdk/example.html` (a plain, framework-free
static page) was the Tier-2 (widget) example. **Superseded by Phase 2
below** — `landing/` no longer exists as a separate thing.

**Test infra**: re-added `frontend/`'s Vitest + React Testing Library setup
(`vitest.config.mts`, `vitest.setup.ts`, the same 17 tests covering
`AuthGate`'s fallback, `AuthForm`, `GuestOtpForm`, and `EmbedLayout`'s resize
wiring) plus a `frontend` CI test step — the old branch had this suite but
never wired it into `.github/workflows/ci.yml`; this does.

One dependency swap found live: `jsdom@^30.0.1` (what the archive pinned)
fails under Node 20 (`webidl.util.markAsUncloneable is not a function`,
undici's bundled `CacheStorage` needs a newer Node). Pinned `jsdom@^27` instead.

**Phase 1 verified**: `frontend` (`eslint`/`knip`/`tsc --noEmit`/`npm test`
17 passed/`npm run build`) and `backend` (full `pytest test/backend`, 1017
passed, + `ruff check .`) both clean in Docker;
`python .github/scripts/validate_domain_config.py` passes; live against
`make start`, `/config` served the new `theme` keys and `/embed`/`embed.js`
worked from `frontend/`'s deployment; `git diff` under `landing/` was empty
at this point — this phase touched nothing there.

## Phase 2 — merging `landing/` back into `frontend/`

After Phase 1 shipped, the team decided the 3-container split (`landing/` as
its own app/build/port) cost more in resource/deployment overhead than it
was worth for this project. Reversed it: `landing/` moves back inside
`frontend/` — one Next.js app, one Docker container again — and, since the
plugin/embed widget from Phase 1 already existed, the landing page's own
Login/Get Started/Sign in buttons were wired to open the *real* widget modal
instead of just navigating to `/login`, dogfooding Tier 2 on the project's
own page (not just `plugin_sdk/example.html`).

**Moved back**: `landing/src/app/page.tsx` → `frontend/src/app/page.tsx`;
`landing/src/components/landing/*` (15 files, including `scroll-top-link.tsx`)
→ `frontend/src/components/landing/`. **Deleted, not moved**: the 6 files
`landing/` kept as frozen copies of things `frontend/` already had for real
(`components/calendar/*`, `theme-toggle.tsx`, `ui/button.tsx`, `lib/*`,
`types/domain.ts`, `config/buttons.ts`) — `frontend/`'s were newer
(post-`buttonFx`) in two cases. `frontend/src/types/domain.ts`'s `SlotStatus`
type, un-exported during the split since landing's frozen copy was the only
external consumer, is exported again now that `calendar-demo.tsx` is back.
Reconciled one file both sides had touched independently:
`components/landing/scroll-reveal.tsx` — took landing's full version
(`GlassPanel` + `useScrollMotion`) over `frontend/`'s trimmed one (`/login`
only needed `GlassPanel`); the full version is a superset, so `/login` still
works. Deleted `landing/` entirely and reverted `docker-compose.yml`,
`Makefile`, `README.md`, root `CLAUDE.md`, `frontend/CLAUDE.md`, and
`.github/workflows/ci.yml` (dropped the now-dead `landing` CI job) back to
describing two services, not three.

**`useAuth()` restored** in `page.tsx`/`nav-bar.tsx`/`hero.tsx`/
`business-cta.tsx`/`footer.tsx` — back to the original `authed ? "/search" :
"/login"` pattern with real `next/link`, no more `NEXT_PUBLIC_APP_URL`
cross-origin plumbing. The one deliberate change from the original,
pre-split design: every logged-out-path CTA's `onClick` now checks
`window.Arbor` first —

```tsx
onClick={authed ? undefined : (e) => {
  if (window.Arbor) { e.preventDefault(); window.Arbor.open(); }
}}
```

— opening the widget modal when the script's loaded, falling through to the
real `href="/login"` navigation otherwise (no-JS visitors, middle-click,
open-in-new-tab, and the brief pre-hydration window all still work). The
authed path (`"Open app"` → `/search`) is untouched — no reason to show a
login modal to someone already signed in. `frontend/src/types/global.d.ts`
declares `Window.Arbor` for TypeScript.

**`embed.js`** gained a public API — `window.Arbor = { open: openModal,
close: closeModal }`, set once at script init — and a `data-mode="buttonless"`
attribute that skips the auto-injected floating launcher while still exposing
that API, so a host page can drive the modal from its own button(s) instead
of (or in addition to) the default one. Both are genuinely reusable by any
real adopter, not landing-specific. `page.tsx` loads the script with
`data-mode="buttonless"`, gated on `tenancy.mode === "single"` exactly like
the pre-split design gated it.

`plugin_sdk/CLAUDE.md`'s "dogfooding" section, `README.md`'s Attributes
table and "Testing locally" note, and `TODO.md`'s "Not planned" bullet were
all updated to describe this as the actual current behavior.

**Phase 2 verified**: this work was done by two agents in sequence — one
executing the merge, a second independently writing tests and re-checking
the result (explicitly briefed to flag problems, not rubber-stamp). Combined:
`eslint`/`knip`/`tsc --noEmit`/`npm run build` clean; `npm test` **29/29**
passed (17 pre-existing unmodified + 12 new — `nav-bar.test.tsx`/
`hero.test.tsx`/`business-cta.test.tsx`/`footer.test.tsx`, each covering
`window.Arbor` present-and-logged-out → `open()` called, absent → real
`/login` navigation attempted, and `authed=true` → `open()` never called
even when `window.Arbor` exists); `python .github/scripts/validate_domain_config.py`
passes; live `make start` showed only `backend`+`frontend` containers (no
`landing`), and curl'd HTML confirmed every landing section/marker present
unchanged and `href="/login"` intact on all four buttons. The second agent's
independent review found the four `window.Arbor` call sites byte-for-byte
consistent with no stale-closure risk (read inside the click handler, not
captured at render time) and flagged no bugs.

**Not click-tested end to end in a real browser** in either phase — no
browser-automation tool is available in this environment. Verified via the
unit suite, live HTTP/curl checks, and DOM-fragment inspection instead.
Worth a manual pass through `plugin_sdk/README.md`'s "Testing locally" steps,
and clicking through the landing page itself, before merge.
