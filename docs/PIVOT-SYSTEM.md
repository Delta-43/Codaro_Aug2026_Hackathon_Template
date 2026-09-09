# The pivot system

How `domain.config.json` works, what every field controls, and what is actually
wired up behind it.

This is the reference for every config block, the precedence model, and which
keys the engine enforces today.

---

## 1. The idea

The engine is a neutral spine: **provider → service → resource → slot → booking → user**.
Nothing in it names a domain. A pivot to a different niche is meant to be a
config edit and a reseed, not a rewrite.

`domain.config.json` is that config. The backend reads it once, resolves it, and
serves it at `GET /config`. The frontend renders from it.

```bash
# edit domain.config.json, then:
make reload    # drop the cached config
make reseed    # rebuild the demo data from it
make checkseed # verify the data and the config agree
```

### The demo data follows too

`make reseed` builds its dataset from the loaded config rather than from a
hardcoded vertical: `backend/seed_config.py` turns `domain.config.json` into the
spec `seed_vertical()` consumes, so currency, timezone, slot duration, prices,
cutoffs, min/max slots, slot capacity and, in single-tenant mode, the
provider's `public_code` all come from the pivot file. `pricing.tiers` become the
catalogue (one service per tier); `terms` supply the nouns.

Two things the config cannot supply are generated: prose (taglines,
descriptions), and the names of marketplace businesses other than the flagship,
`domain.config.json` carries no directory of businesses. `POST /demo/vertical`
still loads one of the three canned verticals from `seed_data.py` on purpose;
that data will not match any pivot.

`make checkseed` (`scripts/check_seed.py`) is the verification: it reports
RESET (did the wipe leave a clean dataset?) and MATCH (does that dataset
describe the config now loaded?) separately, deriving its expectations from
`rules._SERVICE_RULE_MAP` so it cannot disagree with the engine's own resolver.

## 2. The mental model: three layers of precedence

This is the single most important thing to understand, and it is the same idea
applied at three scales.

```
service column / services.metadata      (this business, this offering)
        ↓ falls back to
domain.config.json                      (this deployment's defaults)
        ↓ falls back to
hard default in code                    (always safe, never null)
```

- **Scalars** resolve through `rules.effective_service_rules()`, seven values
  (slot duration, min/max slots, cutoff, price, currency, booking model), each
  mapped to a service column and a dotted config path.
- **Whole blocks** resolve through `rules.effective_service_config()`,
  `services.metadata.<block>` deep-merges over the global block.

That second one is what makes a marketplace possible: two businesses on one
deployment can price, gate and schedule completely differently without either of
them editing `domain.config.json`.

```jsonc
// POST/PATCH /services  ->  stored as services.metadata blocks
{
  "config": {
    "pricing": { "model": "per_hour", "chargePerPerson": false,
                 "rate": { "per": "hour", "amountMinorUnits": 1200 } }
  }
}
```

Overrides go through the **same validator as the global file**: an invalid block
is a 422 on write, and (for seeded or hand-edited rows) is dropped in favour of
the global block on read, per block, with a warning, so one bad block does not
poison the rest. `tenancy` is deliberately not overridable: commission and tenant
verification are platform terms, not a business's to set.

## 3. Loading, and why it fails loudly

`app/config.py` does **read → normalize → validate → cache**:

- **normalize** (`app/config_schema.py`) fills in every default and reconciles
  the deprecated v1 aliases. `rules` ↔ `timing` and `search` ↔ `discovery` are
  kept in sync **in both directions**, so a v1 file boots unchanged and a v1
  reader never sees a stale number. Precedence: explicit v2 path → explicit v1
  path → default.
- **validate** returns *every* problem at once and `load_config()` raises
  `ConfigError` listing them. This file gets hand-edited under time pressure; a
  typo has to fail at the edit, not on whichever booking reads it first.

```
domain.config.json is not a usable domain config:
  - tenancy.providerCode is required when tenancy.mode is 'single'
  - pricing.currency must be a 3-letter ISO 4217 code, got 'EURO'
  - location.timezone must be a valid IANA zone, got 'Europe/Warsawww'
  - capabilities.payments is false, so payments.flow must be 'none' (got 'prepay')
```

`POST /config/reload` is **owner-gated** and validates the new file *before*
dropping the cached one, so a bad edit returns 422 and the running app keeps
serving the last good config. The same validator backs CI
(`.github/scripts/validate_domain_config.py` imports it, so CI and the engine
cannot disagree about what "valid" means).

## 4. The blocks

Every block is per-service overridable. Types are shown with their defaults.

### `configVersion` · `domain`
`configVersion: 2` (int). `domain` is a free label.

### `tenancy`
| Field | Type | Default | Controls |
|---|---|---|---|
| `mode` | `single \| multi` | `multi` | `single` collapses the marketplace to one implicit business: no Search tab, 4 tabs not 5, root redirects to `/provider`, no business-signup link |
| `providerCode` | string \| null | `null` | In single mode, resolves *the* business via `GET /providers/by-code/{code}`. **Required** when mode is `single` |
| `selfOnboarding` | bool | `mode == "multi"` | Whether businesses can sign themselves up |
| `tenantVerification` | `{required, credentials[]}` | off | Licence/KYC gating on the *business* side |
| `commission` | `{enabled, rateBps, chargedOn}` | off | Platform cut, `booking` or `completion` |

### `capabilities`, the on/off spine
Ten booleans: `payments` `inventory` `waitlist` `quotes` `recurrence`
`prerequisites` `entitlements` `cart` `reviews` `follows`. Defaults: `payments`,
`reviews`, `follows` on; the rest off.

A false capability is meant to hide the UI surface **and** refuse the write,
not one without the other. `validate()` already enforces the one cross-check that
matters: `capabilities.payments: false` requires `payments.flow: "none"`.

### `booking`
| Field | Type | Default |
|---|---|---|
| `unitKind` | `time_slot \| staff \| asset \| seat \| room \| class_capacity \| stock_item \| subscription_slot \| project` | `time_slot` |
| `granularity` | `minute \| hour \| day \| night \| week \| month \| none` | `minute` |
| `duration.mode` | `fixed \| variable \| customer_chosen \| open_ended` | `fixed` |
| `duration.minUnits` / `.maxUnits` / `.incrementUnits` | int | `1` / `1` / `1` |
| `party.mode` | `individual \| group \| buyout` | `individual` |
| `party.min` / `.max` | int / int\|null | `1` / `null` (= resource capacity) |
| `party.composition` | `[{key,label,priceFactor}]` \| null | `null` |
| `party.matchResourceCapacity` | bool | `false` |
| `sequence` | `{enabled,steps,minGapHours,maxGapHours}` | off |
| `subject` | `{enabled,noun,fields[]}` | off, the booking is *about* a pet/vehicle/child |
| `options` | `[{key,label,type,choices[]}]` | `[]`, add-ons that change price and can require a prerequisite |

### `pricing`
The arithmetic, in order: **tier match → base → secondary → fees → caps → deposit**.

| Field | Type | Default |
|---|---|---|
| `model` | `fixed \| per_hour \| per_person \| per_unit \| tiered \| quote \| deposit_balance \| subscription \| free` | `fixed` |
| `currency` / `currencyExponent` | ISO-4217 / int | `EUR` / `2` |
| `rate` | `{per, amountMinorUnits}` | `{slot, 0}` |
| `secondaryRate` | same shape \| null | `null` |
| `tiers` | `[{key,label,amountMinorUnits,appliesWhen,validFrom,validUntil,quantityCap}]` | `[]` |
| `chargePerPerson` | bool | `true` |
| `caps` | `{perBookingMinorUnits, perDayMinorUnits}` | both null |
| `fees` | `[{key,label,kind,...}]`, `flat` \| `percent` (rateBps) \| `distanceBand` (bands) | `[]` |
| `deposit` | `{enabled,kind,value,refundable}` | off |

`rate.per` quantities: `booking`→1, `slot`→slot count, `person`→head count,
`unit`→`unit_count`, `hour`→fractional hours, `day`/`night`/`week`/`month`→
**started** units from the selection's span (half a day of storage is a day).

`chargePerPerson: true` reproduces the v1 formula (`price × slots × party`);
`false` is the shared-unit case, a tennis court costs the same for two players
or four. `per: "person"` never double-counts.

`tiers[].appliesWhen` clauses: `partySize`, `timeOfDay` (handles a window that
wraps midnight), `zone`, `bookingIndex`, `subjectField`, `distanceKm`. **An
unknown clause fails closed**, a typo must not widen a discount to everyone.

> **Known mispricing.** A tier is matched once, against the booking's **start**
> time, and applied to the whole booking. A 17:00-19:00 booking under a
> 17:00-18:00 happy-hour tier bills entirely at the happy-hour rate. Time-banded
> pricing that must *split* a booking across bands is not supported, see
> issue #83.

A deposit clamps differently depending on `refundable`: non-refundable is a
prepayment and never exceeds the total; refundable is a bond and may.

### `payments`
`flow` (`prepay|pay_on_site|invoice_after|split|none`), `payer`
(`customer|third_party`), `schedule[]` (milestone payments), `billingCycle`,
`noShowFee`, `usageMetered`, `adapter` (`manual` by default, no PSP exists here).

### `inventory`
`mode` (`none|finite|rentable|consumable|serialised`),
`reservationWindowMinutes`, `loanPeriodHours`, `returnRequired`,
`overdueFeePerDayMinorUnits`, `restockCycle`, `ratioConstraint`.

### `location`
`modes[]` (`on_site|at_customer|remote|delivery|pickup`), `default`, **`timezone`**
(the business's own IANA zone), `distanceUnit` (`km|mi`), `origin`
(`{city,lat,lng}`, the point distances are measured from), `serviceArea`
(`radiusKm`, `travelBufferMinutes`, `feeBands`), `remote.meetingLinkMode`,
`fulfilment` (`windowMinutes`, `cutoffHoursBefore`).

### `prerequisites[]`
`{key, kind, label, appliesTo, required, validityDays, fields[], blocksConfirmation, verifier}`
where `kind ∈ {id_check, licence, intake_form, waiver, membership, approval, credential}`
and `appliesTo ∈ {customer, tenant, subject}`.

### `timing`
`confirmation` (`instant|request_approve`, the default behind each service's
auto-approve toggle), `approvalWindowHours`, `leadTimeMinutes` (minimum notice),
`waitlist`, `seasons[]`, `blackouts[]`, plus the five legacy keys
(`slotDurationMinutes`, `maxBookingsPerSlot`, `cancellationWindowHours`,
`advanceBookingWindowDays`, `bufferMinutes`) mirrored to `rules`.

### `recurrence` · `entitlements` · `discovery`
`recurrence`: `{enabled, patterns[], maxOccurrences, term{mode, noticePeriodDays}}`.
`entitlements`: `{enabled, kind, plans[]}`, credits, memberships, passes.
`discovery`: `{mode: browse|reverse, facets{}, matching{}}`.

### `terms` · `copy` · `metaFields`
`terms` is 17 nouns; `copy` is 10 strings. (v1's `theme` block, colour +
radius, has been removed: the frontend owns its own palette, and a `theme` key
left in an old pivot file is dropped at load rather than rejected.)
`metaFields` maps six entities (`providers` `services` `resources` `slots`
`bookings` `subjects`) to field descriptors:

```jsonc
{ "key": "reason", "label": "Reason for visit",
  "type": "text",       // text|number|boolean|date|select|file ("string" aliases to text)
  "required": false, "options": [], "min": null, "max": null,
  "pattern": null, "helpText": null, "visibleTo": "both" }
```

Undeclared metadata keys always pass (that is the no-migration extension point);
declared ones are strictly checked.

## 5. The rules registry, the escape hatch

`app/rules.py` holds an event → `{config key: validator}` map. Adding a
validator plus a `timing` key makes a rule enforce; **deleting the config key
disables it**; no router changes either way.

```python
RULES = {
    "booking.create":   {"leadTimeMinutes": _lead_time},
    "booking.change":   {"cancellationWindowHours": _cancellation_window},
    "booking.approve":  {},          # live extension points
    "booking.cancel":   {},
    "slot.create":      {"bufferMinutes": _buffer},
    "inventory.reserve": {}, "inventory.return": {}, "payment.due": {},
}
```

`UNDISPATCHED` holds two validators that exist but are deliberately not wired:

- `advanceBookingWindowDays`: the seed lays slots 56 days out while the config
  allows 30; enforcing it today would make half the demo calendar unbookable.
- `maxBookingsPerSlot`: capacity is enforced upstream by `_resolve_selection`
  and the `slot_occupancy` view, which understand party size and multi-slot
  holds. Re-registering it would re-apply `min(capacity, maxBookingsPerSlot)`
  and cap every shared-capacity slot at 1, breaking group bookings. There is a
  regression test.

## 6. What is actually wired

The config is fully expressible and fully validated. **Enforcement is narrower
than the schema**, on purpose, the schema went first so the roadmap has
somewhere to land. Do not assume a key does something because it validates.

Enforced end to end today: `pricing.*` (the whole quote pipeline),
`timing.{slotDuration,maxBookingsPerSlot,cancellationWindow,buffer,leadTime,confirmation}`,
`booking.duration.{min,max}Units`, `location.{timezone,origin,distanceUnit}`,
`metaFields.{resources,slots}`, `discovery.facets`, `tenancy.{mode,providerCode}`,
`terms.{admin,slot}`.

Everything else is declared and validated but has no reader yet. The exact list,
with what each one needs, is in
the table below, which lists what is wired end to end.

## 7. Adding a field

1. Add it to `DEFAULTS` in `app/config_schema.py`. That alone makes it readable
   everywhere and per-service overridable.
2. Add a `validate()` check **only if a wrong value would corrupt data**, a
   silly colour is not the validator's business, an invalid timezone is.
3. Wire a reader. If you cannot yet, add it to the declared-only table in
   `backend/CLAUDE.md` with what it needs.
4. Add coverage under `test/` (owned by the `test-writer` agent).

Step 3 is not optional. v1's real failure was ten leaf fields that looked live
and did nothing; the point of tracking them is that the next reader can tell the
difference.
