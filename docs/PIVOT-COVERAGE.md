# Pivot coverage — what was tested, what broke, what was fixed

Evidence for the claims in [PIVOT-SYSTEM.md](PIVOT-SYSTEM.md). Every number here
comes from a script you can run:

```bash
python3 scripts/check_pivots.py        # summary
python3 scripts/check_pivots.py -v     # + per-pivot gaps
python3 scripts/check_pivots.py --md   # the table below
```

`scripts/check_pivots.py` expresses 50 deliberately different businesses as real
`domain.config.json` fragments, runs each through the actual
`app.config_schema.validate()` and `app.pricing.quote()`, and asserts the quoted
total against a hand-computed figure. It exits non-zero if any pivot fails to
validate, misprices, or duplicates another's capability tuple.

It separates two questions that are easy to conflate:

1. **Can the config express this business?** — does it validate.
2. **Does the engine enforce it end to end?** — does every config path it relies
   on have a real reader.

A pivot can pass (1) and fail (2). That is the expected state for anything on
the roadmap, and saying so plainly is the point of this document.

---

## Results

| Measure | Result |
|---|---|
| Pivots defined | **50** (25 single-tenant, 25 marketplace) |
| Expressible in config v2 | **50 / 50** |
| Quoted total == hand-computed total | **50 / 50** |
| Capability tuples unique (the design's hard constraint) | **yes** |
| Fully enforced end to end today | **0** |
| Blocked on a code-level escape hatch | **13** |
| Schema limitations found | **1** (open) |

**"0 fully enforced" needs context and should not be read as failure.** These 50
were chosen to stress the abstraction, so every one of them leans on at least one
Tier-1 feature (prerequisites, inventory, waitlist, payments) that has a schema
but no reader yet. An ordinary appointment business — the shipped
`domain.config.json` — runs end to end today. What the number honestly says is:
*the schema landed first, the enforcement layers are the roadmap.*

## Issues found and fixed

### Found while implementing

| # | Issue | Fix |
|---|---|---|
| 1 | `POST /config/reload` was **unauthenticated** — anyone could force a disk re-read of the control-plane config | Owner-gated, and it now validates the new file *before* dropping the cached one, so a bad edit returns 422 and the running app keeps serving the last good config |
| 2 | Config had **no runtime validation** — `get_config()` was a bare `json.load`, so a typo surfaced as a 500 on whichever request read it first | `normalize()` + `validate()` at load; `ConfigError` lists every problem at once |
| 3 | `metaFields` entity keys **did not match the call sites** — the code validated `"slots"` (never declared in any config) and never validated `"bookings"` (declared in both) | Widened to six entities; both shipped configs declare all of them |
| 4 | `metaFields[].type: "string"` shipped in the medical example, matched nothing in the type map, and therefore **validated nothing** | `"string"` aliased to `"text"`; the example corrected; an unknown type is now a load error |
| 5 | Anonymous visitors always saw availability grouped in **UTC**, shifting evening slots into the next day for any business east of Greenwich | `location.timezone` added to the `?tz=` → user → **business** → UTC fallback chain |
| 6 | The frontend measured every distance from a **hardcoded Warsaw constant** | `location.origin` / `location.distanceUnit` drive `lib/geo.ts`, applied at boot |
| 7 | Price was one hardcoded expression (`priceMinorUnits × slots × party`) — the reason a per-hour or per-night niche needed code | `app/pricing.py`; defaults reproduce the old expression exactly |
| 8 | `advanceBookingWindowDays` was **silently dead** (registered to an event nothing dispatched) | Still not enforced — the seed lays slots 56 days out while the config allows 30 — but now in an explicit `UNDISPATCHED` map with the reason, and listed as a known gap |

### Found by adversarial review of the new code

| # | Issue | Fix |
|---|---|---|
| 9 | `_enum` did `value not in frozenset`, which **raises `TypeError` on a dict or list**. A plausible hand-edit (`patterns: [{"every": "week"}]`) made `/config/reload` return **500 instead of the documented 422**, and killed startup with a traceback rather than the problem list | `isinstance` guard; unhashable values are now normal listed errors |
| 10 | `pricing.fees[].kind` was unvalidated, so a typo like `"percentage"` made the fee **silently evaluate to zero** in every quote — the exact failure mode the metaField validator exists to prevent | `FEE_KINDS` enum plus per-kind required fields |
| 11 | `distanceBand` bands were only checked for emptiness, so `"bands": "10km"` validated and then priced 0 | Per-band shape check (`maxKm`, `feeMinorUnits`) |
| 12 | `booking.party.min > max` was not cross-checked, though `duration.minUnits > maxUnits` was | Cross-check added |
| 13 | Several keys were declared, validated and served while **nothing read them**, with no way to tell | Explicit declared-only inventory, in code comments, `backend/CLAUDE.md`, and the table below |

### Found by running the 50 pivots

| # | Issue | Status |
|---|---|---|
| 14 | `ctx["unit_count"]` **overrode the duration-derived quantity** for `day`/`night`/`week`/`month`. Any config combining a `per: "unit"` rate with a period-based `secondaryRate` misquoted — a pallet-space pivot billed 20 pallets as *20 weeks*, quoting 26000 instead of 10000 | **Fixed.** A period is a duration, a unit is a quantity; they no longer share an input |
| 15 | `pricing.secondaryRate` **adds** to the base, so a genuine *product* (20 pallets × 4 weeks) cannot be expressed — only a sum | **Open.** See below |

### Regression avoided

Dispatching `maxBookingsPerSlot` on `booking.create` looked like an obvious
tidy-up. It would have re-applied `min(capacity, maxBookingsPerSlot)` and capped
**every shared-capacity slot at the global default of 1**, breaking group
bookings across the board. It is in `UNDISPATCHED` with a comment, and there is a
regression test that fails if anyone re-registers it.

## Open schema limitation

**#41 Warehouse Pallet Space** — two-dimensional pricing (quantity × time) is not
expressible. `rate` and `secondaryRate` are summed, never multiplied, so
`20 pallets × 4 weeks @ 300` cannot be stated. The pivot validates and quotes; it
just quotes the wrong model.

The fix is a `rate.multiplyBy` (or a `rate.per` accepting a pair). It was not
added because only one of the 50 pivots needs it, and the design rule is that a
field must earn its place across at least two — so it is recorded here rather
than built.

## Pivots blocked on a code-level escape hatch

These 13 express cleanly in config and cannot run without an extension point.
Hatch IDs match the section in the original plan.

| # | Pivot | Escape hatch |
|---|---|---|
| 6 | The Barbers on Floriańska | E1 — queue availability (no start times); needs availabilityStrategy |
| 7 | Community Allotment Plots | E2 — open-ended term; needs date_range availabilityStrategy |
| 17 | Vaccination Course (2-dose) | E6 — dependent bookings; needs booking_series + expander |
| 19 | Self-Storage Units | E2 — open-ended term; needs date_range availabilityStrategy |
| 20 | Theatre Reserved Seating | E3 — positional inventory + adjacency; deferred by design |
| 25 | Community Tool Library | E7 — checked_out/returned/overdue lifecycle + fee accrual |
| 30 | Wedding Venue Marketplace | E2 — open-ended booking; needs date_range availabilityStrategy |
| 31 | Home Cleaning (recurring) | E6 — recurring series; needs booking_series + expander |
| 38 | Tutoring Marketplace | E10 — per-service vocabulary/unitKind; vocabulary is global today |
| 40 | Restaurant Reservations | E3 — capacity_fit resourceSelector (pick a table that fits the party) |
| 41 | Warehouse Pallet Space | E2 — open-ended term; needs date_range availabilityStrategy |
| 45 | Freelance Design Marketplace | E4 — a booking with no slot; `bookings.slot_id` is NOT NULL on a frozen table |
| 48 | Removals Reverse Auction | E5 — reverse-auction flow; needs quote_requests + bids entities |

`E2` (date-range availability) blocks 4 pivots on its own and is the single
highest-value hatch to build.

## The 50 pivots

"Engine gap" counts config paths the pivot depends on that have no reader yet, or
names the escape hatch blocking it.

| # | Pivot | Tenancy | Config valid | Quote | Expected | Engine gap |
|---|-------|---------|--------------|-------|----------|------------|
| 1 | Alpine Ski & Board Hire | single | ok | 13500 | 13500 | 6 key(s) |
| 2 | Dr. Halina's Dental Practice | single | ok | 6000 | 6000 | 3 key(s) |
| 3 | Kraków Escape Rooms | single | ok | 12000 | 12000 | 2 key(s) |
| 4 | Vinyasa Yoga Studio | single | ok | 0 | 0 | 4 key(s) |
| 5 | Mobile Car Valeting | single | ok | 6000 | 6000 | 2 key(s) |
| 6 | The Barbers on Floriańska | single | ok | 2500 | 2500 | E1 |
| 7 | Community Allotment Plots | single | ok | 6500 | 6500 | E2 |
| 8 | Farm Shop Veg Boxes | single | ok | 1800 | 1800 | 5 key(s) |
| 9 | Blood Donation Centre | single | ok | 0 | 0 | 2 key(s) |
| 10 | City Tennis Courts | single | ok | 1800 | 1800 | 3 key(s) |
| 11 | Hilltop Boutique Hotel | single | ok | 54000 | 54000 | 2 key(s) |
| 12 | Private Chef at Home | single | ok | 0 | 0 | 2 key(s) |
| 13 | University Lab Equipment | single | ok | 0 | 0 | 4 key(s) |
| 14 | Aqua Park Day Sessions | single | ok | 7500 | 7500 | 2 key(s) |
| 15 | Driving School | single | ok | 7000 | 7000 | 3 key(s) |
| 16 | Recording Studio | single | ok | 20000 | 20000 | 2 key(s) |
| 17 | Vaccination Course (2-dose) | single | ok | 0 | 0 | E6 |
| 18 | Dog Grooming Salon | single | ok | 5500 | 5500 | 2 key(s) |
| 19 | Self-Storage Units | single | ok | 8000 | 8000 | E2 |
| 20 | Theatre Reserved Seating | single | ok | 13000 | 13000 | E3 |
| 21 | Physiotherapy (insurer-billed) | single | ok | 4500 | 4500 | 2 key(s) |
| 22 | Van Hire, driver optional | single | ok | 16500 | 16500 | 3 key(s) |
| 23 | Online Language Tutor | single | ok | 3000 | 3000 | 1 key(s) |
| 24 | Charity Gala | single | ok | 0 | 0 | 4 key(s) |
| 25 | Community Tool Library | single | ok | 0 | 0 | E7 |
| 26 | TradieNow (plumbers/sparks) | multi | ok | 0 | 0 | 4 key(s) |
| 27 | Fitness Class Marketplace | multi | ok | 0 | 0 | 3 key(s) |
| 28 | Peer-to-Peer Car Sharing | multi | ok | 3400 | 3400 | 3 key(s) |
| 29 | Coworking Desk Marketplace | multi | ok | 2000 | 2000 | 4 key(s) |
| 30 | Wedding Venue Marketplace | multi | ok | 0 | 0 | E2 |
| 31 | Home Cleaning (recurring) | multi | ok | 8400 | 8400 | E6 |
| 32 | Local Farmers Market | multi | ok | 2700 | 2700 | 4 key(s) |
| 33 | Specialist Marketplace (insurer) | multi | ok | 12000 | 12000 | 4 key(s) |
| 34 | Event Ticketing Marketplace | multi | ok | 10500 | 10500 | 3 key(s) |
| 35 | Construction Plant Rental | multi | ok | 58000 | 58000 | 3 key(s) |
| 36 | Online Therapy Marketplace | multi | ok | 4000 | 4000 | 3 key(s) |
| 37 | Boat Charter Marketplace | multi | ok | 135000 | 135000 | 4 key(s) |
| 38 | Tutoring Marketplace | multi | ok | 8000 | 8000 | E10 |
| 39 | Salon Marketplace | multi | ok | 5500 | 5500 | 3 key(s) |
| 40 | Restaurant Reservations | multi | ok | 0 | 0 | E3 |
| 41 | Warehouse Pallet Space | multi | ok | 10000 | 10000 | E2 |
| 42 | Photographer Marketplace | multi | ok | 35000 | 35000 | 2 key(s) |
| 43 | Nursery / Childcare | multi | ok | 0 | 0 | 5 key(s) |
| 44 | Parking Space Marketplace | multi | ok | 2000 | 2000 | 3 key(s) |
| 45 | Freelance Design Marketplace | multi | ok | 0 | 0 | E4 |
| 46 | Fishing Beat Permits | multi | ok | 9000 | 9000 | 4 key(s) |
| 47 | Community Events Board | multi | ok | 0 | 0 | 2 key(s) |
| 48 | Removals Reverse Auction | multi | ok | 0 | 0 | E5 |
| 49 | Pharmacy Click & Collect | multi | ok | 2400 | 2400 | 4 key(s) |
| 50 | Shared Kitchen Marketplace | multi | ok | 6600 | 6600 | 4 key(s) |

## What is enforced

| Config path | Enforced by |
|---|---|
| `terms.admin` | auth.py owner-gate message |
| `terms.slot` | rules._term in rule-violation messages |
| `metaFields.resources` | meta.validate_metadata via routers/resources.py |
| `metaFields.slots` | meta.validate_metadata via routers/slots.py |
| `tenancy.mode` | frontend routing (single vs marketplace) |
| `tenancy.providerCode` | frontend sole-provider resolution |
| `discovery.facets` | main._config_with_facets -> search UI |
| `location.timezone` | availability._viewer_tz + bookings._business_tz |
| `location.origin` | frontend lib/geo.ts distance origin |
| `location.distanceUnit` | frontend lib/geo.ts formatting |
| `timing.slotDurationMinutes` | routers/slots.py + effective_service_rules |
| `timing.maxBookingsPerSlot` | routers/slots.py default capacity |
| `timing.cancellationWindowHours` | effective_service_rules -> within_cutoff |
| `timing.bufferMinutes` | apply_rules('slot.create') |
| `timing.leadTimeMinutes` | apply_rules('booking.create') -> rules._lead_time |
| `timing.confirmation` | rules.effective_auto_approve |
| `booking.duration.minUnits` | effective_service_rules -> minSlotsPerBooking |
| `booking.duration.maxUnits` | effective_service_rules -> maxSlotsPerBooking |
| `pricing.currency` | pricing.quote |
| `pricing.rate` | pricing.quote |
| `pricing.secondaryRate` | pricing.quote |
| `pricing.tiers` | pricing.quote -> match_tier |
| `pricing.chargePerPerson` | pricing.quote party factor |
| `pricing.caps.perBookingMinorUnits` | pricing.quote |
| `pricing.fees` | pricing.quote |
| `pricing.deposit` | pricing.quote |

## What is declared but not enforced

Validated and served over `/config`, with no reader. Each entry says what has to
be built. This table is generated from `scripts/check_pivots.py`, so it cannot
drift from the harness.

| Config path | Needs |
|---|---|
| `booking.unitKind` | vocabulary/UI layer (E10 per-service vocabulary) |
| `booking.granularity` | availabilityStrategy plugin (E2 date-range) |
| `booking.duration.mode` | availabilityStrategy plugin (E2) |
| `booking.party.mode` | party rules in _resolve_selection |
| `booking.party.min` | party rules in _resolve_selection |
| `booking.party.max` | party rules in _resolve_selection |
| `booking.party.composition` | weighted person_units passed into quote() |
| `booking.party.matchResourceCapacity` | resourceSelector strategy (E3 capacity_fit) |
| `booking.sequence` | booking_series entity + expander (E6) |
| `booking.subject` | subject entity + intake capture |
| `booking.options` | add-on selection at booking time |
| `pricing.caps.perDayMinorUnits` | cross-booking daily total (a query) |
| `pricing.tiers[].quantityCap` | sold-count query |
| `payments.flow` | PaymentAdapter + payments table (E8) |
| `payments.schedule` | PaymentAdapter (E8) |
| `payments.payer` | PaymentAdapter (E8) |
| `payments.billingCycle` | PaymentAdapter (E8) |
| `payments.noShowFee` | PaymentAdapter (E8) |
| `payments.usageMetered` | bookingLifecycle state machine (E7) |
| `inventory.mode` | inventory block + reservation holds |
| `inventory.returnRequired` | bookingLifecycle checked_out/returned/overdue (E7) |
| `inventory.loanPeriodHours` | bookingLifecycle (E7) |
| `inventory.overdueFeePerDayMinorUnits` | bookingLifecycle (E7) |
| `inventory.restockCycle` | consumable stock counters |
| `inventory.ratioConstraint` | derived-capacity resolver |
| `inventory.seatMap` | positional inventory (E3, deferred) |
| `location.modes` | per-service fulfilment UI |
| `location.serviceArea` | travel radius filter + travel buffer |
| `location.fulfilment` | pickup/delivery window logic |
| `location.remote` | meeting-link generation |
| `prerequisites` | prerequisite_submissions + form renderer + confirm gate |
| `timing.waitlist` | waitlist_entries + auto-promote (Tier 1) |
| `timing.seasons` | availability date-window filter |
| `timing.blackouts` | availability date-window filter |
| `timing.approvalWindowHours` | scheduled expiry job |
| `timing.advanceBookingWindowDays` | rules.UNDISPATCHED — seed horizon conflict |
| `recurrence` | booking_series entity + expander (E6) |
| `entitlements` | entitlement_grants + credit spend |
| `capabilities` | UI gating + write refusal per capability |
| `discovery.mode` | reverse-auction flow plugin (E5) |
| `discovery.matching` | intake-driven provider matching |

## Test suite

`test/backend` is owned by the `test-writer` agent and covers the config schema,
the pricing engine, the rules registry, and the booking/availability routes that
consume them. **792 passed** at the time of writing (330 before this work).

```bash
python -m pytest test/backend -q
```

The pivot harness is complementary, not a replacement: the suite tests units and
routes, the harness tests whether the *schema* can describe a business.
