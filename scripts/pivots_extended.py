"""Pivots #51-100 — probes, not padding.

Batch 1 (#1-50) exhausted the nine design axes: `party` has three values,
`location` five, `duration` four, and 24 of 50 were `on_site`. Generating 50 more
along those axes would produce permutations, not information.

So this batch varies dimensions batch 1 never touched, chosen because each is a
plausible real business AND a place the schema might not reach: currency
exponents, rounding, tax, refund policy, eligibility arithmetic, cross-service
composition, resource-level pricing, and marketplace economics.

**`expect` is always the business-CORRECT total**, not what the engine currently
computes. Where the engine cannot express the model, the mismatch IS the finding
and the pivot carries a `limitation`. That is how #41 (units x weeks) surfaced in
batch 1, and it is the only way a stress test can fail usefully.
"""
from datetime import datetime, timezone

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# A. Currency, exponent and rounding (51-58)
# ---------------------------------------------------------------------------
A = [
    dict(n=51, name="Shinjuku Capsule Hotel", tenancy="single", booked="Capsule nights (JPY)",
         price="Per night, zero-decimal currency",
         flags="U:room P:unit I:finite D:chosen L:onsite Y:solo Q:id T:instant M:prepay X:jpy",
         config={"booking": {"unitKind": "room", "granularity": "night", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 14}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "currency": "JPY", "currencyExponent": 0,
                             "rate": {"per": "night", "amountMinorUnits": 4800}},
                 "inventory": {"mode": "finite"}, "capabilities": {"inventory": True},
                 "location": {"timezone": "Asia/Tokyo"}},
         ctx={"slot_count": 3, "duration_minutes": 4320}, expect=14400,
         depends=["pricing.currency", "pricing.rate"]),

    dict(n=52, name="Kuwait City Dental", tenancy="single", booked="Appointments (KWD)",
         price="Fixed, three-decimal currency",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:intake T:instant M:onsite X:kwd",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "currency": "KWD", "currencyExponent": 3,
                             "rate": {"per": "slot", "amountMinorUnits": 25500}},
                 "payments": {"flow": "pay_on_site"}, "location": {"timezone": "Asia/Kuwait"}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=25500,
         depends=["pricing.currency"]),

    dict(n=53, name="Percent fee stacked on a cap", tenancy="single", booked="Capped hourly hire",
         price="Per hour + 10% service fee, capped",
         flags="U:asset P:hourly I:none D:chosen L:onsite Y:solo Q:none T:instant M:prepay X:caporder",
         config={"pricing": {"model": "per_hour", "chargePerPerson": False,
                             "rate": {"per": "hour", "amountMinorUnits": 1000},
                             "fees": [{"key": "svc", "label": "Service fee", "kind": "percent", "rateBps": 1000}],
                             "caps": {"perBookingMinorUnits": 5000}}},
         ctx={"slot_count": 8, "duration_minutes": 480}, expect=5000,
         depends=["pricing.fees", "pricing.caps.perBookingMinorUnits"]),

    dict(n=54, name="Odd-percent rounding probe", tenancy="single", booked="Consult",
         price="Base 3333 + 8.5% fee",
         flags="U:slot P:fixed I:none D:fixed L:remote Y:solo Q:none T:instant M:prepay X:round",
         config={"pricing": {"model": "fixed", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 3333},
                             "fees": [{"key": "card", "label": "Card fee", "kind": "percent", "rateBps": 850}]},
                 "location": {"modes": ["remote"], "default": "remote"}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=3616,  # 3333 + round(283.305)
         depends=["pricing.fees"]),

    dict(n=55, name="Prepayment deposit above the total", tenancy="single", booked="Micro-session",
         price="Cheap session, oversized non-refundable deposit",
         flags="U:slot P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:depbal X:clamp",
         config={"pricing": {"model": "fixed", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 500},
                             "deposit": {"enabled": True, "kind": "flat", "value": 5000, "refundable": False}},
                 "payments": {"flow": "split"}},
         ctx={"slot_count": 1, "duration_minutes": 15}, expect=500, expect_deposit=500,
         depends=["pricing.deposit"]),

    dict(n=56, name="Two tiers both matching", tenancy="single", booked="Group session",
         price="Overlapping tier windows",
         flags="U:class P:tiered I:none D:fixed L:onsite Y:group Q:none T:instant M:prepay X:tierprec",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 10}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 9000},
                             "tiers": [{"key": "specific", "label": "4-6", "amountMinorUnits": 5000, "appliesWhen": {"partySize": {"min": 4, "max": 6}}},
                                       {"key": "broad", "label": "2+", "amountMinorUnits": 7000, "appliesWhen": {"partySize": {"min": 2}}}]}},
         ctx={"slot_count": 1, "party_size": 5, "duration_minutes": 60}, expect=5000,
         depends=["pricing.tiers"]),

    dict(n=57, name="Free class with a booking fee", tenancy="single", booked="Free class + platform fee",
         price="Zero base, flat fee",
         flags="U:class P:free I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay X:zerobase",
         config={"booking": {"unitKind": "class_capacity"},
                 "pricing": {"model": "free", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 0},
                             "fees": [{"key": "booking", "label": "Booking fee", "kind": "flat", "amountMinorUnits": 150}]}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=150,
         depends=["pricing.fees"]),

    dict(n=58, name="Sliding VAT-inclusive salon", tenancy="single", booked="Treatment, VAT inclusive",
         price="Gross 6000 incl. 23% VAT",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:onsite X:vat",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 6000}},
                 "payments": {"flow": "pay_on_site"}},
         ctx={"slot_count": 1, "duration_minutes": 45}, expect=6000,
         depends=["pricing.rate"],
         limitation="Gross total is right, but the schema has NO tax concept: the 1122 VAT "
                    "component cannot be declared, so no invoice/receipt can break it out and a "
                    "VAT-exclusive niche (add 23% at checkout) cannot be expressed at all."),
]

# ---------------------------------------------------------------------------
# B. Tax, refunds and money that moves after the booking (59-66)
# ---------------------------------------------------------------------------
B = [
    dict(n=59, name="B2B Training (VAT exclusive)", tenancy="multi", booked="Corporate training day",
         price="Net 80000 + 20% VAT = 96000",
         flags="U:slot P:fixed I:none D:fixed L:atcust Y:group Q:approval T:request M:invoice+comm X:vatex",
         config={"booking": {"party": {"mode": "group", "min": 4, "max": 30}},
                 "pricing": {"model": "fixed", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 80000}},
                 "payments": {"flow": "invoice_after"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"}},
                 "capabilities": {"prerequisites": True},
                 "location": {"modes": ["at_customer"], "default": "at_customer"},
                 "prerequisites": [{"key": "po", "kind": "approval", "label": "Purchase order", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 8, "party_size": 12, "duration_minutes": 480}, expect=96000,
         depends=["payments.flow", "tenancy.commission", "prerequisites"],
         limitation="No `tax` block. VAT-exclusive pricing (the norm for B2B) is unreachable: "
                    "the engine quotes the net 80000 and there is nowhere to declare the 16000."),

    dict(n=60, name="Tiered cancellation refunds", tenancy="single", booked="Cottage weekend",
         price="Refund 100% >30d, 50% >7d, 0% after",
         flags="U:room P:unit I:finite D:chosen L:onsite Y:group Q:none T:instant M:prepay X:refundtier",
         config={"booking": {"unitKind": "room", "granularity": "night", "duration": {"mode": "customer_chosen", "minUnits": 2, "maxUnits": 14},
                             "party": {"mode": "group", "min": 1, "max": 6}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False,
                             "rate": {"per": "night", "amountMinorUnits": 12000}},
                 "inventory": {"mode": "finite"}, "capabilities": {"inventory": True},
                 "timing": {"cancellationWindowHours": 168}},
         ctx={"slot_count": 2, "duration_minutes": 2880}, expect=24000,
         depends=["timing.cancellationWindowHours"],
         limitation="Cancellation is a single BINARY cutoff (`cancellationWindowHours`). A graduated "
                    "refund ladder — the standard for accommodation — cannot be declared; there is no "
                    "`refundPolicy[]` and no notion of a partial refund anywhere in the schema."),

    dict(n=61, name="Reschedule-fee physiotherapy", tenancy="single", booked="Appointment with change fee",
         price="4000, +1000 to move inside 24h",
         flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:onsite X:resfee",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 4000}},
                 "payments": {"flow": "pay_on_site"}, "timing": {"cancellationWindowHours": 24}},
         ctx={"slot_count": 1, "duration_minutes": 45}, expect=4000,
         depends=["timing.cancellationWindowHours"],
         limitation="A reschedule inside the cutoff is refused outright; it cannot be ALLOWED-WITH-A-FEE. "
                    "There is no `changeFee` and the reschedule path has no way to add a charge."),

    dict(n=62, name="Gift voucher florist", tenancy="single", booked="Workshop paid by voucher",
         price="6500 workshop, 5000 voucher applied",
         flags="U:class P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay X:voucher",
         config={"booking": {"unitKind": "class_capacity"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 6500}},
                 "capabilities": {"entitlements": True},
                 "entitlements": {"enabled": True, "kind": "pass",
                                  "plans": [{"key": "gift50", "label": "50 gift voucher", "priceMinorUnits": 5000, "cycle": "none", "credits": 1, "appliesToServices": [], "discountBps": 0}]}},
         ctx={"slot_count": 1, "duration_minutes": 120}, expect=1500,
         depends=["entitlements"],
         limitation="`entitlements.plans[]` models credits/memberships but has no monetary balance, so a "
                    "part-paying gift voucher cannot reduce a quote. quote() has no redemption input at all."),

    dict(n=63, name="Split-the-bill supper club", tenancy="single", booked="Seat at a shared table",
         price="Per head 4200, billed per attendee",
         flags="U:seat P:person I:finite D:fixed L:onsite Y:group Q:none T:instant M:split X:splitpay",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 8}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 4200}},
                 "payments": {"flow": "split"}, "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True}},
         ctx={"slot_count": 1, "party_size": 4, "duration_minutes": 180}, expect=16800,
         depends=["payments.flow"],
         limitation="`payments.flow: split` means staged payments by TIME (deposit/balance), not split "
                    "between PEOPLE. Per-attendee billing of one booking has no representation."),

    dict(n=64, name="Deposit forfeited on no-show", tenancy="multi", booked="Tattoo session",
         price="30000, 5000 deposit forfeit on no-show",
         flags="U:staff P:fixed I:none D:variable L:onsite Y:solo Q:waiver T:request M:depbal+comm X:forfeit",
         config={"booking": {"unitKind": "staff", "duration": {"mode": "variable", "minUnits": 1, "maxUnits": 8}},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 30000},
                             "deposit": {"enabled": True, "kind": "flat", "value": 5000, "refundable": False}},
                 "payments": {"flow": "split", "noShowFee": {"enabled": True, "amountMinorUnits": 5000}},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1200, "chargedOn": "completion"}},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "consent", "kind": "waiver", "label": "Consent form", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 4, "duration_minutes": 240}, expect=30000,
         depends=["pricing.deposit", "payments.noShowFee", "prerequisites"]),

    dict(n=65, name="Commission on the net, not the gross", tenancy="multi", booked="Guided hike",
         price="9000 + 500 fee; platform takes 15% of 9000",
         flags="U:class P:person I:none D:fixed L:onsite Y:group Q:waiver T:instant M:prepay+comm X:commbase",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 12}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 4500},
                             "fees": [{"key": "kit", "label": "Kit hire", "kind": "flat", "amountMinorUnits": 500}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "completion"}},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "fitness", "kind": "waiver", "label": "Fitness declaration", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "party_size": 2, "duration_minutes": 360}, expect=9500,
         depends=["tenancy.commission", "pricing.fees"],
         limitation="`commission.rateBps` has no BASE. Whether the platform takes its cut of the net, "
                    "the gross, or excludes pass-through fees is undefined — a material accounting "
                    "ambiguity in every one of the 25 marketplace pivots."),

    dict(n=66, name="Payout schedule to the tenant", tenancy="multi", booked="Event space hire",
         price="120000, tenant paid 7d after completion",
         flags="U:room P:unit I:finite D:chosen L:onsite Y:buyout Q:approval T:request M:invoice+comm X:payout",
         config={"booking": {"unitKind": "room", "duration": {"mode": "customer_chosen", "minUnits": 4, "maxUnits": 24},
                             "party": {"mode": "buyout", "min": 10, "max": 200}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 15000}},
                 "payments": {"flow": "invoice_after"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "insurance", "kind": "credential", "label": "Public liability", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 8, "duration_minutes": 480}, expect=120000,
         depends=["tenancy.commission", "payments.flow", "prerequisites"],
         limitation="Money OUT is unmodelled. `payments.schedule[]` describes what the customer owes and "
                    "when; there is no payout schedule to the tenant, so a marketplace cannot state when "
                    "a business actually gets paid."),
]

EXTENDED = A + B

# ---------------------------------------------------------------------------
# C. Eligibility arithmetic and identity (67-74)
# ---------------------------------------------------------------------------
C = [
    dict(n=67, name="18+ Wine Tasting", tenancy="single", booked="Tasting seat, age gated",
         price="Per person", flags="U:seat P:person I:finite D:fixed L:onsite Y:group Q:id T:instant M:prepay X:age",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 12},
                             "subject": {"enabled": True, "noun": "Guest",
                                         "fields": [{"key": "dob", "label": "Date of birth", "type": "date", "required": True}]}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 5500}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "age", "kind": "id_check", "label": "Over 18", "appliesTo": "subject", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "party_size": 2, "duration_minutes": 120}, expect=11000,
         depends=["prerequisites", "booking.subject"],
         limitation="A prerequisite is a yes/no gate. An age RULE (dob + minAge, evaluated at the booking "
                    "date) cannot be declared — no `minAge`, and metaField `min`/`max` are numeric bounds, "
                    "not date arithmetic."),

    dict(n=68, name="Senior stylist premium", tenancy="multi", booked="Cut with a chosen stylist",
         price="Junior 4000 / senior 7000, same service",
         flags="U:staff P:tiered I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay+comm X:resprice",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 4000},
                             "tiers": [{"key": "senior", "label": "Senior stylist", "amountMinorUnits": 7000, "appliesWhen": {"zone": "senior"}}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1200, "chargedOn": "completion"}}},
         ctx={"slot_count": 1, "duration_minutes": 60, "zone": "senior"}, expect=7000,
         depends=["pricing.tiers", "tenancy.commission"],
         limitation="Priced only by abusing the generic `zone` clause. Pricing belongs to the SERVICE; "
                    "there is no per-RESOURCE price or duration override, so 'this stylist costs more' "
                    "and 'this stylist is slower' are both inexpressible as data."),

    dict(n=69, name="Members-only squash court", tenancy="single", booked="Court, members priced lower",
         price="Guest 2400 / member 1200",
         flags="U:asset P:tiered I:finite D:chosen L:onsite Y:group Q:member T:instant M:prepay X:memberprice",
         config={"booking": {"unitKind": "asset", "party": {"mode": "group", "min": 2, "max": 4},
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 3}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "hour", "amountMinorUnits": 2400},
                             "tiers": [{"key": "member", "label": "Member rate", "amountMinorUnits": 1200, "appliesWhen": {"zone": "member"}}]},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "entitlements": True, "prerequisites": True},
                 "entitlements": {"enabled": True, "kind": "membership",
                                  "plans": [{"key": "full", "label": "Full member", "priceMinorUnits": 45000, "cycle": "annual", "credits": None, "appliesToServices": [], "discountBps": 5000}]},
                 "prerequisites": [{"key": "member", "kind": "membership", "label": "Membership", "appliesTo": "customer", "required": False, "blocksConfirmation": False}]},
         ctx={"slot_count": 1, "duration_minutes": 60, "zone": "member"}, expect=1200,
         depends=["pricing.tiers", "entitlements", "prerequisites"],
         limitation="`entitlements.plans[].discountBps` exists but quote() never reads an entitlement. "
                    "Member pricing works only by hand-passing a `zone`; the declared 5000bps discount "
                    "is inert."),

    dict(n=70, name="Expiring credential kitesurf school", tenancy="single", booked="Lesson requiring a valid cert",
         price="Per hour", flags="U:staff P:hourly I:none D:fixed L:onsite Y:solo Q:member T:instant M:prepay X:expiry",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 6000}},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "iko", "kind": "credential", "label": "IKO Level 2", "appliesTo": "customer", "required": True, "validityDays": 365, "blocksConfirmation": True}],
                 "timing": {"seasons": [{"key": "wind", "label": "Wind season", "startDate": "2027-04-01", "endDate": "2027-10-31"}]}},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=12000,
         depends=["prerequisites", "timing.seasons"]),

    dict(n=71, name="Language-specific tour guide", tenancy="multi", booked="Tour in a chosen language",
         price="Per person", flags="U:class P:person I:none D:fixed L:onsite Y:group Q:none T:instant M:prepay+comm X:locale",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 20}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 3000}},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "booking"}},
                 "location": {"timezone": "Europe/Lisbon"}},
         ctx={"slot_count": 1, "party_size": 3, "duration_minutes": 150}, expect=9000,
         depends=["tenancy.commission"],
         limitation="No locale/language anywhere. `terms`/`copy` are single-language, the frontend "
                    "hardcodes `en-GB` in every Intl formatter, and a resource attribute cannot be made "
                    "filterable — so 'guides who speak German' is neither declarable nor searchable."),

    dict(n=72, name="Accessible-only bookings", tenancy="multi", booked="Step-free room",
         price="Fixed", flags="U:room P:fixed I:finite D:fixed L:onsite Y:solo Q:intake T:instant M:prepay+comm X:a11y",
         config={"booking": {"unitKind": "room"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 8000}},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 800, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "access", "kind": "intake_form", "label": "Access requirements", "appliesTo": "customer", "required": False, "blocksConfirmation": False}],
                 "metaFields": {"resources": [{"key": "step_free", "label": "Step-free", "type": "boolean"}]}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=8000,
         depends=["prerequisites", "metaFields.resources", "inventory.mode"],
         limitation="`metaFields` can DECLARE `step_free` on a resource but nothing can FILTER on it: "
                    "`discovery.facets` is a fixed three-key set (price/distance/rating), so a "
                    "metadata-driven facet is impossible without code."),

    dict(n=73, name="Household account (one payer, many users)", tenancy="single", booked="Swim lessons for 3 children",
         price="Per child per session",
         flags="U:class P:person I:finite D:fixed L:onsite Y:group Q:waiver T:instant M:invoice X:household",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 4},
                             "subject": {"enabled": True, "noun": "Child",
                                         "fields": [{"key": "name", "label": "Name", "type": "text", "required": True}]}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 1800}},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "medical", "kind": "waiver", "label": "Medical form", "appliesTo": "subject", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "party_size": 3, "duration_minutes": 45}, expect=5400,
         depends=["booking.subject", "payments.billingCycle", "prerequisites"],
         limitation="`booking.subject` is ONE subject per booking. Three children each needing their own "
                    "waiver and their own seat cannot be modelled — party size is a number, not a list of "
                    "identified subjects."),

    dict(n=74, name="Corporate account with negotiated rate", tenancy="multi", booked="Desk block on contract",
         price="List 3000, contract 2100",
         flags="U:seat P:tiered I:finite D:chosen L:onsite Y:group Q:approval T:instant M:invoice+comm X:contract",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 20},
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 20}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "day", "amountMinorUnits": 3000},
                             "tiers": [{"key": "contract", "label": "Contract rate", "amountMinorUnits": 2100, "appliesWhen": {"zone": "acme"}}]},
                 "payments": {"flow": "invoice_after", "billingCycle": "monthly"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 900, "chargedOn": "completion"}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "account", "kind": "approval", "label": "Corporate account", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "duration_minutes": 1440, "zone": "acme"}, expect=2100,
         depends=["pricing.tiers", "payments.billingCycle", "prerequisites"],
         limitation="Customer-specific negotiated rates work only by smuggling an account key through "
                    "`zone`. There is no customer-segment concept, so the tier list would have to grow one "
                    "entry per contract and every customer could self-select any of them."),
]

EXTENDED += C

# ---------------------------------------------------------------------------
# D. Composition — bookings made of other things (75-84)
# ---------------------------------------------------------------------------
D = [
    dict(n=75, name="Spa Day Package", tenancy="single", booked="Massage + facial + lunch, one booking",
         price="Bundle 15000 (list 18500)",
         flags="U:slot P:tiered I:none D:fixed L:onsite Y:solo Q:intake T:instant M:prepay X:bundle",
         config={"pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 15000}},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "health", "kind": "intake_form", "label": "Health questionnaire", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 6, "duration_minutes": 360}, expect=15000,
         depends=["prerequisites"],
         limitation="A bundle spanning three DIFFERENT services in one booking is inexpressible: a booking "
                    "is `service_id` + contiguous slots on ONE resource. The 15000 is a hand-entered flat "
                    "price with no link to its components."),

    dict(n=76, name="Room requiring a projector", tenancy="multi", booked="Meeting room + dependent kit",
         price="Room 4000/h, projector must be free too",
         flags="U:room P:hourly I:finite D:chosen L:onsite Y:group Q:none T:instant M:prepay+comm X:depres",
         config={"booking": {"unitKind": "room", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 8},
                             "party": {"mode": "group", "min": 1, "max": 20, "matchResourceCapacity": True},
                             "options": [{"key": "projector", "label": "Projector", "type": "boolean",
                                          "choices": [{"key": "yes", "label": "With projector", "priceMinorUnits": 1500, "requires": []}]}]},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 4000}},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 700, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True}},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=8000,
         depends=["booking.options", "booking.party.matchResourceCapacity", "inventory.mode"],
         limitation="`booking.options[]` can add a PRICE but cannot reserve a second resource. A booking "
                    "that consumes room AND projector capacity simultaneously has no representation — "
                    "`booking_slots` all belong to one resource."),

    dict(n=77, name="Two-person massage (paired staff)", tenancy="single", booked="Couples treatment, 2 therapists",
         price="Per person 7000, both therapists must be free",
         flags="U:staff P:person I:none D:fixed L:onsite Y:group Q:none T:instant M:prepay X:paired",
         config={"booking": {"unitKind": "staff", "party": {"mode": "group", "min": 2, "max": 2}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 7000}}},
         ctx={"slot_count": 1, "party_size": 2, "duration_minutes": 60}, expect=14000,
         depends=["booking.party.min", "booking.party.mode"],
         limitation="Requires TWO resources held for the same slot. The engine holds one resource per "
                    "booking, so a paired-staff treatment can only be faked with a composite resource."),

    dict(n=78, name="Airport transfer (A to B)", tenancy="multi", booked="Journey with two endpoints",
         price="Per km, 45km", flags="U:slot P:unit I:none D:variable L:delivery Y:group Q:none T:instant M:prepay+comm X:twopoint",
         config={"booking": {"duration": {"mode": "variable", "minUnits": 1, "maxUnits": 4},
                             "party": {"mode": "group", "min": 1, "max": 8}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False,
                             "rate": {"per": "unit", "amountMinorUnits": 180}},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "completion"}},
                 "location": {"modes": ["delivery"], "default": "delivery",
                              "serviceArea": {"radiusKm": 80, "travelBufferMinutes": 30, "feeBands": []}}},
         ctx={"slot_count": 1, "unit_count": 45, "party_size": 3, "duration_minutes": 60}, expect=8100,
         depends=["location.serviceArea", "tenancy.commission"],
         limitation="`location` describes ONE place. A journey has an origin and a destination; there is "
                    "nowhere to put the second, and `serviceArea.radiusKm` is a circle around a single point."),

    dict(n=79, name="Multi-day festival pass", tenancy="multi", booked="3-day pass across many stages",
         price="Pass 24000 (day 9500)",
         flags="U:seat P:tiered I:finite D:chosen L:onsite Y:group Q:none T:instant M:prepay+comm X:pass",
         config={"booking": {"unitKind": "seat", "granularity": "day",
                             "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 3},
                             "party": {"mode": "group", "min": 1, "max": 6}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "day", "amountMinorUnits": 9500},
                             "tiers": [{"key": "full", "label": "3-day pass", "amountMinorUnits": 8000, "appliesWhen": {"partySize": {"min": 1}}}]},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 600, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True}},
         ctx={"slot_count": 3, "duration_minutes": 4320}, expect=24000,
         depends=["pricing.tiers", "inventory.mode"]),

    dict(n=80, name="Sequential course (8 weeks, one enrolment)", tenancy="single", booked="Enrol once, attend 8 sessions",
         price="Course 32000", flags="U:class P:fixed I:finite D:fixed L:onsite Y:solo Q:none T:instant M:prepay X:course",
         config={"booking": {"unitKind": "class_capacity",
                             "sequence": {"enabled": True, "steps": 8, "minGapHours": 144, "maxGapHours": 200}},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 32000}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True, "recurrence": True},
                 "recurrence": {"enabled": True, "patterns": ["weekly"], "maxOccurrences": 8}},
         ctx={"slot_count": 1, "duration_minutes": 90}, expect=32000,
         depends=["booking.sequence", "recurrence", "inventory.mode"]),

    dict(n=81, name="Waiting-list-only allotment of scarce slots", tenancy="single", booked="Ballot for a scarce slot",
         price="Free ballot entry", flags="U:slot P:free I:finite D:fixed L:onsite Y:solo Q:approval T:waitlist M:none X:ballot",
         config={"pricing": {"model": "free", "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"}, "inventory": {"mode": "finite"},
                 "capabilities": {"payments": False, "inventory": True, "waitlist": True, "prerequisites": True},
                 "prerequisites": [{"key": "eligible", "kind": "approval", "label": "Eligibility", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"waitlist": {"enabled": True, "autoPromote": False, "maxPerSlot": 500}}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=0,
         depends=["timing.waitlist", "prerequisites", "capabilities"],
         limitation="A waitlist is FIFO by construction (`autoPromote`). A ballot/lottery allocation — "
                    "random or weighted draw among applicants — has no representation."),

    dict(n=82, name="Overnight shift rota", tenancy="multi", booked="22:00-06:00 shift crossing midnight",
         price="Per hour, night premium",
         flags="U:staff P:tiered I:none D:chosen L:onsite Y:solo Q:id T:request M:invoice+comm X:midnight",
         config={"booking": {"unitKind": "staff", "duration": {"mode": "customer_chosen", "minUnits": 4, "maxUnits": 12}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "hour", "amountMinorUnits": 1800},
                             "tiers": [{"key": "night", "label": "Night rate", "amountMinorUnits": 2400,
                                        "appliesWhen": {"timeOfDay": {"from": "22:00", "to": "06:00"}}}]},
                 "payments": {"flow": "invoice_after"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "completion"}},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "dbs", "kind": "id_check", "label": "Background check", "appliesTo": "tenant", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 8, "duration_minutes": 480, "start_local": datetime(2026, 8, 18, 22, 0)}, expect=19200,
         depends=["pricing.tiers", "prerequisites", "tenancy.commission"]),

    dict(n=83, name="Happy-hour crossing the boundary", tenancy="single", booked="Booking that starts in one band, ends in another",
         price="17:00-19:00 spanning an 18:00 price change",
         flags="U:asset P:tiered I:none D:chosen L:onsite Y:group Q:none T:instant M:onsite X:spanband",
         config={"booking": {"unitKind": "asset", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 6},
                             "party": {"mode": "group", "min": 1, "max": 8}},
                 "pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "hour", "amountMinorUnits": 3000},
                             "tiers": [{"key": "happy", "label": "Happy hour", "amountMinorUnits": 1500,
                                        "appliesWhen": {"timeOfDay": {"from": "17:00", "to": "18:00"}}}]},
                 "payments": {"flow": "pay_on_site"}},
         ctx={"slot_count": 2, "duration_minutes": 120, "start_local": datetime(2026, 8, 18, 17, 0)}, expect=4500,
         depends=["pricing.tiers"],
         limitation="Tier matching uses the START time only, so a 17:00-19:00 booking is billed entirely "
                    "at the happy-hour rate (3000) instead of 1x1500 + 1x3000 = 4500. Time-banded pricing "
                    "cannot SPLIT a booking across bands — a real mispricing, not just a missing feature."),

    dict(n=84, name="Resource swap mid-booking", tenancy="multi", booked="Long hire moving between units",
         price="Per day", flags="U:asset P:unit I:serial D:chosen L:pickup Y:solo Q:id T:instant M:prepay+comm X:swap",
         config={"booking": {"unitKind": "asset", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 30}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False, "rate": {"per": "day", "amountMinorUnits": 5000}},
                 "inventory": {"mode": "serialised"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1200, "chargedOn": "completion"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["pickup"], "default": "pickup"},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "ID", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 5, "duration_minutes": 7200}, expect=25000,
         depends=["inventory.mode", "prerequisites", "tenancy.commission"],
         limitation="`_resolve_selection` requires every slot in a booking to share ONE resource. A 5-day "
                    "hire that swaps units on day 3 (routine in fleet operations) cannot be one booking."),
]

EXTENDED += D

# ---------------------------------------------------------------------------
# E. Capacity, scheduling shapes and operations (85-100)
# ---------------------------------------------------------------------------
E = [
    dict(n=85, name="Ferry with vehicle decks", tenancy="multi", booked="Two capacity pools on one sailing",
         price="Foot 1200/pax, car 4500",
         flags="U:seat P:person I:finite D:fixed L:onsite Y:group Q:id T:instant M:prepay+comm X:multipool",
         config={"booking": {"unitKind": "seat", "party": {"mode": "group", "min": 1, "max": 9}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 1200}},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 500, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "Passenger ID", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "party_size": 3, "duration_minutes": 240}, expect=3600,
         depends=["inventory.mode", "prerequisites"],
         limitation="A slot has ONE `capacity` integer. A sailing with independent passenger and vehicle "
                    "pools (and a car consuming both) needs multi-dimensional capacity — inexpressible."),

    dict(n=86, name="Restaurant turn times by daypart", tenancy="single", booked="Table, 90min dinner / 60min lunch",
         price="Free booking", flags="U:asset P:free I:finite D:fixed L:onsite Y:group Q:none T:instant M:none X:turntime",
         config={"booking": {"unitKind": "asset", "party": {"mode": "group", "min": 1, "max": 8, "matchResourceCapacity": True}},
                 "pricing": {"model": "free", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 0}},
                 "payments": {"flow": "none"}, "inventory": {"mode": "finite"},
                 "capabilities": {"payments": False, "inventory": True}},
         ctx={"slot_count": 1, "duration_minutes": 90}, expect=0,
         depends=["booking.party.matchResourceCapacity", "inventory.mode"],
         limitation="`slotDurationMinutes` is one number per service. A turn time that differs by daypart "
                    "(60 at lunch, 90 at dinner) cannot be declared without splitting into two services."),

    dict(n=87, name="Cleaner's travel time between jobs", tenancy="multi", booked="Back-to-back at-customer jobs",
         price="Per hour", flags="U:staff P:hourly I:none D:chosen L:atcust Y:solo Q:none T:instant M:invoice+comm X:travelbuf",
         config={"booking": {"unitKind": "staff", "duration": {"mode": "customer_chosen", "minUnits": 2, "maxUnits": 6}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 2500}},
                 "payments": {"flow": "invoice_after"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "completion"}},
                 "location": {"modes": ["at_customer"], "default": "at_customer",
                              "serviceArea": {"radiusKm": 25, "travelBufferMinutes": 45, "feeBands": []}},
                 "timing": {"bufferMinutes": 45}},
         ctx={"slot_count": 3, "duration_minutes": 180}, expect=7500,
         depends=["location.serviceArea", "timing.bufferMinutes", "tenancy.commission"],
         limitation="`bufferMinutes` is a FIXED pad applied at slot creation. Travel time between two "
                    "at-customer jobs depends on the distance between them — a dynamic buffer the schema "
                    "cannot express."),

    dict(n=88, name="Peak-season capacity increase", tenancy="single", booked="More seats in summer",
         price="Per person", flags="U:class P:person I:finite D:fixed L:onsite Y:group Q:none T:season M:prepay X:varcap",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "group", "min": 1, "max": 30}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 2000}},
                 "inventory": {"mode": "finite"},
                 "capabilities": {"inventory": True},
                 "timing": {"seasons": [{"key": "high", "label": "High season", "startDate": "2027-06-01", "endDate": "2027-09-01"}]}},
         ctx={"slot_count": 1, "party_size": 4, "duration_minutes": 120}, expect=8000,
         depends=["timing.seasons", "inventory.mode"],
         limitation="`timing.seasons[]` can gate availability on/off but carries no OVERRIDES. A season "
                    "that changes capacity (or price, or duration) has nowhere to say so — seasons are a "
                    "boolean window, not a settings layer."),

    dict(n=89, name="Last-minute discount", tenancy="multi", booked="Fill empty slots cheaply",
         price="4000 normally, 2000 inside 24h",
         flags="U:slot P:tiered I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay+comm X:lastmin",
         config={"pricing": {"model": "tiered", "chargePerPerson": False,
                             "rate": {"per": "booking", "amountMinorUnits": 4000},
                             "tiers": [{"key": "lastmin", "label": "Last minute", "amountMinorUnits": 2000, "appliesWhen": {"zone": "lastmin"}}]},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1200, "chargedOn": "booking"}}},
         ctx={"slot_count": 1, "duration_minutes": 60, "zone": "lastmin"}, expect=2000,
         depends=["pricing.tiers", "tenancy.commission"],
         limitation="No `appliesWhen` clause reads the gap between NOW and the slot START. Last-minute "
                    "(and its mirror, early-booking) discounts — a staple of yield management — can only "
                    "be faked by passing a `zone` the customer could choose themselves."),

    dict(n=90, name="Overbooking-tolerant clinic", tenancy="single", booked="Deliberate 10% overbook",
         price="Fixed", flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:intake T:instant M:invoice X:overbook",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 3000}},
                 "payments": {"flow": "invoice_after"},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "intake", "kind": "intake_form", "label": "Intake", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 1, "duration_minutes": 20}, expect=3000,
         depends=["prerequisites", "payments.flow"],
         limitation="Capacity is a hard ceiling (`available_count >= party`). Deliberate overbooking — "
                    "standard where no-shows are predictable — needs an overbook allowance the schema "
                    "does not have."),

    dict(n=91, name="Opening hours per weekday", tenancy="single", booked="Closed Mondays, late Thursdays",
         price="Fixed", flags="U:staff P:fixed I:none D:fixed L:onsite Y:solo Q:none T:blackout M:onsite X:hours",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 2800}},
                 "payments": {"flow": "pay_on_site"},
                 "timing": {"blackouts": [{"key": "aug", "label": "Summer close", "startDate": "2027-08-01", "endDate": "2027-08-14"}]}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=2800,
         depends=["timing.blackouts"],
         limitation="`blackouts[]` are DATE RANGES. Recurring weekly opening hours (closed Mondays, open "
                    "late Thursdays) — the single most common scheduling fact about any business — cannot "
                    "be declared; they exist only implicitly in which slots got seeded."),

    dict(n=92, name="Two-week notice with a hard horizon", tenancy="single", booked="Long-notice consultation",
         price="Fixed", flags="U:staff P:fixed I:none D:fixed L:remote Y:solo Q:approval T:request M:prepay X:horizon",
         config={"booking": {"unitKind": "staff"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 9500}},
                 "location": {"modes": ["remote"], "default": "remote"},
                 "capabilities": {"prerequisites": True},
                 "prerequisites": [{"key": "docs", "kind": "approval", "label": "Documents reviewed", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve", "leadTimeMinutes": 20160, "advanceBookingWindowDays": 90}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=9500,
         depends=["timing.leadTimeMinutes", "timing.advanceBookingWindowDays", "prerequisites"]),

    dict(n=93, name="Per-tenant commission override", tenancy="multi", booked="Anchor tenant on a better rate",
         price="Fixed 5000; platform takes 5% not 15%",
         flags="U:slot P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay+comm X:commoverride",
         config={"pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 5000}},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1500, "chargedOn": "booking"}}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=5000,
         depends=["tenancy.commission"],
         limitation="`tenancy` is not overridable per service — now DELIBERATELY so, and enforced: "
                    "the write path rejects it, because a tenant setting its own `commission.rateBps` "
                    "would be privilege escalation. Negotiating a different rate with an anchor tenant is "
                    "therefore still a code change; doing it properly needs a platform-side per-tenant "
                    "commission table, not a config override."),

    dict(n=94, name="Tenant-set cancellation policy", tenancy="multi", booked="Each business sets its own window",
         price="Per hour", flags="U:room P:hourly I:finite D:chosen L:onsite Y:group Q:none T:instant M:prepay+comm X:tenantpolicy",
         config={"booking": {"unitKind": "room", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 8},
                             "party": {"mode": "group", "min": 1, "max": 12}},
                 "pricing": {"model": "per_hour", "chargePerPerson": False, "rate": {"per": "hour", "amountMinorUnits": 3500}},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 1000, "chargedOn": "booking"}},
                 "capabilities": {"inventory": True},
                 "timing": {"cancellationWindowHours": 48}},
         ctx={"slot_count": 2, "duration_minutes": 120}, expect=7000,
         depends=["timing.cancellationWindowHours", "inventory.mode", "tenancy.commission"]),

    dict(n=95, name="Zero-duration instant service", tenancy="single", booked="Drop-off, no time span",
         price="Flat 900", flags="U:slot P:fixed I:none D:fixed L:pickup Y:solo Q:none T:instant M:onsite X:zerodur",
         config={"pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 900}},
                 "payments": {"flow": "pay_on_site"},
                 "location": {"modes": ["pickup"], "default": "pickup"}},
         ctx={"slot_count": 1, "duration_minutes": 0}, expect=900,
         depends=["pricing.rate"]),

    dict(n=96, name="Very large party buyout", tenancy="multi", booked="Stadium concourse, 5000 guests",
         price="Per person 250", flags="U:class P:person I:finite D:fixed L:onsite Y:buyout Q:approval T:request M:invoice+comm X:bigparty",
         config={"booking": {"unitKind": "class_capacity", "party": {"mode": "buyout", "min": 500, "max": 8000}},
                 "pricing": {"model": "per_person", "rate": {"per": "person", "amountMinorUnits": 250}},
                 "payments": {"flow": "invoice_after"},
                 "inventory": {"mode": "finite"},
                 "tenancy": {"commission": {"enabled": True, "rateBps": 400, "chargedOn": "completion"}},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "prerequisites": [{"key": "safety", "kind": "approval", "label": "Safety plan", "appliesTo": "customer", "required": True, "blocksConfirmation": True}],
                 "timing": {"confirmation": "request_approve"}},
         ctx={"slot_count": 1, "party_size": 5000, "duration_minutes": 300}, expect=1250000,
         depends=["booking.party.mode", "prerequisites", "inventory.mode"]),

    dict(n=97, name="Free cancellation, paid rebooking", tenancy="single", booked="Flexible fare",
         price="Fixed 11000", flags="U:seat P:fixed I:finite D:fixed L:onsite Y:solo Q:none T:instant M:prepay X:flexfare",
         config={"booking": {"unitKind": "seat"},
                 "pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 11000}},
                 "inventory": {"mode": "finite"}, "capabilities": {"inventory": True},
                 "timing": {"cancellationWindowHours": 0}},
         ctx={"slot_count": 1, "duration_minutes": 120}, expect=11000,
         depends=["timing.cancellationWindowHours", "inventory.mode"],
         limitation="One `cancellationCutoffHours` governs BOTH cancel and reschedule (`within_cutoff` is "
                    "shared). A fare that is freely cancellable but charges to rebook — or the reverse — "
                    "cannot be expressed."),

    dict(n=98, name="Deposit that is not part of the price", tenancy="single", booked="Refundable damage bond",
         price="Hire 20000 + 30000 bond held separately",
         flags="U:asset P:unit I:rentable D:chosen L:pickup Y:solo Q:id T:instant M:depbal X:bond",
         config={"booking": {"unitKind": "asset", "granularity": "day", "duration": {"mode": "customer_chosen", "minUnits": 1, "maxUnits": 7}},
                 "pricing": {"model": "per_unit", "chargePerPerson": False,
                             "rate": {"per": "day", "amountMinorUnits": 10000},
                             "deposit": {"enabled": True, "kind": "flat", "value": 30000, "refundable": True}},
                 "payments": {"flow": "split"},
                 "inventory": {"mode": "rentable", "returnRequired": True, "loanPeriodHours": 168},
                 "capabilities": {"inventory": True, "prerequisites": True},
                 "location": {"modes": ["pickup"], "default": "pickup"},
                 "prerequisites": [{"key": "id", "kind": "id_check", "label": "ID", "appliesTo": "customer", "required": True, "blocksConfirmation": True}]},
         ctx={"slot_count": 2, "duration_minutes": 2880}, expect=20000, expect_deposit=30000,
         depends=["pricing.deposit", "inventory.returnRequired", "prerequisites"],
         ),  # FIXED by this exercise: a refundable bond is a hold, not a prepayment,
             # so it is no longer clamped to the total. Non-refundable still is (#55).

    dict(n=99, name="Cross-border marketplace, mixed currencies", tenancy="multi", booked="Tenants price in their own currency",
         price="This tenant in CHF", flags="U:slot P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay+comm X:multicur",
         config={"pricing": {"model": "fixed", "chargePerPerson": False, "currency": "CHF",
                             "rate": {"per": "booking", "amountMinorUnits": 8500}},
                 "tenancy": {"selfOnboarding": True, "commission": {"enabled": True, "rateBps": 1000, "chargedOn": "booking"}},
                 "location": {"timezone": "Europe/Zurich"}},
         ctx={"slot_count": 1, "duration_minutes": 60}, expect=8500,
         depends=["pricing.currency", "tenancy.commission"],
         limitation="Per-tenant currency works, but nothing aggregates across currencies: provider "
                    "`priceFromMinorUnits` picks a min across services regardless of currency, and search "
                    "price sort/filter compares raw integers — so CHF 85 sorts against HUF 8500."),

    dict(n=100, name="Same-day pivot: config swap under load", tenancy="single", booked="The 16:00 pivot itself",
         price="Whatever the new config says",
         flags="U:slot P:fixed I:none D:fixed L:onsite Y:solo Q:none T:instant M:prepay X:pivotswap",
         config={"pricing": {"model": "fixed", "chargePerPerson": False, "rate": {"per": "booking", "amountMinorUnits": 4200}},
                 "terms": {"resource": "Bay", "resources": "Bays", "slot": "Window", "slots": "Windows"},
                 "copy": {"landingTitle": "Book a Bay"}},
         ctx={"slot_count": 1, "duration_minutes": 30}, expect=4200,
         depends=["terms.slot", "pricing.rate"]),
]

EXTENDED += E
