#!/usr/bin/env python3
"""Run all 50 design pivots through the real config validator and pricing engine.

The pivot thesis is only worth as much as its evidence. This harness turns the
50 hypothetical pivots from the v2 design into *executable* checks: each one is
expressed as a real `domain.config.json` fragment, normalized and validated by
`app.config_schema`, and (where it has a determinate price) quoted by
`app.pricing.quote` and asserted against a hand-computed expected total.

It answers two different questions, and keeps them separate on purpose:

1. **Can the config EXPRESS this pivot?**  -> `validate()` returns no errors.
2. **Does the engine ENFORCE it end to end?** -> every config path the pivot
   depends on appears in `ENFORCED` below.

A pivot can pass (1) and fail (2); that is the normal state for anything on the
Tier 1/Tier 2 roadmap, and saying so plainly is the point. What must never
happen is a pivot failing (1) — that means the schema cannot describe a business
we claimed it could.

    python scripts/check_pivots.py           # summary table
    python scripts/check_pivots.py -v        # + per-pivot enforcement gaps
    python scripts/check_pivots.py --md      # markdown, for docs/PIVOT-COVERAGE.md

Exit code is non-zero if any pivot fails validation or misprices.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config_schema import normalize, validate  # noqa: E402
from app.pricing import quote  # noqa: E402

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# What the engine actually enforces today.
#
# Derived by auditing every `get_config()` / `effective_service_config()` read in
# `backend/app`. Keep this honest — a path listed here must have a real reader,
# and anything in DECLARED_ONLY must say what is missing. This map is what stops
# the config growing a second generation of keys that look live and do nothing,
# which is exactly what happened to v1's `copy` and `theme`.
# ---------------------------------------------------------------------------
ENFORCED = {
    "terms.admin": "auth.py owner-gate message",
    "terms.slot": "rules._term in rule-violation messages",
    "metaFields.resources": "meta.validate_metadata via routers/resources.py",
    "metaFields.slots": "meta.validate_metadata via routers/slots.py",
    "tenancy.mode": "frontend routing (single vs marketplace)",
    "tenancy.providerCode": "frontend sole-provider resolution",
    "discovery.facets": "main._config_with_facets -> search UI",
    "location.timezone": "availability._viewer_tz + bookings._business_tz",
    "location.origin": "frontend lib/geo.ts distance origin",
    "location.distanceUnit": "frontend lib/geo.ts formatting",
    "timing.slotDurationMinutes": "routers/slots.py + effective_service_rules",
    "timing.maxBookingsPerSlot": "routers/slots.py default capacity",
    "timing.cancellationWindowHours": "effective_service_rules -> within_cutoff",
    "timing.bufferMinutes": "apply_rules('slot.create')",
    "timing.leadTimeMinutes": "apply_rules('booking.create') -> rules._lead_time",
    "timing.confirmation": "rules.effective_auto_approve",
    "booking.duration.minUnits": "effective_service_rules -> minSlotsPerBooking",
    "booking.duration.maxUnits": "effective_service_rules -> maxSlotsPerBooking",
    "pricing.currency": "pricing.quote",
    "pricing.rate": "pricing.quote",
    "pricing.secondaryRate": "pricing.quote",
    "pricing.tiers": "pricing.quote -> match_tier",
    "pricing.chargePerPerson": "pricing.quote party factor",
    "pricing.caps.perBookingMinorUnits": "pricing.quote",
    "pricing.fees": "pricing.quote",
    "pricing.deposit": "pricing.quote",
}

# Declared in DEFAULTS, validated, served over /config — but nothing reads it yet.
# The value is what has to be built, phrased so it maps onto the roadmap.
DECLARED_ONLY = {
    "booking.unitKind": "vocabulary/UI layer (E10 per-service vocabulary)",
    "booking.granularity": "availabilityStrategy plugin (E2 date-range)",
    "booking.duration.mode": "availabilityStrategy plugin (E2)",
    "booking.party.mode": "party rules in _resolve_selection",
    "booking.party.min": "party rules in _resolve_selection",
    "booking.party.max": "party rules in _resolve_selection",
    "booking.party.composition": "weighted person_units passed into quote()",
    "booking.party.matchResourceCapacity": "resourceSelector strategy (E3 capacity_fit)",
    "booking.sequence": "booking_series entity + expander (E6)",
    "booking.subject": "subject entity + intake capture",
    "booking.options": "add-on selection at booking time",
    "pricing.caps.perDayMinorUnits": "cross-booking daily total (a query)",
    "pricing.tiers[].quantityCap": "sold-count query",
    "payments.flow": "PaymentAdapter + payments table (E8)",
    "payments.schedule": "PaymentAdapter (E8)",
    "payments.payer": "PaymentAdapter (E8)",
    "payments.billingCycle": "PaymentAdapter (E8)",
    "payments.noShowFee": "PaymentAdapter (E8)",
    "payments.usageMetered": "bookingLifecycle state machine (E7)",
    "inventory.mode": "inventory block + reservation holds",
    "inventory.returnRequired": "bookingLifecycle checked_out/returned/overdue (E7)",
    "inventory.loanPeriodHours": "bookingLifecycle (E7)",
    "inventory.overdueFeePerDayMinorUnits": "bookingLifecycle (E7)",
    "inventory.restockCycle": "consumable stock counters",
    "inventory.ratioConstraint": "derived-capacity resolver",
    "inventory.seatMap": "positional inventory (E3, deferred)",
    "location.modes": "per-service fulfilment UI",
    "location.serviceArea": "travel radius filter + travel buffer",
    "location.fulfilment": "pickup/delivery window logic",
    "location.remote": "meeting-link generation",
    "prerequisites": "prerequisite_submissions + form renderer + confirm gate",
    "timing.waitlist": "waitlist_entries + auto-promote (Tier 1)",
    "timing.seasons": "availability date-window filter",
    "timing.blackouts": "availability date-window filter",
    "timing.approvalWindowHours": "scheduled expiry job",
    "timing.advanceBookingWindowDays": "rules.UNDISPATCHED — seed horizon conflict",
    "recurrence": "booking_series entity + expander (E6)",
    "entitlements": "entitlement_grants + credit spend",
    "capabilities": "UI gating + write refusal per capability",
    "discovery.mode": "reverse-auction flow plugin (E5)",
    "discovery.matching": "intake-driven provider matching",
}


def base(tenancy: str) -> dict:
    cfg = {"tenancy": {"mode": tenancy}}
    if tenancy == "single":
        cfg["tenancy"]["providerCode"] = "DEMO-0001"
    return cfg


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# ---------------------------------------------------------------------------
# The 50 pivots. `config` is merged over the tenancy base; `ctx` is a
# representative selection; `expect` is the hand-computed total in minor units.
# `blocked` names the escape hatch that still needs code; `limitation` records a
# gap this exercise actually found in the v2 schema itself.
# ---------------------------------------------------------------------------
SINGLE = [
    dict(n=1, name="Alpine Ski & Board Hire", booked="Rentable kit sets, multi-day",
         price="Per day + deposit", flags="U:asset P:unit I:rentable D:chosen L:pickup Y:solo Q:id T:season M:depbal",
         config={"booking": {"unitKind": "asset", "granularity": "day",
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 21}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False,
                             "rate": {"per": "day", "amountMinorUnits": 4500},
                             "deposit": {"enabled": True, "kind": "percent", "value": 30, "refundable": True}},
                 "payments": {"flow": "split", "schedule": [
                     {"key": "deposit", "label": "Deposit", "kind": "percent", "value": 30, "dueOffsetDays": 0, "relativeTo": "booking"},
                     {"key": "balance", "label": "Balance", "kind": "percent", "value": 70, "dueOffsetDays": 0, "relativeTo": "start"}]},
                 "inventory": {"mode": "rentable", "returnRequired": True, "loanPeriodHours": 504},
                 "location": {"modes": ["pickup"], "default": "pickup", "timezone": "Europe/Zurich"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "Photo ID", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"seasons": [{"key": "winter", "label": "Winter", "startDate": "2026-12-01", "endDate": "2027-04-15"}]}},
         ctx={"slot_count": 3, "duration_minutes": 4320}, expect=13500,
         depends=["inventory.mode", "inventory.returnRequired", "prerequisites", "timing.seasons", "payments.schedule", "booking.granularity"]),

    dict(n=2, name="Dr. Halina's Dental Practice", booked="Dentist appointments", price="Fixed per visit",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:intake T:instant M:onsite",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "rate": {"per": "slot", "amountMinorUnits": 6000}},
                 "payments": {"flow": "pay_on_site"},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "intake", "kind": "intake_form", "label": "Patient intake", "appliesTo": "customer", "required": True, "blocksConfirmation": True,
                                    "fields": [{"key": "reason", "label": "Reason for visit", "type": "text", "required": True}]}],
                 "metaFields": {"bookings": [{"key": "reason", "label": "Reason", "type": "text"}]}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=6000,
         depends=["booking.unitKind", "prerequisites", "payments.flow"]),

    dict(n=3, name="Kraków Escape Rooms", booked="Whole room, per group", price="Tiered by headcount",
         flags="U:room P:tiered I:none D:fixed L:onsite Y:buyout Q:none T:instant M:prepay",
         config={"booking": {"unitKind": "room", "party": {"mode": "buyout", "min": 2, "max": 6, "matchResourceCapacity": True}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 12000},
                             "tiers": [{"key": "small", "label": "2-3 players", "amountMinorUnits": 9000, "appliesWhen": {"partySize": {"max": 3}}},
                                       {"key": "large", "label": "4-6 players", "amountMinorUnits": 12000, "appliesWhen": {"partySize": {"min": 4}}}]}},
         ctx={"slot_count": 1, "party_size": 5, "duration_minutes": 60}, expect=12000,
         depends=["pricing.tiers", "booking.party.mode", "booking.party.matchResourceCapacity"]),

    dict(n=4, name="Vinyasa Yoga Studio", booked="Class spots", price="Class-pass subscription",
         flags="U:class P:subsn I:none D:fixed L:onsite Y:solo Q:member T:waitlist M:subsn",
         config={"booking": {"unitKind": "class_capacity"},
                 "pricing": {"model": "subscription", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "prepay", "billingCycle": "monthly"},
                 "capabilities": {"entitlements": True, "waitlist": True, "prerequisites": True},
                 "entitlements": {"enabled": True, "kind": "membership",
                                  "plans": [{"key": "unlimited", "label": "Unlimited", "priceMinorUnits": 9900, "cycle": "monthly", "credits": None, "appliesToServices": [], "discountBps": 0}]},
                 "prerequisites": [{"key": "member", "kind": "membership", "label": "Active membership", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"waitlist": {"enabled": True, "autoPromote": True, "maxPerSlot": 10}}},
         ctx={"slot_count": 1, "duration_minutes": 75}, expect=0,
         depends=["entitlements", "timing.waitlist", "prerequisites", "payments.billingCycle"]),

    dict(n=5, name="Mobile Car Valeting", booked="Valet at your address", price="Tiered by vehicle size",
         flags="U:slot P:tiered I:none D:variable L:atcust Y:solo Q:none T:request M:onsite",
         config={"booking": {"duration": {"mode": "variable", "minUnits": 1, "maxUnits": 4},
                             "subject": {"enabled": True, "noun": "Vehicle", "fields": [{"key": "size", "label": "Size", "type": "select", "options": ["hatch", "suv"]}]}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 4000},
                             "tiers": [{"key": "suv", "label": "SUV", "amountMinorUnits": 6000, "appliesWhen": {"subjectField": {"key": "size", "equals": "suv"}}}]},
                 "payments": {"flow": "pay_on_site"},
                 "location": {"modes": ["at_customer"], "default": "at_customer",
                              "serviceArea": {"radiusKm": 25, "travelBufferMinutes": 30, "feeBands": []}},
                 "timing": {"confirmation": "request_approve", "leadTimeMinutes": 240}},
         ctx={"slot_count": 2, "duration_minutes": 120, "subject": {"size": "suv"}}, expect=6000,
         depends=["location.serviceArea", "booking.subject", "pricing.tiers", "timing.confirmation", "timing.leadTimeMinutes"]),

    dict(n=6, name="The Barbers on Floriańska", booked="Walk-in queue position", price="Fixed per cut",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:none T:queue M:onsite",
         config={"booking": {"unitKind": "staff", "granularity": "none"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 2500}},
                 "payments": {"flow": "pay_on_site"}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=2500,
         depends=["booking.granularity"], blocked="E1 — queue availability (no start times); needs availabilityStrategy"),

    dict(n=7, name="Community Allotment Plots", booked="Annual plot lease", price="Annual subscription",
         flags="U:subsn P:subsn I:serial D:open L:onsite Y:solo Q:approval T:waitlist M:invoice",
         config={"booking": {"unitKind": "subscription_slot", "granularity": "month", "duration": {"mode": "open_ended"}},
                 "pricing": {"model": "subscription", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 6500}},
                 "payments": {"flow": "invoice_after", "billingCycle": "annual"},
                 "inventory": {"mode": "serialised"},
                 "capabilities": {"inventory": True, "waitlist": True, "prerequisites": True, "recurrence": True},
                 "recurrence": {"enabled": True, "patterns": ["monthly"], "term": {"mode": "rolling", "noticePeriodDays": 90}},
                 "prerequisites": [{"key": "approval", "kind": "approval", "label": "Committee approval", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve", "waitlist": {"enabled": True, "autoPromote": False, "maxPerSlot": 200}}},
         ctx={"slot_count": 1, "duration_minutes": 43200}, expect=6500,
         depends=["booking.duration.mode", "inventory.mode", "recurrence", "timing.waitlist", "prerequisites"],
         blocked="E2 — open-ended term; needs date_range availabilityStrategy"),

    dict(n=8, name="Farm Shop Veg Boxes", booked="Weekly box (consumable stock)", price="Weekly subscription",
         flags="U:stock P:subsn I:consum D:fixed L:pickup Y:solo Q:none T:blackout M:subsn",
         config={"booking": {"unitKind": "stock_item"},
                 "pricing": {"model": "subscription", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 1800}},
                 "payments": {"flow": "prepay", "billingCycle": "weekly"},
                 "inventory": {"mode": "consumable", "restockCycle": "weekly"},
                 "capabilities": {"inventory": True, "recurrence": True},
                 "recurrence": {"enabled": True, "patterns": ["weekly"], "maxOccurrences": 52},
                 "location": {"modes": ["pickup"], "default": "pickup", "fulfilment": {"windowMinutes": 180, "cutoffHoursBefore": 48}},
                 "timing": {"blackouts": [{"key": "xmas", "label": "Christmas", "startDate": "2026-12-24", "endDate": "2027-01-02"}]}},
         ctx={"slot_count": 1, "duration_minutes": 180}, expect=1800,
         depends=["inventory.mode", "inventory.restockCycle", "recurrence", "location.fulfilment", "timing.blackouts"]),

    dict(n=9, name="Blood Donation Centre", booked="Donation appointment", price="Free",
         flags="U:slot P:free I:none D:fixed L:onsite Y:solo Q:waiver T:instant M:none",
         config={"pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"},
                 "capabilities": {"payments": False, "prerequisites": True, "reviews": False},
                 "prerequisites": [{"key": "health", "kind": "waiver", "label": "Health screening", "appliesTo": "customer", "required": True, "validityDays": 90, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "duration_minutes": 45}, expect=0,
         depends=["capabilities", "prerequisites"]),

    dict(n=10, name="City Tennis Courts", booked="Court hours", price="Per hour, member rate",
         flags="U:asset P:hourly I:finite D:chosen L:onsite Y:group Q:member T:blackout M:prepay",
         config={"booking": {"unitKind": "asset", "party": {"mode": "group", "min": 1, "max": 4},
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 4, "incrementUnits": 1}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 1200}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "entitlements": True},
                 "entitlements": {"enabled": True, "kind": "membership",
                                  "plans": [{"key": "resident", "label": "Resident", "priceMinorUnits": 4500, "cycle": "annual", "credits": None, "appliesToServices": [], "discountBps": 2500}]},
                 "timing": {"blackouts": [{"key": "tournament", "label": "Club tournament", "startDate": "2026-07-01", "endDate": "2026-07-07"}]}},
         ctx={"slot_count": 3, "party_size": 4, "duration_minutes": 90}, expect=1800,
         depends=["pricing.chargePerPerson", "entitlements", "timing.blackouts", "inventory.mode"]),
]

SINGLE += [
    dict(n=11, name="Hilltop Boutique Hotel", booked="Room nights", price="Per night x per person",
         flags="U:room P:person I:finite D:chosen L:onsite Y:group Q:id T:instant M:depbal",
         config={"booking": {"unitKind": "room", "granularity": "night",
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 14},
                             "party": {"mode": "group", "min": 1, "max": 4,
                                       "composition": [{"key": "adult", "label": "Adult", "priceFactor": 1.0},
                                                       {"key": "child", "label": "Child", "priceFactor": 0.5}]}},
                 "pricing": {"model": "per_person", "rate": {"per": "night", "amountMinorUnits": 9000},
                             "deposit": {"enabled": True, "kind": "percent", "value": 20, "refundable": False},
                             "tiers": [{"key": "peak", "label": "Peak", "amountMinorUnits": 12000,
                                        "validFrom": "2026-07-01", "validUntil": "2026-08-31"}]},
                 "payments": {"flow": "split"}, "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "ID at check-in", "appliesTo": "customer", "required": True, "blocksConfirmation": False}]},
         ctx={"slot_count": 3, "party_size": 2, "duration_minutes": 4320, "now": datetime(2026, 10, 1, tzinfo=timezone.utc)},
         expect=54000, depends=["booking.granularity", "booking.party.composition", "pricing.deposit", "pricing.tiers"]),

    dict(n=12, name="Private Chef at Home", booked="Chef's evening", price="Quote on request",
         flags="U:slot P:quote I:none D:variable L:atcust Y:group Q:intake T:request M:invoice",
         config={"booking": {"duration": {"mode": "variable", "minUnits": 1, "maxUnits": 8}, "party": {"mode": "group", "min": 2, "max": 20}},
                 "pricing": {"model": "quote", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "invoice_after"},
                 "capabilities": {"quotes": True, "prerequisites": True},
                 "location": {"modes": ["at_customer"], "default": "at_customer", "serviceArea": {"radiusKm": 40, "travelBufferMinutes": 60, "feeBands": []}},
                 "prerequisites": [{"key": "brief", "kind": "intake_form", "label": "Menu brief", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 4, "party_size": 8, "duration_minutes": 240}, expect=0,
         depends=["capabilities", "pricing.rate", "location.serviceArea", "timing.confirmation"]),

    dict(n=13, name="University Lab Equipment", booked="Serialised instruments", price="Free (internal)",
         flags="U:asset P:free I:serial D:chosen L:onsite Y:solo Q:id T:request M:none",
         config={"booking": {"unitKind": "asset", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 8}},
                 "pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"}, "inventory": {"mode": "serialised"},
                 "capabilities": {"payments": False, "inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "cert", "kind": "credential", "label": "Instrument training", "appliesTo": "customer", "required": True, "validityDays": 730, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve", "blackouts": [{"key": "service", "label": "Maintenance", "startDate": "2026-09-01", "endDate": "2026-09-05"}]}},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=0,
         depends=["capabilities", "inventory.mode", "prerequisites", "timing.blackouts"]),

    dict(n=14, name="Aqua Park Day Sessions", booked="Session capacity", price="Per person, age bands",
         flags="U:class P:person I:none D:fixed L:onsite Y:group Q:none T:season M:prepay",
         config={"booking": {"unitKind": "class_capacity",
                             "party": {"mode": "group", "min": 1, "max": 10,
                                       "composition": [{"key": "adult", "label": "Adult", "priceFactor": 1.0},
                                                       {"key": "child", "label": "Child", "priceFactor": 0.5}]}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 2500}},
                 "timing": {"seasons": [{"key": "summer", "label": "Summer", "startDate": "2026-06-01", "endDate": "2026-09-15"}]}},
         ctx={"slot_count": 1, "party_size": 4, "person_units": 3.0, "duration_minutes": 240}, expect=7500,
         depends=["booking.party.composition", "timing.seasons"]),

    dict(n=15, name="Driving School", booked="Instructor hours", price="Per hour, lesson packs",
         flags="U:staff P:hourly I:none D:fixed L:atcust Y:solo Q:id T:instant M:prepay",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 3500}},
                 "capabilities": {"entitlements": True, "prerequisites": True},
                 "entitlements": {"enabled": True, "kind": "credits",
                                  "plans": [{"key": "pack10", "label": "10 lessons", "priceMinorUnits": 32000, "cycle": "none", "credits": 10, "appliesToServices": [], "discountBps": 0}]},
                 "location": {"modes": ["at_customer"], "default": "at_customer", "serviceArea": {"radiusKm": 15, "travelBufferMinutes": 15, "feeBands": []}},
                 "prerequisites": [{"key": "licence", "kind": "licence", "label": "Provisional licence", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=7000,
         depends=["entitlements", "prerequisites", "location.serviceArea"]),

    dict(n=16, name="Recording Studio", booked="Room + engineer", price="Per hour, min block",
         flags="U:room P:hourly I:none D:chosen L:onsite Y:group Q:none T:request M:depbal",
         config={"booking": {"unitKind": "room", "duration": {"mode": "customer_chosen", "minUnits": 3, "maxUnits": 12},
                             "party": {"mode": "group", "min": 1, "max": 8, "matchResourceCapacity": True},
                             "options": [{"key": "engineer", "label": "Engineer", "type": "boolean",
                                          "choices": [{"key": "yes", "label": "With engineer", "priceMinorUnits": 4000, "requires": []}]}]},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 5000},
                             "deposit": {"enabled": True, "kind": "flat", "value": 5000, "refundable": True}},
                 "payments": {"flow": "split"}, "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 4, "duration_minutes": 240}, expect=20000,
         depends=["booking.duration.minUnits", "booking.options", "pricing.deposit", "booking.party.matchResourceCapacity"]),

    dict(n=17, name="Vaccination Course (2-dose)", booked="Dose 1 + dose 2 pair", price="Free",
         flags="U:slot P:free I:consum D:fixed L:onsite Y:solo Q:waiver T:season M:none",
         config={"booking": {"sequence": {"enabled": True, "steps": 2, "minGapHours": 504, "maxGapHours": 2016}},
                 "pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"}, "inventory": {"mode": "consumable", "restockCycle": "weekly"},
                 "capabilities": {"payments": False, "inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "consent", "kind": "waiver", "label": "Medical consent", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"seasons": [{"key": "flu", "label": "Flu season", "startDate": "2026-10-01", "endDate": "2027-02-28"}]}},
         ctx={"slot_count": 1, "duration_minutes": 15}, expect=0,
         depends=["booking.sequence", "inventory.mode", "prerequisites", "timing.seasons", "capabilities"],
         blocked="E6 — dependent bookings; needs booking_series + expander"),

    dict(n=18, name="Dog Grooming Salon", booked="Groomer slot, per pet", price="Tiered by size",
         flags="U:staff P:tiered I:none D:variable L:onsite Y:solo Q:intake T:instant M:onsite",
         config={"booking": {"unitKind": "staff", "duration": {"mode": "variable", "minUnits": 1, "maxUnits": 4},
                             "subject": {"enabled": True, "noun": "Dog",
                                         "fields": [{"key": "size", "label": "Size", "type": "select", "options": ["small", "large"]}]}},
                 "pricing": {"model": "tiered", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 3500},
                             "tiers": [{"key": "large", "label": "Large breed", "amountMinorUnits": 5500,
                                        "appliesWhen": {"subjectField": {"key": "size", "equals": "large"}}}]},
                 "payments": {"flow": "pay_on_site"},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "vacc", "kind": "intake_form", "label": "Vaccination record", "appliesTo": "subject", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 2, "duration_minutes": 90, "subject": {"size": "large"}}, expect=5500,
         depends=["booking.subject", "pricing.tiers", "prerequisites"]),

    dict(n=19, name="Self-Storage Units", booked="Serialised unit, monthly", price="Monthly subscription",
         flags="U:subsn P:subsn I:serial D:open L:onsite Y:solo Q:id T:instant M:invoice",
         config={"booking": {"unitKind": "subscription_slot", "granularity": "month", "duration": {"mode": "open_ended"}},
                 "pricing": {"model": "subscription", "chargePerPerson": False, "rate": {"per": "month", "amountMinorUnits": 8000}},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "inventory": {"mode": "serialised"},
                 "capabilities": {"inventory": True, "recurrence": True, "prerequisites": True},
                 "recurrence": {"enabled": True, "patterns": ["monthly"], "term": {"mode": "rolling", "noticePeriodDays": 30}},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "Photo ID", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "duration_minutes": 43200}, expect=8000,
         depends=["booking.duration.mode", "payments.billingCycle", "recurrence", "inventory.mode"],
         blocked="E2 — open-ended term; needs date_range availabilityStrategy"),

    dict(n=20, name="Theatre Reserved Seating", booked="Specific seats", price="Tiered by zone",
         flags="U:seat P:tiered I:finite D:fixed L:onsite Y:group Q:none T:instant M:prepay",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 8}},
                 "pricing": {"model": "tiered", "rate": {"per": "person", "amountMinorUnits": 4000},
                             "tiers": [{"key": "stalls", "label": "Stalls", "amountMinorUnits": 6500, "appliesWhen": {"zone": "stalls"}}]},
                 "inventory": {"mode": "finite", "seatMap": {"enabled": True, "adjacencyRequired": True}},
                 "capabilities": {"inventory": True}},
         ctx={"slot_count": 1, "party_size": 2, "zone": "stalls", "duration_minutes": 150}, expect=13000,
         depends=["pricing.tiers", "inventory.seatMap"],
         blocked="E3 — positional inventory + adjacency; deferred by design"),

    dict(n=21, name="Physiotherapy (insurer-billed)", booked="Physio appointment", price="Fixed, insurer pays",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:approval T:request M:invoice",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "rate": {"per": "slot", "amountMinorUnits": 4500}},
                 "payments": {"flow": "invoice_after", "payer": "third_party"},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "referral", "kind": "approval", "label": "GP referral", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 1, "duration_minutes": 45}, expect=4500,
         depends=["payments.payer", "prerequisites", "timing.confirmation"]),

    dict(n=22, name="Van Hire, driver optional", booked="Van, self-drive or driven", price="Per day + add-on",
         flags="U:asset P:unit I:rentable D:chosen L:delivery Y:solo Q:id T:instant M:depbal",
         config={"booking": {"unitKind": "asset", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 14},
                             "options": [{"key": "driver", "label": "With driver", "type": "select",
                                          "choices": [{"key": "self", "label": "Self-drive", "priceMinorUnits": 0, "requires": ["licence"]},
                                                      {"key": "driven", "label": "With driver", "priceMinorUnits": 12000, "requires": []}]}]},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "day", "amountMinorUnits": 7000},
                             "fees": [{"key": "delivery", "label": "Delivery", "kind": "flat", "amountMinorUnits": 2500}],
                             "deposit": {"enabled": True, "kind": "percent", "value": 25, "refundable": True}},
                 "payments": {"flow": "split"}, "inventory": {"mode": "rentable", "returnRequired": True, "loanPeriodHours": 336},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["delivery"], "default": "delivery"},
                 "prerequisites": [{"key": "licence", "kind": "licence", "label": "Driving licence", "appliesTo": "customer", "required": False, "blocksConfirmation": True}]},
         ctx={"slot_count": 2, "duration_minutes": 2880}, expect=16500,
         depends=["booking.options", "pricing.fees", "inventory.mode", "prerequisites"]),

    dict(n=23, name="Online Language Tutor", booked="Remote lesson", price="Per hour",
         flags="U:slot P:hourly I:none D:fixed L:remote Y:solo Q:none T:instant M:prepay",
         config={"pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 3000},
                             "tiers": [{"key": "trial", "label": "First lesson free", "amountMinorUnits": 0, "appliesWhen": {"bookingIndex": {"max": 0}}}]},
                 "location": {"modes": ["remote"], "default": "remote", "timezone": "Europe/Warsaw", "remote": {"meetingLinkMode": "generated"}}},
         ctx={"slot_count": 1, "duration_minutes": 60, "booking_index": 3}, expect=3000,
         depends=["location.remote", "location.timezone", "pricing.tiers"]),

    dict(n=24, name="Charity Gala", booked="Table seats, RSVP", price="Free + optional donation",
         flags="U:seat P:free I:finite D:fixed L:onsite Y:group Q:approval T:waitlist M:none",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 10}},
                 "pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"}, "inventory": {"mode": "finite"},
                 "capabilities": {"payments": False, "inventory": True, "waitlist": True, "prerequisites": True, "reviews": False},
                 "prerequisites": [{"key": "invite", "kind": "approval", "label": "Invitation", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"waitlist": {"enabled": True, "autoPromote": True, "maxPerSlot": 50}}},
         ctx={"slot_count": 1, "party_size": 4, "duration_minutes": 240}, expect=0,
         depends=["capabilities", "timing.waitlist", "prerequisites", "inventory.mode"]),

    dict(n=25, name="Community Tool Library", booked="Serialised tools on loan", price="Free w/ membership + late fees",
         flags="U:asset P:free I:serial D:fixed L:pickup Y:solo Q:member T:instant M:invoice",
         config={"booking": {"unitKind": "asset"},
                 "pricing": {"model": "free", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "invoice_after"},
                 "inventory": {"mode": "serialised", "returnRequired": True, "loanPeriodHours": 168, "overdueFeePerDayMinorUnits": 100},
                 "capabilities": {"inventory": True, "entitlements": True, "prerequisites": True},
                 "entitlements": {"enabled": True, "kind": "membership",
                                  "plans": [{"key": "member", "label": "Member", "priceMinorUnits": 2000, "cycle": "annual", "credits": None, "appliesToServices": [], "discountBps": 0}]},
                 "location": {"modes": ["pickup"], "default": "pickup"},
                 "prerequisites": [{"key": "member", "kind": "membership", "label": "Library membership", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "duration_minutes": 10080}, expect=0,
         depends=["inventory.returnRequired", "inventory.overdueFeePerDayMinorUnits", "entitlements", "prerequisites"],
         blocked="E7 — checked_out/returned/overdue lifecycle + fee accrual"),
]

MULTI = [
    dict(n=26, name="TradieNow (plumbers/sparks)", booked="Trade callout", price="Quote on request",
         flags="U:slot P:quote I:none D:variable L:atcust Y:solo Q:intake T:request M:invoice+comm",
         config={"booking": {"duration": {"mode": "variable", "minUnits": 1, "maxUnits": 8}},
                 "pricing": {"model": "quote", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "invoice_after"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1200, "chargedOn": "completion"},
                             "tenantVerification": {"required": True, "credentials": [{"key": "gas_safe", "label": "Gas Safe", "expires": True}]}},
                 "capabilities": {"quotes": True, "prerequisites": True},
                 "location": {"modes": ["at_customer"], "default": "at_customer", "serviceArea": {"radiusKm": 30, "travelBufferMinutes": 45, "feeBands": []}},
                 "prerequisites": [{"key": "job", "kind": "intake_form", "label": "Job description", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=0,
         depends=["tenancy.commission", "tenancy.tenantVerification", "capabilities", "location.serviceArea"]),

    dict(n=27, name="Fitness Class Marketplace", booked="Class spots across studios", price="Platform credit wallet",
         flags="U:class P:subsn I:none D:fixed L:onsite Y:solo Q:none T:waitlist M:subsn+comm",
         config={"booking": {"unitKind": "class_capacity"},
                 "pricing": {"model": "subscription", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "prepay", "billingCycle": "monthly"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 2000, "chargedOn": "booking"}},
                 "capabilities": {"entitlements": True, "waitlist": True},
                 "entitlements": {"enabled": True, "kind": "credits",
                                  "plans": [{"key": "flex", "label": "Flex 30", "priceMinorUnits": 7900, "cycle": "monthly", "credits": 30, "appliesToServices": [], "discountBps": 0}]},
                 "timing": {"waitlist": {"enabled": True, "autoPromote": True, "maxPerSlot": 20}}},
         ctx={"slot_count": 1, "duration_minutes": 55}, expect=0,
         depends=["entitlements", "timing.waitlist", "tenancy.commission"]),

    dict(n=28, name="Peer-to-Peer Car Sharing", booked="Member-owned cars", price="Per hour + per km metered",
         flags="U:asset P:hourly I:serial D:chosen L:pickup Y:solo Q:id T:instant M:depbal+comm",
         config={"booking": {"unitKind": "asset", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 48},
                             "subject": {"enabled": True, "noun": "Vehicle", "fields": []}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False,
                             "rate": {"per": "hour", "amountMinorUnits": 800},
                             "secondaryRate": {"per": "unit", "amountMinorUnits": 25},
                             "deposit": {"enabled": True, "kind": "percent", "value": 10, "refundable": True}},
                 "payments": {"flow": "split", "usageMetered": True},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "completion"},
                             "tenantVerification": {"required": True, "credentials": []}},
                 "inventory": {"mode": "serialised"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["pickup"], "default": "pickup"},
                 "prerequisites": [{"key": "licence", "kind": "licence", "label": "Driving licence", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 3, "duration_minutes": 180, "unit_count": 40}, expect=3400,
         depends=["pricing.secondaryRate", "payments.usageMetered", "tenancy.commission", "inventory.mode"]),

    dict(n=29, name="Coworking Desk Marketplace", booked="Hot desk / fixed desk", price="Day pass or monthly",
         flags="U:seat P:unit I:finite D:chosen L:onsite Y:solo Q:none T:instant M:prepay+comm",
         config={"booking": {"unitKind": "seat", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 30}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "day", "amountMinorUnits": 2000}},
                 "payments": {"flow": "prepay"}, "inventory": {"mode": "finite"},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1000, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True}},
         ctx={"slot_count": 1, "duration_minutes": 1440}, expect=2000,
         depends=["booking.granularity", "tenancy.selfOnboarding", "tenancy.commission", "inventory.mode"]),

    dict(n=30, name="Wedding Venue Marketplace", booked="Whole venue, a full day", price="Quote -> deposit -> balance",
         flags="U:room P:quote I:finite D:open L:onsite Y:buyout Q:approval T:season M:split+comm",
         config={"booking": {"unitKind": "room", "duration": {"mode": "open_ended"}, "party": {"mode": "buyout", "min": 20, "max": 300}},
                 "pricing": {"model": "quote", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "split", "schedule": [
                     {"key": "hold", "label": "Holding deposit", "kind": "flat", "value": 50000, "dueOffsetDays": 0, "relativeTo": "booking"},
                     {"key": "interim", "label": "50%", "kind": "percent", "value": 50, "dueOffsetDays": -180, "relativeTo": "start"},
                     {"key": "balance", "label": "Balance", "kind": "percent", "value": 50, "dueOffsetDays": -30, "relativeTo": "start"}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 800, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"quotes": True, "inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "viewing", "kind": "approval", "label": "Venue viewing", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve", "seasons": [{"key": "wedding", "label": "Season", "startDate": "2027-04-01", "endDate": "2027-10-31"}]}},
         ctx={"slot_count": 1, "party_size": 120, "duration_minutes": 1440}, expect=0,
         depends=["payments.schedule", "timing.seasons", "booking.party.mode", "booking.duration.mode"],
         blocked="E2 — open-ended booking; needs date_range availabilityStrategy"),

    dict(n=31, name="Home Cleaning (recurring)", booked="Weekly cleaner slot", price="Per hour, monthly billed",
         flags="U:subsn P:hourly I:none D:chosen L:atcust Y:solo Q:none T:instant M:subsn+comm",
         config={"booking": {"unitKind": "subscription_slot", "duration": {"mode": "customer_chosen", "minUnits": 2, "maxUnits": 8}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 2800}},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1800, "chargedOn": "completion"}},
                 "capabilities": {"recurrence": True},
                 "recurrence": {"enabled": True, "patterns": ["weekly", "biweekly"], "maxOccurrences": 52},
                 "location": {"modes": ["at_customer"], "default": "at_customer", "serviceArea": {"radiusKm": 20, "travelBufferMinutes": 30, "feeBands": []}}},
         ctx={"slot_count": 3, "duration_minutes": 180}, expect=8400,
         depends=["recurrence", "payments.billingCycle", "location.serviceArea", "tenancy.commission"],
         blocked="E6 — recurring series; needs booking_series + expander"),

    dict(n=32, name="Local Farmers Market", booked="Multi-vendor basket", price="Per unit",
         flags="U:stock P:unit I:consum D:fixed L:pickup Y:solo Q:none T:blackout M:prepay+comm",
         config={"booking": {"unitKind": "stock_item"},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "unit", "amountMinorUnits": 450}},
                 "payments": {"flow": "prepay"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 700, "chargedOn": "booking"}},
                 "inventory": {"mode": "consumable", "restockCycle": "weekly"},
                 "capabilities": {"inventory": True, "cart": True},
                 "location": {"modes": ["pickup"], "default": "pickup", "fulfilment": {"windowMinutes": 120, "cutoffHoursBefore": 24}},
                 "timing": {"blackouts": [{"key": "winter", "label": "Winter break", "startDate": "2027-01-05", "endDate": "2027-02-01"}]}},
         ctx={"slot_count": 1, "unit_count": 6, "duration_minutes": 120}, expect=2700,
         depends=["capabilities", "inventory.mode", "location.fulfilment", "timing.blackouts"]),

    dict(n=33, name="Specialist Marketplace (insurer)", booked="Consultant appointment", price="Fixed, insurer pays",
         flags="U:staff P:fixed I:none D:fixed L:remote Y:solo Q:approval T:request M:invoice+comm",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "rate": {"per": "slot", "amountMinorUnits": 12000}},
                 "payments": {"flow": "invoice_after", "payer": "third_party"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 900, "chargedOn": "completion"},
                             "tenantVerification": {"required": True, "credentials": [{"key": "gmc", "label": "GMC registration", "expires": True}]}},
                 "capabilities": {"prerequisites": True},
                 "location": {"modes": ["remote", "on_site"], "default": "remote", "remote": {"meetingLinkMode": "generated"}},
                 "prerequisites": [{"key": "referral", "kind": "approval", "label": "Referral", "appliesTo": "customer", "required": True, "blocksConfirmation": True, "verifier": "insurer_api"}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=12000,
         depends=["payments.payer", "prerequisites", "tenancy.tenantVerification", "location.remote"]),

    dict(n=34, name="Event Ticketing Marketplace", booked="GA capacity", price="Early-bird tiers",
         flags="U:class P:tiered I:finite D:fixed L:onsite Y:group Q:none T:waitlist M:prepay+comm",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 10}},
                 "pricing": {"model": "tiered", "rate": {"per": "person", "amountMinorUnits": 5000},
                             "tiers": [{"key": "early", "label": "Early bird", "amountMinorUnits": 3500,
                                        "validFrom": "2026-06-01", "validUntil": "2026-09-01", "quantityCap": 200}]},
                 "payments": {"flow": "prepay"}, "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 600, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True, "waitlist": True},
                 "timing": {"waitlist": {"enabled": True, "autoPromote": True, "maxPerSlot": 100}}},
         ctx={"slot_count": 1, "party_size": 3, "duration_minutes": 180}, expect=10500,
         depends=["pricing.tiers", "pricing.tiers[].quantityCap", "timing.waitlist", "inventory.mode"]),

    dict(n=35, name="Construction Plant Rental", booked="Serialised heavy plant", price="Per day + delivery band",
         flags="U:asset P:unit I:serial D:chosen L:delivery Y:solo Q:waiver T:request M:depbal+comm",
         config={"booking": {"unitKind": "asset", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 60}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "day", "amountMinorUnits": 25000},
                             "fees": [{"key": "delivery", "label": "Delivery", "kind": "distanceBand",
                                       "bands": [{"maxKm": 10, "feeMinorUnits": 3000}, {"maxKm": 50, "feeMinorUnits": 8000},
                                                 {"maxKm": None, "feeMinorUnits": 15000}]}],
                             "deposit": {"enabled": True, "kind": "percent", "value": 20, "refundable": True}},
                 "payments": {"flow": "split"}, "inventory": {"mode": "serialised", "returnRequired": True},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1100, "chargedOn": "completion"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["delivery"], "default": "delivery",
                              "serviceArea": {"radiusKm": 120, "travelBufferMinutes": 0,
                                              "feeBands": [{"maxKm": 50, "feeMinorUnits": 8000}]}},
                 "prerequisites": [{"key": "waiver", "kind": "waiver", "label": "Damage waiver", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 2, "duration_minutes": 2880, "distance_km": 40}, expect=58000,
         depends=["pricing.fees", "inventory.mode", "location.serviceArea", "prerequisites"]),

    dict(n=36, name="Online Therapy Marketplace", booked="Remote session", price="Sliding scale",
         flags="U:slot P:tiered I:none D:fixed L:remote Y:solo Q:intake T:instant M:prepay+comm",
         config={"pricing": {"model": "tiered", "chargePerPerson": False, "rate": {"per": "slot", "amountMinorUnits": 8000},
                             "tiers": [{"key": "low", "label": "Reduced rate", "amountMinorUnits": 4000, "appliesWhen": {"zone": "low"}},
                                       {"key": "mid", "label": "Standard", "amountMinorUnits": 6000, "appliesWhen": {"zone": "mid"}}]},
                 "payments": {"flow": "prepay"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "booking"}},
                 "capabilities": {"prerequisites": True},
                 "location": {"modes": ["remote"], "default": "remote", "remote": {"meetingLinkMode": "generated"}},
                 "prerequisites": [{"key": "intake", "kind": "intake_form", "label": "Intake questionnaire", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "discovery": {"matching": {"enabled": True, "source": "intake_form"}}},
         ctx={"slot_count": 1, "duration_minutes": 50, "zone": "low"}, expect=4000,
         depends=["pricing.tiers", "discovery.matching", "prerequisites", "location.remote"]),

    dict(n=37, name="Boat Charter Marketplace", booked="Whole boat + skipper", price="Per day, staged payment",
         flags="U:asset P:unit I:serial D:chosen L:pickup Y:buyout Q:id T:season M:split+comm",
         config={"booking": {"unitKind": "asset", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 14},
                             "party": {"mode": "buyout", "min": 1, "max": 12},
                             "options": [{"key": "skipper", "label": "Skipper", "type": "select",
                                          "choices": [{"key": "self", "label": "Bareboat", "priceMinorUnits": 0, "requires": ["skipper_licence"]},
                                                      {"key": "crewed", "label": "With skipper", "priceMinorUnits": 18000, "requires": []}]}]},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "day", "amountMinorUnits": 45000},
                             "deposit": {"enabled": True, "kind": "percent", "value": 30, "refundable": True}},
                 "payments": {"flow": "split", "schedule": [
                     {"key": "deposit", "label": "Deposit", "kind": "percent", "value": 30, "dueOffsetDays": 0, "relativeTo": "booking"},
                     {"key": "balance", "label": "Balance", "kind": "percent", "value": 70, "dueOffsetDays": -30, "relativeTo": "start"}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"}},
                 "inventory": {"mode": "serialised"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["pickup"], "default": "pickup"},
                 "prerequisites": [{"key": "skipper_licence", "kind": "licence", "label": "Skipper licence", "appliesTo": "customer", "required": False, "blocksConfirmation": True}],
                 "timing": {"seasons": [{"key": "sail", "label": "Sailing season", "startDate": "2027-05-01", "endDate": "2027-09-30"}]}},
         ctx={"slot_count": 3, "duration_minutes": 4320}, expect=135000,
         depends=["payments.schedule", "booking.options", "timing.seasons", "inventory.mode"]),

    dict(n=38, name="Tutoring Marketplace", booked="1:1 AND group classes", price="Per hour / per person",
         flags="U:class+slot P:person+hourly I:none D:fixed L:remote+onsite Y:solo+group Q:none T:instant M:prepay+comm",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 12}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 2000}},
                 "payments": {"flow": "prepay"},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1400, "chargedOn": "booking"}},
                 "location": {"modes": ["remote", "on_site"], "default": "remote"}},
         ctx={"slot_count": 1, "party_size": 4, "duration_minutes": 60}, expect=8000,
         depends=["booking.unitKind", "location.modes"],
         blocked="E10 — per-service vocabulary/unitKind; vocabulary is global today"),

    dict(n=39, name="Salon Marketplace", booked="Named stylist", price="Fixed, no-show deposit",
         flags="U:staff P:fixed I:none D:variable L:onsite Y:solo Q:none T:instant M:depbal+comm",
         config={"booking": {"unitKind": "staff", "duration": {"mode": "variable", "minUnits": 1, "maxUnits": 4}},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "slot", "amountMinorUnits": 5500},
                             "deposit": {"enabled": True, "kind": "flat", "value": 1000, "refundable": False}},
                 "payments": {"flow": "split", "noShowFee": {"enabled": True, "amountMinorUnits": 1000}},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1200, "chargedOn": "completion"}},
                 "timing": {"blackouts": [{"key": "holiday", "label": "Staff holiday", "startDate": "2026-12-20", "endDate": "2027-01-03"}]}},
         ctx={"slot_count": 1, "duration_minutes": 45}, expect=5500,
         depends=["payments.noShowFee", "booking.unitKind", "timing.blackouts", "pricing.deposit"]),

    dict(n=40, name="Restaurant Reservations", booked="Tables sized to party", price="Free + no-show fee",
         flags="U:asset P:free I:finite D:fixed L:onsite Y:group Q:none T:waitlist M:none+comm",
         config={"booking": {"unitKind": "asset", "party": {"mode": "group", "min": 1, "max": 12, "matchResourceCapacity": True}},
                 "pricing": {"model": "free", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none", "noShowFee": {"enabled": True, "amountMinorUnits": 1500}},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 300, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"payments": False, "inventory": True, "waitlist": True},
                 "timing": {"waitlist": {"enabled": True, "autoPromote": True, "maxPerSlot": 25}}},
         ctx={"slot_count": 1, "party_size": 5, "duration_minutes": 90}, expect=0,
         depends=["booking.party.matchResourceCapacity", "payments.noShowFee", "timing.waitlist"],
         blocked="E3 — capacity_fit resourceSelector (pick a table that fits the party)"),
]

MULTI += [
    dict(n=41, name="Warehouse Pallet Space", booked="Pallet slots per week", price="Per unit x per week",
         flags="U:stock P:unit I:finite D:open L:delivery Y:solo Q:approval T:request M:invoice+comm",
         config={"booking": {"unitKind": "stock_item", "granularity": "week", "duration": {"mode": "open_ended"}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False,
                             "rate": {"per": "unit", "amountMinorUnits": 300},
                             "secondaryRate": {"per": "week", "amountMinorUnits": 1000}},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 900, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["delivery"], "default": "delivery"},
                 "prerequisites": [{"key": "account", "kind": "approval", "label": "Trade account", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 1, "unit_count": 20, "duration_minutes": 40320}, expect=10000,
         depends=["pricing.secondaryRate", "booking.duration.mode", "payments.billingCycle"],
         blocked="E2 — open-ended term; needs date_range availabilityStrategy",
         limitation="pricing.secondaryRate ADDS to the base; a genuine units x weeks PRODUCT "
                    "(20 pallets x 4 weeks) cannot be expressed. Quoted 20x300 + 4x1000 = 10000, "
                    "not 20x4x300 = 24000."),

    dict(n=42, name="Photographer Marketplace", booked="Shoot packages", price="Tiered packages",
         flags="U:slot P:tiered I:none D:fixed L:atcust Y:group Q:none T:request M:split+comm",
         config={"booking": {"party": {"mode": "group", "min": 1, "max": 50}},
                 "pricing": {"model": "tiered", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 60000},
                             "tiers": [{"key": "half", "label": "Half day", "amountMinorUnits": 35000, "appliesWhen": {"zone": "half"}}]},
                 "payments": {"flow": "split", "schedule": [
                     {"key": "book", "label": "Booking fee", "kind": "percent", "value": 25, "dueOffsetDays": 0, "relativeTo": "booking"},
                     {"key": "delivery", "label": "On delivery", "kind": "percent", "value": 75, "dueOffsetDays": 14, "relativeTo": "start"}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1300, "chargedOn": "completion"}},
                 "location": {"modes": ["at_customer"], "default": "at_customer", "serviceArea": {"radiusKm": 60, "travelBufferMinutes": 60, "feeBands": []}},
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 4, "party_size": 20, "duration_minutes": 240, "zone": "half"}, expect=35000,
         depends=["pricing.tiers", "payments.schedule", "location.serviceArea"]),

    dict(n=43, name="Nursery / Childcare", booked="Weekday sessions", price="Monthly subscription",
         flags="U:class P:subsn I:finite D:fixed L:onsite Y:solo Q:waiver T:waitlist M:invoice+comm",
         config={"booking": {"unitKind": "class_capacity",
                             "subject": {"enabled": True, "noun": "Child",
                                         "fields": [{"key": "dob", "label": "Date of birth", "type": "date", "required": True}]}},
                 "pricing": {"model": "subscription", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 500, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite", "ratioConstraint": {"perResourceKey": "staff", "ratio": 4}},
                 "capabilities": {"inventory": True, "waitlist": True, "recurrence": True, "prerequisites": True},
                 "recurrence": {"enabled": True, "patterns": ["weekly"], "maxOccurrences": 40},
                 "prerequisites": [{"key": "medical", "kind": "waiver", "label": "Medical + safeguarding", "appliesTo": "subject", "required": True, "blocksConfirmation": True}],
                 "timing": {"waitlist": {"enabled": True, "autoPromote": False, "maxPerSlot": 60}}},
         ctx={"slot_count": 1, "duration_minutes": 300}, expect=0,
         depends=["booking.subject", "inventory.ratioConstraint", "recurrence", "timing.waitlist", "prerequisites"]),

    dict(n=44, name="Parking Space Marketplace", booked="Serialised bays", price="Per hour, daily cap",
         flags="U:asset P:hourly I:serial D:chosen L:onsite Y:solo Q:none T:instant M:prepay+comm",
         config={"booking": {"unitKind": "asset", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 24},
                             "subject": {"enabled": True, "noun": "Vehicle",
                                         "fields": [{"key": "reg", "label": "Registration", "type": "text", "required": True}]}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 350},
                             "caps": {"perBookingMinorUnits": 2000, "perDayMinorUnits": 2000}},
                 "payments": {"flow": "prepay"},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1600, "chargedOn": "booking"}},
                 "inventory": {"mode": "serialised"}, "capabilities": {"inventory": True}},
         ctx={"slot_count": 10, "duration_minutes": 600}, expect=2000,
         depends=["pricing.caps.perBookingMinorUnits", "pricing.caps.perDayMinorUnits", "booking.subject", "inventory.mode"]),

    dict(n=45, name="Freelance Design Marketplace", booked="A project, no calendar", price="Quote -> milestones",
         flags="U:project P:quote I:none D:open L:remote Y:solo Q:approval T:request M:split+comm",
         config={"booking": {"unitKind": "project", "granularity": "none", "duration": {"mode": "open_ended"}},
                 "pricing": {"model": "quote", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "split", "schedule": [
                     {"key": "m1", "label": "Milestone 1", "kind": "percent", "value": 33, "dueOffsetDays": 0, "relativeTo": "booking"},
                     {"key": "m2", "label": "Milestone 2", "kind": "percent", "value": 33, "dueOffsetDays": 30, "relativeTo": "booking"},
                     {"key": "m3", "label": "Final", "kind": "percent", "value": 34, "dueOffsetDays": 60, "relativeTo": "booking"}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 2000, "chargedOn": "completion"}},
                 "capabilities": {"quotes": True, "prerequisites": True},
                 "location": {"modes": ["remote"], "default": "remote"},
                 "prerequisites": [{"key": "brief", "kind": "approval", "label": "Approved brief", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 1, "duration_minutes": 0}, expect=0,
         depends=["booking.granularity", "booking.duration.mode", "payments.schedule"],
         blocked="E4 — a booking with no slot; `bookings.slot_id` is NOT NULL on a frozen table"),

    dict(n=46, name="Fishing Beat Permits", booked="Rods on a beat", price="Per rod per day",
         flags="U:seat P:person I:finite D:fixed L:onsite Y:group Q:id T:season M:prepay+comm",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 6}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 4500}},
                 "payments": {"flow": "prepay"}, "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 700, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "rod_licence", "kind": "licence", "label": "Rod licence", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"seasons": [{"key": "open", "label": "Open season", "startDate": "2027-03-15", "endDate": "2027-10-15"}],
                            "blackouts": [{"key": "spawn", "label": "Spawning", "startDate": "2027-05-01", "endDate": "2027-05-14"}]}},
         ctx={"slot_count": 1, "party_size": 2, "duration_minutes": 720}, expect=9000,
         depends=["timing.seasons", "timing.blackouts", "prerequisites", "inventory.mode"]),

    dict(n=47, name="Community Events Board", booked="Free RSVP events", price="Free",
         flags="U:class P:free I:none D:fixed L:remote Y:solo Q:none T:instant M:none",
         config={"booking": {"unitKind": "class_capacity"},
                 "pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": False, "rateBps": 0, "chargedOn": "booking"}},
                 "capabilities": {"payments": False, "reviews": False, "follows": True},
                 "location": {"modes": ["remote", "on_site"], "default": "remote"}},
         ctx={"slot_count": 1, "duration_minutes": 90}, expect=0,
         depends=["capabilities", "tenancy.selfOnboarding"]),

    dict(n=48, name="Removals Reverse Auction", booked="Customer posts, firms bid", price="Reverse quote",
         flags="U:slot P:quote I:none D:variable L:delivery Y:solo Q:id T:request M:split+comm",
         config={"booking": {"duration": {"mode": "variable", "minUnits": 1, "maxUnits": 12}},
                 "pricing": {"model": "quote", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "split"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"},
                             "tenantVerification": {"required": True, "credentials": [{"key": "insurance", "label": "Goods in transit", "expires": True}]}},
                 "capabilities": {"quotes": True, "prerequisites": True},
                 "discovery": {"mode": "reverse"},
                 "location": {"modes": ["delivery"], "default": "delivery"},
                 "prerequisites": [{"key": "insurance", "kind": "credential", "label": "Insurance", "appliesTo": "tenant", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 3, "duration_minutes": 360}, expect=0,
         depends=["discovery.mode", "tenancy.tenantVerification", "payments.flow"],
         blocked="E5 — reverse-auction flow; needs quote_requests + bids entities"),

    dict(n=49, name="Pharmacy Click & Collect", booked="Dispensed stock", price="Per unit",
         flags="U:stock P:unit I:consum D:fixed L:pickup Y:solo Q:approval T:blackout M:onsite+comm",
         config={"booking": {"unitKind": "stock_item"},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "unit", "amountMinorUnits": 1200}},
                 "payments": {"flow": "pay_on_site"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 400, "chargedOn": "completion"}},
                 "inventory": {"mode": "consumable", "restockCycle": "daily"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["pickup"], "default": "pickup", "fulfilment": {"windowMinutes": 240, "cutoffHoursBefore": 2}},
                 "prerequisites": [{"key": "rx", "kind": "approval", "label": "Prescription", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"blackouts": [{"key": "bank", "label": "Bank holidays", "startDate": "2026-12-25", "endDate": "2026-12-26"}]}},
         ctx={"slot_count": 1, "unit_count": 2, "duration_minutes": 240}, expect=2400,
         depends=["inventory.mode", "location.fulfilment", "prerequisites", "timing.blackouts"]),

    dict(n=50, name="Shared Kitchen Marketplace", booked="Certified kitchen hours", price="Peak / off-peak tiers",
         flags="U:room P:tiered I:finite D:chosen L:onsite Y:group Q:member T:instant M:invoice+comm",
         config={"booking": {"unitKind": "room", "duration": {"mode": "customer_chosen", "minUnits": 2, "maxUnits": 12},
                             "party": {"mode": "group", "min": 1, "max": 6, "matchResourceCapacity": True}},
                 "pricing": {"model": "tiered", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 4000},
                             "tiers": [{"key": "offpeak", "label": "Off-peak", "amountMinorUnits": 2200,
                                        "appliesWhen": {"timeOfDay": {"from": "18:00", "to": "06:00"}}}]},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "entitlements": True, "prerequisites": True, "recurrence": True},
                 "entitlements": {"enabled": True, "kind": "membership",
                                  "plans": [{"key": "resident", "label": "Resident", "priceMinorUnits": 15000, "cycle": "monthly", "credits": None, "appliesToServices": [], "discountBps": 1500}]},
                 "recurrence": {"enabled": True, "patterns": ["weekly"], "maxOccurrences": 52},
                 "prerequisites": [{"key": "hygiene", "kind": "credential", "label": "Food hygiene cert", "appliesTo": "customer", "required": True, "validityDays": 1095, "blocksConfirmation": True},
                                   {"key": "member", "kind": "membership", "label": "Membership", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 3, "duration_minutes": 180, "start_local": datetime(2026, 8, 18, 20, 0)}, expect=6600,
         depends=["pricing.tiers", "entitlements", "recurrence", "booking.party.matchResourceCapacity", "prerequisites"]),
]

ALL = [dict(p, tenancy="single") for p in SINGLE] + [dict(p, tenancy="multi") for p in MULTI]

try:  # batch 2 (#51-100): probes aimed at dimensions batch 1 never varied
    from pivots_extended import EXTENDED

    ALL += EXTENDED
except ImportError:
    pass


def run_one(p: dict) -> dict:
    cfg = normalize(deep_merge(base(p["tenancy"]), p["config"]))
    errors = validate(cfg)

    priced, price_error = None, None
    if not errors:
        ctx = {"party_size": 1, "now": NOW, **p["ctx"]}
        try:
            priced = quote(cfg["pricing"], ctx)
        except Exception as e:  # a quote must never raise on a validated config
            price_error = f"{type(e).__name__}: {e}"

    mispriced = (
        priced is not None
        and p.get("expect") is not None
        and priced["amountMinorUnits"] != p["expect"]
    )
    # Some findings live in the deposit, not the total (a refundable bond that
    # gets silently clamped to the hire fee still quotes the right price).
    if priced is not None and p.get("expect_deposit") is not None:
        mispriced = mispriced or priced["depositMinorUnits"] != p["expect_deposit"]
    gaps = [d for d in p.get("depends", []) if d not in ENFORCED]
    # `expect` is always the business-CORRECT total. When a pivot declares a
    # `limitation`, a mismatch is the documented proof of that gap rather than a
    # regression — that distinction is what lets this script stay exit-0 while
    # still reporting what the schema cannot yet say.
    known_gap = mispriced and bool(p.get("limitation"))
    return {
        "pivot": p, "config": cfg, "errors": errors, "priced": priced,
        "price_error": price_error, "mispriced": mispriced, "gaps": gaps,
        "known_gap": known_gap,
        "ok": not errors and not price_error and (not mispriced or known_gap),
    }


def check_flag_uniqueness() -> list[str]:
    """The design's hard constraint: no two pivots share a capability tuple."""
    seen, dupes = {}, []
    for p in ALL:
        key = p["flags"].replace("+comm", "")
        if key in seen:
            dupes.append(f"#{p['n']} {p['name']} duplicates #{seen[key]}")
        seen[key] = p["n"]
    return dupes


def main() -> int:
    verbose = "-v" in sys.argv
    markdown = "--md" in sys.argv
    results = [run_one(p) for p in ALL]
    dupes = check_flag_uniqueness()

    expressible = [r for r in results if not r["errors"]]
    enforced_now = [r for r in results if r["ok"] and not r["gaps"] and not r["pivot"].get("blocked")]
    blocked = [r for r in results if r["pivot"].get("blocked")]
    limits = [r for r in results if r["pivot"].get("limitation")]
    broken = [r for r in results if not r["ok"]]

    if markdown:
        print("| # | Pivot | Tenancy | Config valid | Quote | Expected | Engine gap |")
        print("|---|-------|---------|--------------|-------|----------|------------|")
        for r in results:
            p = r["pivot"]
            valid = "ok" if not r["errors"] else f"**FAIL** ({len(r['errors'])})"
            amount = r["priced"]["amountMinorUnits"] if r["priced"] else "-"
            exp = p.get("expect", "-")
            match = "" if not r["mispriced"] else " **MISMATCH**"
            gap = "none — end to end" if not r["gaps"] else f"{len(r['gaps'])} key(s)"
            if p.get("blocked"):
                gap = p["blocked"].split(" — ")[0]
            print(f"| {p['n']} | {p['name']} | {p['tenancy']} | {valid} | {amount}{match} | {exp} | {gap} |")
        print()
    else:
        for r in results:
            p = r["pivot"]
            mark = ("gap " if r["known_gap"] else "ok  ") if r["ok"] else "FAIL"
            note = ""
            if r["errors"]:
                note = f"  <- {len(r['errors'])} config error(s)"
            elif r["known_gap"]:
                if p.get("expect_deposit") is not None and r["priced"]["depositMinorUnits"] != p["expect_deposit"]:
                    note = (f"  GAP deposit {r['priced']['depositMinorUnits']}, "
                            f"correct is {p['expect_deposit']}")
                else:
                    note = f"  GAP quoted {r['priced']['amountMinorUnits']}, correct is {p['expect']}"
            elif r["mispriced"]:
                note = f"  <- quoted {r['priced']['amountMinorUnits']}, expected {p['expect']}"
            elif p.get("blocked"):
                note = f"  [{p['blocked'].split(' — ')[0]}]"
            elif r["gaps"]:
                note = f"  [{len(r['gaps'])} declared-only key(s)]"
            print(f"[{mark}] {p['n']:>2} {p['name']:<34} {p['tenancy']:<6}{note}")
            if verbose:
                for e in r["errors"]:
                    print(f"          ! {e}")
                for g in r["gaps"]:
                    print(f"          - {g}: {DECLARED_ONLY.get(g, 'unmapped')}")
                if p.get("limitation"):
                    print(f"          LIMITATION: {p['limitation']}")

    print()
    n_single = sum(1 for p in ALL if p["tenancy"] == "single")
    print(f"pivots                          : {len(results)} "
          f"({n_single} single-tenant, {len(ALL) - n_single} marketplace)")
    correct = [r for r in results if r["priced"] and not r["mispriced"]]
    gap_results = [r for r in results if r["known_gap"]]
    print(f"expressible in config v2        : {len(expressible)}/{len(results)}")
    print(f"quoted == hand-computed total   : {len(correct)}/{len(results)}")
    print(f"enforced end to end today       : {len(enforced_now)}")
    print(f"awaiting an escape hatch (code) : {len(blocked)}")
    print(f"schema limitations found        : {len(limits)} ({len(gap_results)} proven by a misquote)")
    print(f"unique capability tuples        : {'yes' if not dupes else 'NO — ' + '; '.join(dupes)}")

    for r in limits:
        print(f"\nLIMITATION  #{r['pivot']['n']} {r['pivot']['name']}\n  {r['pivot']['limitation']}")

    if broken:
        print(f"\n{len(broken)} pivot(s) FAILED:")
        for r in broken:
            print(f"  #{r['pivot']['n']} {r['pivot']['name']}")
            for e in r["errors"]:
                print(f"    ! {e}")
            if r["price_error"]:
                print(f"    ! quote raised {r['price_error']}")
            if r["mispriced"]:
                print(f"    ! quoted {r['priced']['amountMinorUnits']}, expected {r['pivot']['expect']}")
    return 1 if (broken or dupes) else 0


if __name__ == "__main__":
    sys.exit(main())
