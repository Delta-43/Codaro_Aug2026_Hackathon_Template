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

---

# Part 2 — enforcing what the config declares

The work above made the pivot file's *vocabulary* real. This part does the same
for its *behaviour*: every block that was validated and served but read by
nothing.

## The shape of the problem

An audit of all 153 config leaf paths, done by perturbing each key and diffing
what the frontend actually receives, found three categories:

- **read** — `tenancy`, `location`, `capabilities`, `search.facets`, plus the
  `terms`/`copy`/`theme` wired in Part 1;
- **reaching the UI indirectly** — 17 leaves that shape a serialized payload;
- **inert** — entire blocks (`payments`, `inventory`, `recurrence`,
  `entitlements`, `prerequisites`) plus `pricing.model`, which had **no effect
  whatsoever**: all seven alternative models produced byte-identical output.

## 1. Slot length follows `booking.granularity`

All 100 pivots resolved to a flat **30-minute slot** regardless of granularity.
A hotel declaring `night`, a warehouse declaring `week` and a plot lease
declaring `month` all seeded half-hour slots. It was invisible per-pivot because
each config was internally consistent; only comparing *across* pivots showed one
slot length for a hundred different businesses.

`seed_config._grid()` already had a `>= 1440` branch for day-sized units.
Nothing could ever reach it.

- `config_schema.GRANULARITY_SLOT_MINUTES` supplies the default when the config
  states no `slotDurationMinutes`. It lands in `normalize()`, so the seeder and
  `GET /services` resolve one shared value. Explicit config still wins.
- `_grid` emits `dayStep`, so a week-long unit lays one slot per week rather
  than a fresh 7-day slot every 24h (which read as sevenfold capacity).
- `daysBack` is rounded to a whole number of units so the lattice lands **on**
  today. At a flat 7 a monthly unit stepped −7/+23/+53 while
  `seed._align_to_unit_grid` anchored on 0/+30/+60; slots from the two lattices
  overlapped.
- Demo bookings are spaced by whole units, reuse the grid slot for long units
  instead of inserting a parallel one, and align to the lattice when they fall
  outside the seeded window. `_seed_requests` had a second unpatched call site
  doing the same thing.

Verified live: hotel 1440-min slots (max 14 — a 1–14 night stay); warehouse
10080-min slots with **zero overlaps**, all on-lattice; allotment a contiguous
monthly lattice where each slot ends exactly where the next begins. The 84
minute-granularity pivots are provably untouched — below 1440 the new helper
returns `_insert_dedicated_slot` directly and the spacing step is `day`.

**`scripts/check_pivot_states.py`** (`make checkstates`) is new and exists
because of this bug: it runs every pivot through load → spec → rules →
serialize, and asserts a cross-pivot invariant that a hundred businesses cannot
all run the same calendar. Verified to fail (exit 1, 32 mismatches) when the
mapping is broken.

## 2. Pricing — the UI showed a different number than it charged

`pricing.py` was fully built and already charged correctly. The UI computed
`priceMinorUnits × slots × party`, which is only the *default* pricing block's
formula. On the tiered escape room:

    party=2  engine charges 9000   UI showed 18000
    party=5  engine charges 12000  UI showed 45000

A live mispricing bug, not a missing feature. `POST /bookings/quote` runs
`_resolve_selection` + `_price` — the identical path `create_booking` takes — so
quote and charge cannot drift. Read-only, but it still validates, so an
unbookable range raises the same `ApiError` rather than pricing something that
cannot be booked.

The confirm screen renders the engine's own `breakdown`, the deposit, the
billing cycle and blocking prerequisites. On a quote failure it says so rather
than falling back to arithmetic: a wrong number is worse than none, because the
customer reads it as the price. The quote is stamped with the inputs it was
quoted for, so a party-size change cannot briefly render the previous total.

## 3. Entitlements

New `entitlements` table. `plan_key` is deliberately **not** a foreign key —
plans live in the config, so renaming or retiring one must not orphan history;
an unresolvable key goes inert.

`quote()` now reads an entitlement, closing the gap `check_pivots.py` itself
called out. The discount applies to the **service charge (base + secondary), not
fees**, so percentage fees compute off the discounted charge. That is the
conservative reading and it is deliberate: whether commission sits on net or
gross is already an open question (#65), and a member discount must not quietly
answer it a second way.

`resolve_entitlement` breaks ties on the **largest** discount, so holding two
plans never quietly charges the worse one. Credits are spent *after* the booking
row exists and best-effort — decrementing first would spend a credit for a
booking that may never exist — and the booking records `entitlement_id` so a
missed decrement is reconcilable.

## 4. Inventory — the return leg

The booking *is* the loan record, so this rides in `metadata` per the
frozen-base-table rule. The overdue fee is **computed, never stored**: it changes
with the clock. `POST /bookings/{id}/return` is owner-only by design — a customer
able to self-certify could clear their own fee.

Verified on the tool library (168h loan, 100/day): 8 days overdue → fee 800 →
returned → fee frozen at 800. Double-return refused, client 403.

## 5. Recurrence

`POST /bookings` takes an optional `repeat`. Two things wrong on the first
attempt: the **whole span** repeats, not just its first slot (booking one slot
failed `minSlotsPerBooking` on every occurrence), and monthly steps **clamp to
the last valid day** so a series starting on the 31st does not skip February.
`count` is clamped to `recurrence.maxOccurrences` server-side.

The first occurrence must succeed on its own merits; later ones are best-effort
and land only where the business actually opened a slot. Ones that cannot are
**reported, not dropped** — a series that quietly books 3 of 12 while the
customer believes they hold 12 is the worst outcome.

## 6. Waitlist

New `waitlist_entries` table + router. `position` is a join stamp that is
**never renumbered** — a queue that resequences on departure lets someone move
backwards. The API reports `peopleAhead` instead.

Promoted bookings are created **pending regardless of auto-approve**: the
customer joined a queue, they did not agree to a specific booking.

`bookings.client_email` is NOT NULL and the waitlist row cannot carry it — the
table is new but already created, and the schema is append-only (no `ALTER`) —
so the address is resolved at promotion time instead.

## 7. Prerequisites and payments

A blocking prerequisite now **outranks auto-approve**: an instant-confirmation
service that also demands a sign-off does not confirm. Satisfaction is recorded
per **booking**, not per customer — the same person can be cleared for one and
not another.

`payment_state` is **derived** from `payments.flow` plus what has been recorded
paid, never stored, so it cannot drift from the config after a pivot.
`POST /bookings/{id}/pay` deliberately *records* rather than charges:
`payments.adapter` is `manual` in every shipped config, so wiring a PSP means
implementing the adapter behind that route, not changing its meaning.

## 8. `advanceBookingWindowDays` — dispatched at last

This sat in `rules.UNDISPATCHED` with a comment saying *"wire it once the seed
horizon and the config agree."* They now do: `_grid` seeds **exactly** the
declared window. That meant removing the six-unit floor added in §1, which
contradicted the rule about to be enforced.

Doing so exposed three configs that did not mean what they said — a monthly plot
lease bookable one month ahead. Pivots 007/019/041 now declare a longer window,
so the allotment demo has 12 monthly slots in 365 days. Verified: the rule
rejects beyond the window, and **0 of 16 seeded slots are unbookable**.

Worth recording: the first attempt inserted a duplicate `"timing"` key into those
pivot definitions, which Python silently resolves to the *last* value — two of
the three were being overwritten while looking correct in the diff. Caught by
asserting on the loaded value rather than the source text.

## Verification

`pytest backend` 1017 passed · `tsc` 0 errors · `eslint` 21 warnings
(unchanged baseline) · `next build` all routes · `check_pivots` 100/100
expressible, 97/100 priced, **"config keys audited: all"** · `make checkstates`
100/100 · `make checkseed` 10/10 · app routes 200.

Docs and contract tests that described the old state were updated rather than
left lying: `check_pivots.py`'s audit map (five blocks moved `DECLARED_ONLY` →
`ENFORCED`), two `test_rules.py` registry tests, `backend/CLAUDE.md`'s "Declared
but NOT enforced" table, and the pinned `SERVICE_KEYS`/`BOOKING_KEYS` sets.

## Still not built

- `inventory.reservationWindowMinutes` and the `finite`/`bulk`/`consumable`
  modes — an expiring hold needs a reservation state ahead of booking; stock
  distinct from capacity needs its own table.
- `recurrence.term` — cancelling a *series* under notice.
- `capabilities.quotes` / `.cart` — no surface at all.
- `payments.noShowFee`, `timing.approvalWindowHours` — both need something that
  does not exist yet (a no-show action; a scheduled job).
- The 33 `LIMITATION`s in `check_pivots.py` — VAT, weekly opening hours,
  overbooking allowance, season overrides, multi-dimensional capacity. These are
  gaps in the **config language itself**, not wiring.
- `TODO.md`'s P1–P6 round-trip amplification, untouched.
