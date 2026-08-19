# 91 — Pivot presets: render the config's vocabulary and theme

Branch: `91-pivot-presets`

## The gap

An end-to-end check of the pivot system against a live `community-allotment-plots`
config found the backend half complete and the frontend half largely absent.

The backend serves the whole pivot file at `GET /config` and consumes it
properly: `scripts/check_pivots.py` reports **100/100 pivots expressible** and
**97/100 quoted totals matching a hand computation**, `make checkseed` reports
RESET 9/9 and MATCH 10/10, and `timing.confirmation: request_approve` correctly
propagates to `Service.autoApprove: false`.

The frontend read four things from that payload — `tenancy`, `location`,
`capabilities`, and `search.facets` — and nothing else. In particular:

- **`terms`** was served and ignored. The config declared `service: "Plan"`,
  `slot: "Billing period"`, `booking: "Subscription"`, `client: "Customer"`;
  the UI rendered `src/config/verticals.ts`, a static file with three hardcoded
  demo verticals. With `/demo/vertical` returning `oneToOne`, every screen read
  *"Tutor studio / Subject / Tutor / Search tutors"* over allotment-plot data.
- **`theme`** (`primaryColor: "#15803d"`, `radius: "0.5rem"`) was served and
  wired to no CSS variable.
- **`copy`** shipped ten keys — including `confirmTitle`, `emptyStateSlots`,
  `emptyStateBookings`, `requestPending` — with zero call sites. The
  `request_approve` pivot lands bookings as `pending` and the result screen
  still said *"You're booked"*.

This is the "looks live, does nothing" failure that `rules.capability()`'s own
docstring exists to prevent, applied to vocabulary instead of gates.

## What changed

| File | Change |
|---|---|
| `frontend/src/api/index.ts` | `PivotConfig` gains `terms` / `copy` / `theme`; added `FALLBACK_PIVOT_CONFIG` so both contexts share one degraded-mode value |
| `frontend/src/config/verticals.ts` | New `applyPivotVocabulary(base, terms, copy)` overlay |
| `frontend/src/lib/pivot-theme.ts` | **New.** Applies `theme` to the `--primary` / `--radius` tokens |
| `frontend/src/context/app-context.tsx` | Applies the overlay + theme at boot; exposes `copy` |
| `frontend/src/context/owner-context.tsx` | Same overlay, so the owner console and customer side agree |
| `frontend/src/components/booking/result-screen.tsx` | `copy.confirmTitle`, and `copy.requestPending` when the booking is `pending` |
| `frontend/src/app/(app)/bookings/page.tsx` | `copy.emptyStateBookings` |

### Why an overlay rather than replacing `verticals.ts`

The three static verticals are *demo* vocabulary — they exist so the seeded
fleet/tutoring/yoga datasets read naturally, and they carry two things `terms`
cannot express. So the config wins where it speaks and the vertical fills the
rest. Three fields are deliberately not overridden:

- **`bookingVerb`** always comes from the vertical. `terms.booking` is a noun
  ("Subscription"); using it as the CTA renders a button reading *"Subscription"*
  instead of *"Book"*.
- **`partyNoun`** is overridden only when the vertical already has one. `null`
  is a *structural* signal — "this vertical has no party-size concept" — and it
  drives whether the party stepper renders at all. `terms.party` is always
  populated (it defaults to `"Guests"`), so a blanket override would surface a
  party control on every one-to-one deployment.
- **`categories`** stay static: they must match the `categoryId`s the backend
  actually seeded, which `terms` says nothing about.

### Theme application

`theme` maps onto `--primary` / `--radius`, tokens `app/globals.css` already
defines and every Tailwind utility already derives from — so overriding two
variables repaints the app without touching a component. They are written as an
inline style on `:root`, which outranks both the stylesheet's `:root` rule and
its `.dark` block; that is intentional, since a configured brand colour is the
brand in both themes. `--primary-foreground` is derived from the colour's
relative luminance, because the stylesheet's pairing is tuned for the default
pink and a mid-tone brand would otherwise get unreadable text. A non-hex value
(`oklch(...)`, a `var()`) keeps the stylesheet's own pairing. Null fields clear
the override rather than stranding the previous pivot's colour, so `make reload`
after editing the theme away actually reverts it.

## Verification

- `tsc --noEmit` — 0 errors in `src/`
- `eslint src` — 21 warnings before the change, 21 after; no new issues
- `next build` — passes, all 24 routes
- Overlay run against the live config: `Subject → Plan`, `Tutors → Plans`,
  `"No open hours in this period." → "No billing periods available yet."`,
  `label → "Community Allotment Plots"`
- `partyNoun` semantics hold: `oneToOne` stays `null`; `group` goes
  `spots → Guests`
- **Empty config is byte-identical to the static vertical** — a config that
  declares no `terms`/`copy` produces exactly the pre-change behaviour
- Live routes `/`, `/search`, `/owner`, `/bookings`, `/login` all 200

## Known-remaining, deliberately out of scope

The *shape-changing* v2 blocks are still not rendered: `pricing.model`,
`booking.granularity` / `unitKind` / `duration.mode`, `payments.flow`,
`inventory`, `prerequisites`, `recurrence`, `entitlements`, `discovery.mode`.
The current pivot declares `pricing.model: subscription`, `granularity: month`,
`duration.mode: open_ended`, `payments.flow: invoice_after` and
`billingCycle: annual`; the UI shows a flat `6500 EUR` against a 30-minute slot.

Relatedly, only two capabilities are gated anywhere — `reviews`
(`bookings.py:532`, `bookings.py:612`) and `follows` (`providers.py:332`), each
mirrored in the UI. The other six (`payments`, `inventory`, `waitlist`,
`quotes`, `cart`, `entitlements`) are validated and served but have no endpoint
and no surface, so there is nothing to gate yet. This is known scope, not silent
breakage — `check_pivots.py` lists these as unbuilt rather than pretending they
are wired. Rendering them needs backend endpoints first.

## Test-suite note (pre-existing, not introduced here)

`test/` runs 1024 passing / 1 failing, but the failure **moves between runs**:
one run failed `e2e/test_live_api.py::test_create_reschedule_cancel_lifecycle`,
which then passed in isolation; a re-run failed
`test_demo_user_has_seeded_bookings` instead. The `e2e/` tests reseed the shared
live Supabase mid-suite (`Seeded vertical fleet` appears in the run log), so they
race each other and clobber whatever pivot data is loaded. Worth an issue of its
own: the e2e tests need an isolated dataset, and running them currently destroys
the local demo seed (recoverable with `make reseed`).
