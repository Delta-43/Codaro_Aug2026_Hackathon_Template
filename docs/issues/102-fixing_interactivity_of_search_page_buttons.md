# 102 — Generalize the landing-page interactivity into one config, applied platform-wide

## What & why

The delightful hover/press "feel" the landing page shipped with had been added
to buttons piecemeal, and the **search page's own controls (Filter, category
Chips, Clear) were bypassing it entirely** — the issue's named trigger. This
turns that feel into a single, pivot-editable **interactivity config** and
routes *every* interactive element on the platform through it: buttons, links,
cards/rows, calendar tiles, rating stars, headings, clickable icons, and the
`>` row chevrons. A rule doc makes "always use the config" the standing
convention for future pivots/agents. Also: the login front door gained a theme
control so it can follow (or be pinned against) the OS light/dark setting.

## The config (`frontend/src/config/buttons.ts` → `buttonFx`)

Kept as the existing TypeScript config (not a separate JSON) so it stays
type-checked and Tailwind keeps scanning the class strings. Extended from 6 to
**9 roles** — the three new ones cover the elements the issue called out by
name:

| Token | Role | Feel |
|-------|------|------|
| `press` | real buttons / pills / icon-buttons / toggles (baked into `<Button>`) | grow scale-105 |
| `pill` | round CTAs | `rounded-full` |
| `link` | standalone text/nav links | grow scale-110 |
| `surface` | clickable cards & list rows | muted fill + primary border on hover |
| `tile` | calendar day cells | pink hover tint |
| `star` | interactive rating stars | grow scale-150 (landing feel) |
| **`heading`** *(new)* | interactive titles / wordmarks | grow scale-105, origin-left |
| **`icon`** *(new)* | bare clickable icons | grow scale-110 |
| **`chevron`** *(new)* | `>` at a row's end | nudges on the row's `group` hover |

## The rule for future pivots

- New file **`docs/interactivity.md`** — the token table, the two gotchas
  (scale needs `transition-all`; `chevron` is a group-hover), the "don't scale
  inline prose links" rule, and the standing instruction: **any new/changed
  interactive element pulls a `buttonFx` token; add a role there if none fits —
  never hard-code the feel at the call site.**
- Pointer added to **`frontend/CLAUDE.md`** Conventions so agents load it.
- `landing/` keeps its own frozen `buttonFx` copy (separate deployable); the new
  roles are frontend-only and documented as such.

## Applied everywhere (~30 components/pages)

- **Search (named focus):** Filter button, category Chips, Clear link, provider
  cards (surface), code-scan targets.
- **Shells:** `app-shell` + `business-shell` — page-title / wordmark / brand
  headings now use `heading`; cart & nav icon-buttons use `press`. (Replaced the
  duplicated inline scale-strings from #84.)
- **Cards & rows:** booking cards, conversation rows, provider service rows,
  following-business slices, resource picker, owner booking rows → `surface`,
  each with a `group` + `chevron` nudge where a `>` sits at the end.
- **Calendar:** slot pills, day-view rows, zoom toggles, owner booking-calendar
  (nav arrows, day cells → `tile`, booking pills, view segmented).
- **Stars:** the review-form and owner "rate customer" inputs → `star`. (Static
  `aria-hidden` rating displays are left alone — they aren't interactive.)
- **Icons/controls:** theme-toggle, modal & dialog close buttons, message-thread
  back/cancel, appearance picker, notification/auto-approve switches, docs chips
  and Home link.

## Login theme (system light/dark)

Theming was already `defaultTheme="system"`, but the login pages had no control
and a previously-pinned choice would override the OS. Added the 3-way
`AppearancePicker` (Light / Dark / **Smart** = system) to the top-right of both
`/login` and `/login/business`, so the front door adjusts to — and by default
follows — the system setting before sign-in.

## Verification

- `npx tsc --noEmit` → clean.
- `npx knip` → clean (exit 0; only the benign `.css` config hint).
- Live (Docker preview, `/search`): Filter button and Chips carry
  `hover:scale-105 transition-all`; non-followed provider cards carry the
  `surface` hover (`hover:border-primary/40 hover:bg-muted`) while followed cards
  keep their accent branch. Only pre-existing backend-CORS console errors (this
  preview runs on a non-allowlisted port) — none from the UI changes.
- ESLint is not configured in the repo, so there is no lint gate to run.

`/login` couldn't be viewed live (an active session redirects it to `/search`,
as in prior sessions); it reuses the already-verified `AppearancePicker` and
compiles clean.

## Round 2 — targeted polish pass

A second, detailed pass from user feedback. New shared token: **`pink`**
(`hover:text-primary`) — the platform's "turn pink on hover," now a role in
`buttonFx`.

**Login**
- Removed the front-door appearance control (kept `defaultTheme="system"`, so it
  still follows the OS); the explicit toggle now lives only in Settings.
- "Demo Mode" buttons turn pink on hover; the sign-up agree **checkbox** grows
  on hover (cursor-pointer + `press`).

**Nav / shells (both customer + business)**
- Top page-title and account/business label made larger (`text-base`) and
  interactive; the account label link turns pink + presses.
- Desktop side-rail nav icons now scale on hover and the row turns pink;
  bottom-tab hover is pink too. Cart icon turns pink + presses.
- **Sign out** is a shared `SignOutButton` (side rails + Settings) with a
  confirmation dialog ("Sign out of Arbor?") and a pink hover. `ConfirmDialog`
  gained a calm `tone="primary"` + custom `icon` (it was destructive-only).

**Search**
- Followed provider card no longer wears a permanent pink glow — the ring/border
  emphasis is now hover-only.
- The provider preview (opening an account) has interactive avatar, name and
  ★ rating.

**Services (provider profile)**
- Avatar, name, ★ rating and the external-link chips are interactive; chips turn
  pink on hover.

**Calendar**
- month/week/day toggles turn pink on hover. **Responsive fix:** the 7-column
  week view was clipping on phones — it now scrolls horizontally inside its own
  container (`min-w-[34rem]` + `overflow-x-auto`), so the page body no longer
  overflows (verified at 280px).

**Reservations / Settings duplicate titles**
- The page `<h1>` on Bookings and the Settings panel were showing a second
  visible title under the shell's mobile header — both are now `sr-only`, so the
  shell top bar is the single visible title.

**Profile (account)**
- Settings cog darkens to full pink on hover; the verified badge is interactive.

**Settings panel**
- Appearance row slimmed: removed the Palette "Theme" label and the
  `AppearancePicker`'s redundant caption (compact 3-button control).
- All neutral buttons (Change password, Sign out) turn pink on hover; Delete
  account stays destructive-red.
- Notification rows: the bell icons scale + turn pink on row hover; switches
  already press.
- Profile fields interactive: the display-name/email/password **labels** and the
  profile **name** grow on hover.
- Account plate is now two equal-width buttons (`grid-cols-2`) — symmetrical.

**Verification (round 2):** `tsc` + `knip` clean; live at 280px — login (no
appearance control, pink demo buttons, interactive checkbox), followed-card
hover-only glow, nav icon scale + cart pink + account interactive, single visible
title on Bookings & Settings, symmetric account plate, sign-out confirm dialog
(primary tone), search-preview + provider-profile avatar/name/star interactive,
calendar zoom pink, and the week view scrolling internally with no page overflow.
No console errors.

**Open interpretation:** "appearance same as landing" was read as *consistent +
interactive*; kept the 3-way Light/Dark/Smart picker (Smart = system) rather than
swapping in landing's 2-state sun/moon toggle, since it also exposes "follow
system." Easy to switch if the 2-state look is what's wanted.

## Round 3 — nav sizing, calendar toggles, settings appearance

- **Nav bar:** page-title enlarged to `text-lg` and coloured **pink**
  (`text-primary`) on both the desktop top bar and the mobile header — the open
  page now reads pink at tablet/desktop widths. Account/business label bumped to
  `text-base`. (Verified: 18px pink title at 280px and 1024px; 16px account
  label.)
- **Calendar toggles:** the month/week/day segment now scrolls horizontally when
  the viewport is too narrow (`overflow-x-auto` + `shrink-0` buttons) instead of
  overflowing. The **owner** booking-calendar segment was grey when active — now
  pink when chosen (`bg-primary`) and pink on hover, and its header row wraps
  (`flex-wrap`) so the segment can't collide with the date nav. (Verified: at
  280px the customer toggle scrolls, active is pink, page has no horizontal
  overflow.)
- **Settings:** the editable Display-name **label** had missed the interactive
  treatment — fixed; all field labels now grow **and** turn pink on hover. The
  **Appearance** plate was a lonely full-width button row — restructured so the
  Light/Dark/Smart control sits on the **right**, vertically centred against the
  "Appearance" label + description (balanced, aligned). (Verified: label
  interactive; appearance is a centred row with the picker on the right.)

**Verification (round 3):** `tsc` + `knip` clean; live checks above at 280px and
1024px; no console errors.
