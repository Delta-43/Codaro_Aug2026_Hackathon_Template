# Pivot coverage — what was tested, what broke, what was fixed

Evidence for the claims in [PIVOT-SYSTEM.md](PIVOT-SYSTEM.md). Every number here
comes from a script you can run:

```bash
python3 scripts/check_pivots.py        # summary
python3 scripts/check_pivots.py -v     # + per-pivot gaps
python3 scripts/check_pivots.py --md   # the table below
```

`scripts/check_pivots.py` expresses 100 deliberately different businesses as real
`domain.config.json` fragments, runs each through the actual
`app.config_schema.validate()` and `app.pricing.quote()`, and asserts the quoted
total against a hand-computed figure. It exits non-zero if any pivot fails to
validate, misprices unexpectedly, or duplicates another's capability tuple.

Pivots #1-50 live in `scripts/check_pivots.py`; #51-100 in
`scripts/pivots_extended.py`. A pivot may declare a `limitation`, which marks a
known gap: the mismatch is then reported as `gap`, not a regression.

It separates two questions that are easy to conflate:

1. **Can the config express this business?** — does it validate.
2. **Does the engine enforce it end to end?** — does every config path it relies
   on have a real reader.

A pivot can pass (1) and fail (2). That is the expected state for anything on
the roadmap, and saying so plainly is the point of this document.

---

## Results

| Measure | Batch 1 (#1-50) | Both batches (#1-100) |
|---|---|---|
| Pivots defined | 50 | **100** (55 single-tenant, 45 marketplace) |
| Expressible in config v2 | 50 / 50 | **100 / 100** |
| Quoted total == hand-computed total | 50 / 50 | **97 / 100** |
| Capability tuples unique (the design's hard constraint) | yes | **yes** |
| Fully enforced end to end today | 0 | **13** |
| Blocked on a code-level escape hatch | 13 | **13** |
| Schema limitations found | 1 | **33** (3 proven by a misquote) |

**The two batches do different jobs.** Batch 1 walks the nine design axes
(bookable unit, pricing, inventory, duration, location, party, prerequisites,
timing, money flow) and asks *can the schema describe this business?* — the
answer is yes, 50 times over.

Batch 2 was written after those axes were exhausted (`party` has three values,
`location` five, and 24 of the first 50 were `on_site`; more permutations would
prove nothing). It instead probes dimensions batch 1 never varied — currency
exponents, rounding, tax, refund policy, eligibility arithmetic, cross-service
composition, resource-level pricing, marketplace economics — chosen because each
is both a plausible business *and* somewhere the schema might not reach. That is
where all 32 new limitations came from.

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

## What batch 2 found

Three pivots **misquote** — the engine returns a confidently wrong number rather
than refusing. Those are the serious ones:

| # | Pivot | Quoted | Correct | Why |
|---|---|---|---|---|
| 59 | B2B Training | 80000 | 96000 | No `tax` concept anywhere, so VAT-exclusive pricing is unreachable |
| 62 | Gift voucher florist | 6500 | 1500 | `entitlements.plans[]` has no monetary balance and `quote()` takes no redemption input |
| 83 | Happy-hour crossing a band | 3000 | 4500 | Tier matching reads the **start time only**, so a 17:00-19:00 booking bills entirely at the 17:00-18:00 rate |

**#83 is the most dangerous finding in either batch.** It is not a missing
feature — it is a silent mispricing in a configuration that validates cleanly and
looks correct. Any business with time-banded pricing (off-peak gyms, happy hours,
night rates) will undercharge on every booking that spans a boundary. Fixing it
means splitting a booking across bands, which changes the shape of `quote()` from
"one rate" to "a rate per segment".

### Fixed during this exercise

**Per-service overrides were never validated.** `validate()` only ever ran on the
global file at load, so `services.metadata.<block>` reached the pricing and
scheduling paths unchecked — a service could carry a `pricing` block that quoted
real money with no schema check. Worse, the override path was *unreachable*
through the API (only `image_url` and `auto_approve` were ever written), so the
marketplace claim — two businesses pricing differently without touching
`domain.config.json` — was not actually usable. Now `POST`/`PATCH /services` take
a validated `config` object (422 on a bad block), and the read path drops an
invalid block in favour of the global one, per block, with a warning.
`tenancy` is deliberately non-overridable: a tenant setting its own
`commission.rateBps` would be privilege escalation.

Closing that hole surfaced four more, all fixed:

| Issue | Effect |
|---|---|
| A malformed `timing.seasons`/`blackouts` entry produced a **path-less** error message, so the override filter dropped it | Bad windows passed the write gate |
| `effective_service_pricing` read the **raw** metadata block rather than the surviving one | A service with a typo'd `pricing` block priced at the global default — **a silent zero price**, not even its own column value |
| `ServiceCreate.auto_approve` defaulted to `True`, stamping the key on every created service | `timing.confirmation` was unreachable through the API, as was a deployment-wide `request_approve` |
| `serialize_service` read `metadata.auto_approve` directly instead of `effective_auto_approve` | The wire said `autoApprove: true` while the booking path created `pending` bookings |

The zero-price one is the same shape as #83: a config that validates, looks
correct, and quietly gets the money wrong.

**Refundable bonds were clamped to the total.** `_deposit` did
`min(value, total)` for every deposit, so a 30000 damage bond on a 20000 tool
hire silently became 20000 — under-securing the asset. A deposit is two different
things: a *non-refundable* one is a prepayment and can never exceed the price; a
*refundable* one is a hold and routinely does. Now branched on `refundable`, with
`#55` covering the prepayment branch and `#98` the bond branch.

### Themes behind the 32 new limitations

| Theme | Pivots | The gap |
|---|---|---|
| **Tax** | 58, 59 | No `tax` block at all. VAT-inclusive quotes the right gross but cannot break out the component; VAT-exclusive is simply wrong. Affects every commercial pivot in both batches. |
| **Refunds & change policy** | 60, 61, 97 | Cancellation is one binary cutoff shared by cancel *and* reschedule. No graduated refund ladder, no change fee, no way to be free to cancel but paid to rebook. |
| **Marketplace economics** | 65, 66, 93, 99 | `commission.rateBps` has no base (net? gross? incl. pass-through fees?); no payout schedule to the tenant; `tenancy` is not per-service overridable so commission is global; nothing aggregates across currencies. |
| **Discounts are inert** | 62, 69, 74, 89 | `entitlements.plans[].discountBps` is never read by `quote()`. Member rates, contract rates and last-minute pricing all work only by smuggling a key through the generic `zone` clause — which the customer could self-select. |
| **Composition** | 75, 76, 77, 78, 84 | A booking is one service, one resource, contiguous slots. Bundles across services, dependent resources, paired staff, mid-booking resource swaps and two-endpoint journeys are all unrepresentable. |
| **Scheduling shapes** | 86, 87, 88, 90, 91 | `blackouts[]` are date ranges, so **recurring weekly opening hours cannot be declared at all** — the most common scheduling fact about any business exists only implicitly in which slots got seeded. Seasons carry no overrides, turn time is one number, buffers are static, overbooking is impossible. |
| **Identity & eligibility** | 67, 73 | A prerequisite is a yes/no gate, so age rules (dob + minAge) need date arithmetic the schema lacks. `booking.subject` is one subject per booking, so three children each needing a waiver and a seat cannot be modelled. |
| **Capacity** | 85 | A slot has one `capacity` integer; independent pools (ferry passengers vs vehicle decks) need multi-dimensional capacity. |
| **Discovery & i18n** | 71, 72 | No locale anywhere (`en-GB` is hardcoded in every frontend formatter), and `metaFields` can declare a resource attribute that `discovery.facets` can never filter on. |
| **Allocation** | 81 | A waitlist is FIFO by construction; ballots and weighted draws have no representation. |

### Ranked by damage

1. **#83 time-band splitting** — silently wrong money, today, in a valid config.
2. **Tax** — blocks correctness for every B2B and most B2C commerce.
3. **Weekly opening hours** — every business has them; none can declare them.
4. **Commission base + per-tenant override** — ambiguous accounting across all 45 marketplace pivots.
5. **Inert `discountBps`** — a declared field that does nothing, the exact v1 disease this work set out to cure.

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

## The pivots

"Engine gap" counts config paths the pivot depends on that have no reader yet, or
names the escape hatch blocking it.

### Batch 1 — the nine design axes (#1-50)

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

### Batch 2 — probes into unmodelled dimensions (#51-100)

| # | Pivot | Tenancy | Config valid | Quote | Expected | Engine gap |
|---|-------|---------|--------------|-------|----------|------------|
| 51 | Shinjuku Capsule Hotel | single | ok | 14400 | 14400 | none — end to end |
| 52 | Kuwait City Dental | single | ok | 25500 | 25500 | none — end to end |
| 53 | Percent fee stacked on a cap | single | ok | 5000 | 5000 | none — end to end |
| 54 | Odd-percent rounding probe | single | ok | 3616 | 3616 | none — end to end |
| 55 | Prepayment deposit above the total | single | ok | 500 | 500 | none — end to end |
| 56 | Two tiers both matching | single | ok | 5000 | 5000 | none — end to end |
| 57 | Free class with a booking fee | single | ok | 150 | 150 | none — end to end |
| 58 | Sliding VAT-inclusive salon | single | ok | 6000 | 6000 | none — end to end |
| 59 | B2B Training (VAT exclusive) | multi | ok | 80000 **MISMATCH** | 96000 | 3 key(s) |
| 60 | Tiered cancellation refunds | single | ok | 24000 | 24000 | none — end to end |
| 61 | Reschedule-fee physiotherapy | single | ok | 4000 | 4000 | none — end to end |
| 62 | Gift voucher florist | single | ok | 6500 **MISMATCH** | 1500 | 1 key(s) |
| 63 | Split-the-bill supper club | single | ok | 16800 | 16800 | 1 key(s) |
| 64 | Deposit forfeited on no-show | multi | ok | 30000 | 30000 | 2 key(s) |
| 65 | Commission on the net, not the gross | multi | ok | 9500 | 9500 | 1 key(s) |
| 66 | Payout schedule to the tenant | multi | ok | 120000 | 120000 | 3 key(s) |
| 67 | 18+ Wine Tasting | single | ok | 11000 | 11000 | 2 key(s) |
| 68 | Senior stylist premium | multi | ok | 7000 | 7000 | 1 key(s) |
| 69 | Members-only squash court | single | ok | 1200 | 1200 | 2 key(s) |
| 70 | Expiring credential kitesurf school | single | ok | 12000 | 12000 | 2 key(s) |
| 71 | Language-specific tour guide | multi | ok | 9000 | 9000 | 1 key(s) |
| 72 | Accessible-only bookings | multi | ok | 8000 | 8000 | 2 key(s) |
| 73 | Household account (one payer, many users) | single | ok | 5400 | 5400 | 3 key(s) |
| 74 | Corporate account with negotiated rate | multi | ok | 2100 | 2100 | 2 key(s) |
| 75 | Spa Day Package | single | ok | 15000 | 15000 | 1 key(s) |
| 76 | Room requiring a projector | multi | ok | 8000 | 8000 | 3 key(s) |
| 77 | Two-person massage (paired staff) | single | ok | 14000 | 14000 | 2 key(s) |
| 78 | Airport transfer (A to B) | multi | ok | 8100 | 8100 | 2 key(s) |
| 79 | Multi-day festival pass | multi | ok | 24000 | 24000 | 1 key(s) |
| 80 | Sequential course (8 weeks, one enrolment) | single | ok | 32000 | 32000 | 3 key(s) |
| 81 | Waiting-list-only allotment of scarce slots | single | ok | 0 | 0 | 3 key(s) |
| 82 | Overnight shift rota | multi | ok | 19200 | 19200 | 2 key(s) |
| 83 | Happy-hour crossing the boundary | single | ok | 3000 **MISMATCH** | 4500 | none — end to end |
| 84 | Resource swap mid-booking | multi | ok | 25000 | 25000 | 3 key(s) |
| 85 | Ferry with vehicle decks | multi | ok | 3600 | 3600 | 2 key(s) |
| 86 | Restaurant turn times by daypart | single | ok | 0 | 0 | 2 key(s) |
| 87 | Cleaner's travel time between jobs | multi | ok | 7500 | 7500 | 2 key(s) |
| 88 | Peak-season capacity increase | single | ok | 8000 | 8000 | 2 key(s) |
| 89 | Last-minute discount | multi | ok | 2000 | 2000 | 1 key(s) |
| 90 | Overbooking-tolerant clinic | single | ok | 3000 | 3000 | 2 key(s) |
| 91 | Opening hours per weekday | single | ok | 2800 | 2800 | 1 key(s) |
| 92 | Two-week notice with a hard horizon | single | ok | 9500 | 9500 | 2 key(s) |
| 93 | Per-tenant commission override | multi | ok | 5000 | 5000 | 1 key(s) |
| 94 | Tenant-set cancellation policy | multi | ok | 7000 | 7000 | 2 key(s) |
| 95 | Zero-duration instant service | single | ok | 900 | 900 | none — end to end |
| 96 | Very large party buyout | multi | ok | 1250000 | 1250000 | 3 key(s) |
| 97 | Free cancellation, paid rebooking | single | ok | 11000 | 11000 | 1 key(s) |
| 98 | Deposit that is not part of the price | single | ok | 20000 | 20000 | 2 key(s) |
| 99 | Cross-border marketplace, mixed currencies | multi | ok | 8500 | 8500 | 1 key(s) |
| 100 | Same-day pivot: config swap under load | single | ok | 4200 | 4200 | none — end to end |

### Limitation register

| # | Pivot | Limitation |
|---|---|---|
| 41 | Warehouse Pallet Space | pricing.secondaryRate ADDS to the base; a genuine units x weeks PRODUCT (20 pallets x 4 weeks) cannot be expressed. Quoted 20x300 + 4x1000 = 10000, not 20x4x300 = 24000. |
| 58 | Sliding VAT-inclusive salon | Gross total is right, but the schema has NO tax concept: the 1122 VAT component cannot be declared, so no invoice/receipt can break it out and a VAT-exclusive niche (add 23% at checkout) cannot be expressed at all. |
| 59 | B2B Training (VAT exclusive) | No `tax` block. VAT-exclusive pricing (the norm for B2B) is unreachable: the engine quotes the net 80000 and there is nowhere to declare the 16000. |
| 60 | Tiered cancellation refunds | Cancellation is a single BINARY cutoff (`cancellationWindowHours`). A graduated refund ladder — the standard for accommodation — cannot be declared; there is no `refundPolicy[]` and no notion of a partial refund anywhere in the schema. |
| 61 | Reschedule-fee physiotherapy | A reschedule inside the cutoff is refused outright; it cannot be ALLOWED-WITH-A-FEE. There is no `changeFee` and the reschedule path has no way to add a charge. |
| 62 | Gift voucher florist | `entitlements.plans[]` models credits/memberships but has no monetary balance, so a part-paying gift voucher cannot reduce a quote. quote() has no redemption input at all. |
| 63 | Split-the-bill supper club | `payments.flow: split` means staged payments by TIME (deposit/balance), not split between PEOPLE. Per-attendee billing of one booking has no representation. |
| 65 | Commission on the net, not the gross | `commission.rateBps` has no BASE. Whether the platform takes its cut of the net, the gross, or excludes pass-through fees is undefined — a material accounting ambiguity in every one of the 25 marketplace pivots. |
| 66 | Payout schedule to the tenant | Money OUT is unmodelled. `payments.schedule[]` describes what the customer owes and when; there is no payout schedule to the tenant, so a marketplace cannot state when a business actually gets paid. |
| 67 | 18+ Wine Tasting | A prerequisite is a yes/no gate. An age RULE (dob + minAge, evaluated at the booking date) cannot be declared — no `minAge`, and metaField `min`/`max` are numeric bounds, not date arithmetic. |
| 68 | Senior stylist premium | Priced only by abusing the generic `zone` clause. Pricing belongs to the SERVICE; there is no per-RESOURCE price or duration override, so 'this stylist costs more' and 'this stylist is slower' are both inexpressible as data. |
| 69 | Members-only squash court | `entitlements.plans[].discountBps` exists but quote() never reads an entitlement. Member pricing works only by hand-passing a `zone`; the declared 5000bps discount is inert. |
| 71 | Language-specific tour guide | No locale/language anywhere. `terms`/`copy` are single-language, the frontend hardcodes `en-GB` in every Intl formatter, and a resource attribute cannot be made filterable — so 'guides who speak German' is neither declarable nor searchable. |
| 72 | Accessible-only bookings | `metaFields` can DECLARE `step_free` on a resource but nothing can FILTER on it: `discovery.facets` is a fixed three-key set (price/distance/rating), so a metadata-driven facet is impossible without code. |
| 73 | Household account (one payer, many users) | `booking.subject` is ONE subject per booking. Three children each needing their own waiver and their own seat cannot be modelled — party size is a number, not a list of identified subjects. |
| 74 | Corporate account with negotiated rate | Customer-specific negotiated rates work only by smuggling an account key through `zone`. There is no customer-segment concept, so the tier list would have to grow one entry per contract and every customer could self-select any of them. |
| 75 | Spa Day Package | A bundle spanning three DIFFERENT services in one booking is inexpressible: a booking is `service_id` + contiguous slots on ONE resource. The 15000 is a hand-entered flat price with no link to its components. |
| 76 | Room requiring a projector | `booking.options[]` can add a PRICE but cannot reserve a second resource. A booking that consumes room AND projector capacity simultaneously has no representation — `booking_slots` all belong to one resource. |
| 77 | Two-person massage (paired staff) | Requires TWO resources held for the same slot. The engine holds one resource per booking, so a paired-staff treatment can only be faked with a composite resource. |
| 78 | Airport transfer (A to B) | `location` describes ONE place. A journey has an origin and a destination; there is nowhere to put the second, and `serviceArea.radiusKm` is a circle around a single point. |
| 81 | Waiting-list-only allotment of scarce slots | A waitlist is FIFO by construction (`autoPromote`). A ballot/lottery allocation — random or weighted draw among applicants — has no representation. |
| 83 | Happy-hour crossing the boundary | Tier matching uses the START time only, so a 17:00-19:00 booking is billed entirely at the happy-hour rate (3000) instead of 1x1500 + 1x3000 = 4500. Time-banded pricing cannot SPLIT a booking across bands — a real mispricing, not just a missing feature. |
| 84 | Resource swap mid-booking | `_resolve_selection` requires every slot in a booking to share ONE resource. A 5-day hire that swaps units on day 3 (routine in fleet operations) cannot be one booking. |
| 85 | Ferry with vehicle decks | A slot has ONE `capacity` integer. A sailing with independent passenger and vehicle pools (and a car consuming both) needs multi-dimensional capacity — inexpressible. |
| 86 | Restaurant turn times by daypart | `slotDurationMinutes` is one number per service. A turn time that differs by daypart (60 at lunch, 90 at dinner) cannot be declared without splitting into two services. |
| 87 | Cleaner's travel time between jobs | `bufferMinutes` is a FIXED pad applied at slot creation. Travel time between two at-customer jobs depends on the distance between them — a dynamic buffer the schema cannot express. |
| 88 | Peak-season capacity increase | `timing.seasons[]` can gate availability on/off but carries no OVERRIDES. A season that changes capacity (or price, or duration) has nowhere to say so — seasons are a boolean window, not a settings layer. |
| 89 | Last-minute discount | No `appliesWhen` clause reads the gap between NOW and the slot START. Last-minute (and its mirror, early-booking) discounts — a staple of yield management — can only be faked by passing a `zone` the customer could choose themselves. |
| 90 | Overbooking-tolerant clinic | Capacity is a hard ceiling (`available_count >= party`). Deliberate overbooking — standard where no-shows are predictable — needs an overbook allowance the schema does not have. |
| 91 | Opening hours per weekday | `blackouts[]` are DATE RANGES. Recurring weekly opening hours (closed Mondays, open late Thursdays) — the single most common scheduling fact about any business — cannot be declared; they exist only implicitly in which slots got seeded. |
| 93 | Per-tenant commission override | `tenancy` is NOT in `OVERRIDABLE_BLOCKS`, so commission is global to the deployment. Negotiating a different rate with an anchor tenant — routine marketplace economics — requires a code change. |
| 97 | Free cancellation, paid rebooking | One `cancellationCutoffHours` governs BOTH cancel and reschedule (`within_cutoff` is shared). A fare that is freely cancellable but charges to rebook — or the reverse — cannot be expressed. |
| 99 | Cross-border marketplace, mixed currencies | Per-tenant currency works, but nothing aggregates across currencies: provider `priceFromMinorUnits` picks a min across services regardless of currency, and search price sort/filter compares raw integers — so CHF 85 sorts against HUF 8500. |

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
