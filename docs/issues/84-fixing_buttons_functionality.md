# 84 — Button mechanics config + platform-wide interactivity fixes

Branch: `84-fixing_buttons_functionality`

## Goal

Give the platform a **single, easily-changeable config file** for how buttons and
interactive elements *feel*, then apply that feel consistently across the whole
product (not just the landing page), plus a batch of related UI fixes on
messaging, navigation, login, profile, calendar, and settings.

## What changed

### The single source of truth — `frontend/src/config/buttons.ts`

All interaction "feel" lives in one file. Change a value here and every matching
element across landing, login, and the app updates with it. Tokens:

| Token | Applied to | Effect |
|-------|-----------|--------|
| `press` | **every** `<Button>`/CTA (baked into the `buttonVariants` base) | gentle hover-grow |
| `pill` | primary CTAs / floating controls | rounded pill shape |
| `link` | text/nav links, avatars | stronger hover-grow |
| `surface` | clickable cards & list rows (bookings, services, conversations, review plates) | full muted fill + pink-tinted border on hover |
| `tile` | calendar day cells | pink hover tint |
| `star` | rating stars | lively hover-grow (matches landing testimonials) |

`press` is baked into `ui/button.tsx`, so the landing `<Link className={buttonVariants(...)}>`
CTAs and the app's `<Button>`s share it automatically.

### Landing / login

- Landing nav CTA + hero/docs/business CTAs now pull their pill+feel from the config
  (de-duplicated the copy-pasted inline classes).
- Landing nav brand is **pink** and smooth-scrolls to the top of the page
  (the page scrolls inside `<main>`, not the window — new `landing/scroll-top-link.tsx`
  finds that container). Footer brand uses the same; the footer's tree-leaf badge
  was removed and its plate narrowed (`max-w-5xl` → `max-w-4xl`).
- Customer **login is now a real liquid-glass plate** (same `SceneBackground` +
  `GlassPanel` as the landing), the "Arbor" title links to the landing page, and the
  Email/Password labels are centered + interactive. Business login got the
  Arbor-link + centered-label treatment (its distinct amber card kept intentionally).

### Messaging

- **Unread badge fixed**: `use-unread-count.ts` now refetches on route change and on
  an explicit `arbor:unread-changed` event (fired by the thread when it marks read),
  not just `window.focus` — SPA navigation never fires focus, which left the badge
  stale after reading a thread.
- Conversation rows get the clearer `surface` hover (unread rows deepen their accent).

### Navigation shells (customer `app-shell` + business `business-shell`)

- Mobile shows a single title: pink **Arbor** (→ landing) on the left, page name on
  the right; the page's own `<h1>` is `sr-only` on mobile (killed the duplicate title).
- Brand links point to `/` (were `/search` / `/owner`).
- Top-bar page names are now interactive: clicking scrolls the page to top, with a
  hover-grow. The hover-zoom **no longer clips** — the clip boundary moved onto the
  button itself (it self-truncates) instead of an `overflow-hidden` ancestor.
- Bottom-nav tabs are `group`s; hovering grows the icon.

### Profile (`account`)

- Removed the redundant "Manage your account in Settings." line.
- Settings cog is **pink + interactive**.
- Review plates get the `surface` hover; stars and avatars (main + per-review) grow on
  hover like the landing.

### Calendar / bookings / services

- Booking cards, service cards, and calendar day cells get more explicit hover
  (`surface` / `tile`).
- Bookings Upcoming/Past toggle carries the button press-feel.

### Settings panel

- **"Delete my data" link → "Delete account" button** (same `ShieldAlert` icon, same
  destructive color); the Account plate is now a symmetrical row (Sign out + Delete,
  both `size="sm"`).
- All plate titles hover-grow; notification toggles and the demo-use-case buttons carry
  the press-feel.

## Verification

- `python3 .github/scripts/validate_domain_config.py` → ✓
- `npx tsc --noEmit` → ✓ clean
- `pytest` → 1024 passed, **1 pre-existing failure** unrelated to this issue:
  `test_live_api.py::test_create_reschedule_cancel_lifecycle` (live-API/shared-DB e2e
  flake — picks a multi-slot service and posts one slot → `INVALID_RANGE`). This
  session changed only `frontend/src`; no backend/config/test files were touched.
- Landing, messaging, profile, settings changes were verified live in the browser
  (computed colors/classes + no console errors); the gated app views were checked with
  an active session.

## Files touched

`frontend/src/config/buttons.ts` (core), `components/ui/button.tsx`,
`components/landing/{nav-bar,hero,docs-cta,business-cta,footer,scroll-top-link}.tsx`,
`app/login/page.tsx`, `app/login/business/page.tsx`,
`hooks/use-unread-count.ts`, `components/messaging/{message-thread,conversation-list}.tsx`,
`components/{app-shell}.tsx`, `components/business/business-shell.tsx`,
`app/(app)/{bookings,messages,account}/page.tsx`,
`components/booking/booking-card.tsx`, `components/provider/provider-profile.tsx`,
`components/calendar/month-view.tsx`, `components/settings/settings-panel.tsx`.
