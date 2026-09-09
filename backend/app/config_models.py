# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pydantic models describing `domain.config.json`, the shape of the whole v2
tree, in one place.

Why this file exists
--------------------
The config shape used to be written three times: `config_schema.DEFAULTS` (a
dict literal), `config_schema.validate()` (imperative checks) and the
hand-written TypeScript in `frontend/src/api/index.ts`. Nothing linked them, and
they had already drifted, the backend declares 17 `terms` keys, the frontend
type declared 13, and `scripts/generate_pivots.py` writes three of the missing
ones into all 100 shipped pivots.

These models are the single source of truth. From them:

  * `scripts/gen_config_schema.py` writes `domain.config.schema.json`, which
    gives the pivot file editor autocomplete and inline docs;
  * `frontend` generates `src/api/config.generated.ts`, so the TS types can no
    longer drift from the backend.

What this file is NOT (yet)
---------------------------
It does not validate anything in production. `config_schema.validate()` is still
the validator, and it stays that way until an equivalence harness proves these
models emit byte-identical problem strings, the strings are a production
contract, not just a test one (`config_schema.validate_overrides` set-diffs them
to decide which per-service override blocks survive, and a wrongly-dropped block
silently reprices a service). See `test_config_models.py` for the golden test
that keeps the models and `DEFAULTS` in lockstep in the meantime.

Conventions
-----------
* **Field names are camelCase**, matching the JSON exactly, so the model dumps
  to the config verbatim and the generated schema/TS use the names the file
  uses. The single exception is `copy_`, aliased to `copy`: the bare name
  shadows `BaseModel.copy` and pydantic warns at import. Dump with
  `by_alias=True` (`config_dump()` below does).
* **Numbers are `Number`** (`StrictInt | StrictFloat`), mirroring
  `config_schema._int`, which accepts an int or a float and explicitly rejects
  `bool`. Strict types matter here: lax mode would accept `"30"` for an int and
  `1` for a bool, silently widening the schema in a way no test would catch.
* **Enums are `Literal`**, and `test_config_models.py` asserts each one covers
  exactly the matching frozenset in `config_schema`, so the two cannot drift.
* **Leaf item models allow extra keys.** Real configs carry presentational
  fields the engine ignores (`label`, `helpText`, `appliesWhen`); rejecting them
  would fail 100 shipped pivots.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

CONFIG_VERSION = 2

# `config_schema._int` takes an int or a float and rejects bool. Strict members
# preserve both halves of that: no "30"-as-int, no True-as-1.
Number = StrictInt | StrictFloat

# -- enum vocabularies ---------------------------------------------------
#
# The canonical form. `config_schema` keeps the equivalent frozensets for the
# current validator; a test asserts the two agree so neither can drift.

UnitKind = Literal[
    "time_slot", "staff", "asset", "seat", "room",
    "class_capacity", "stock_item", "subscription_slot", "project",
]
Granularity = Literal["minute", "hour", "day", "night", "week", "month", "none"]
DurationMode = Literal["fixed", "variable", "customer_chosen", "open_ended"]
PartyMode = Literal["individual", "group", "buyout"]
PricingModel = Literal[
    "fixed", "per_hour", "per_person", "per_unit", "tiered",
    "quote", "deposit_balance", "subscription", "free",
]
RatePeriod = Literal[
    "booking", "slot", "hour", "day", "night", "week", "month", "person", "unit"
]
InventoryMode = Literal["none", "finite", "rentable", "consumable", "serialised"]
LocationMode = Literal["on_site", "at_customer", "remote", "delivery", "pickup"]
PrereqKind = Literal[
    "id_check", "licence", "intake_form", "waiver", "membership", "approval", "credential"
]
PrereqTarget = Literal["customer", "tenant", "subject"]
ConfirmationMode = Literal["instant", "request_approve"]
PaymentFlow = Literal["prepay", "pay_on_site", "invoice_after", "split", "none"]
Payer = Literal["customer", "third_party"]
BillingCycle = Literal["none", "weekly", "monthly", "annual"]
EntitlementKind = Literal["none", "credits", "membership", "pass"]
DiscoveryMode = Literal["browse", "reverse"]
TenancyMode = Literal["single", "multi"]
MetaFieldType = Literal["text", "number", "boolean", "date", "select", "file"]
FeeKind = Literal["flat", "percent", "distanceBand"]
DepositKind = Literal["percent", "flat"]
OptionType = Literal["boolean", "select"]
RecurrencePattern = Literal["weekly", "biweekly", "monthly"]


class _Block(BaseModel):
    """A config block. Unknown keys are dropped, matching `check_shape`, which
    only inspects keys `DEFAULTS` declares.

    The published schema says `additionalProperties: false` even though runtime
    validation only *ignores* extras. That is deliberate and is the more useful
    of the two behaviours to surface in an editor: a key the engine drops
    silently is exactly the typo a pivot author needs told about, and without it
    the generated TypeScript grows an `[k: string]: unknown` index signature
    that collapses `keyof Terms` to `string`, which is the drift these types
    exist to prevent."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={"additionalProperties": False},
    )


class _Item(BaseModel):
    """A list entry. Extra keys are KEPT: real configs carry presentational
    fields the engine never reads (`label`, `helpText`, `appliesWhen`,
    `validFrom`), and dropping them would silently rewrite a pivot file."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# -- tenancy -------------------------------------------------------------


class Credential(_Item):
    key: str
    label: str | None = None
    expires: StrictBool | None = None


class TenantVerification(_Block):
    required: StrictBool = False
    credentials: list[Credential] = Field(default_factory=list)


class Commission(_Block):
    enabled: StrictBool = False
    rateBps: Number = 0
    chargedOn: str = "completion"


class Tenancy(_Block):
    mode: TenancyMode = "multi"
    providerCode: str | None = Field(
        default=None,
        description="Required when mode is 'single', how the app resolves its one business.",
    )
    selfOnboarding: StrictBool | None = Field(
        default=None,
        description="Defaults to (mode == 'multi') at load: a marketplace onboards businesses, a single-business site does not.",
    )
    tenantVerification: TenantVerification = Field(default_factory=TenantVerification)
    commission: Commission = Field(default_factory=Commission)


# -- capabilities --------------------------------------------------------


class Capabilities(_Block):
    """The on/off spine. A false capability means the UI hides the surface AND
    the backend refuses the write, not one without the other."""

    payments: StrictBool = True
    inventory: StrictBool = False
    waitlist: StrictBool = False
    quotes: StrictBool = False
    recurrence: StrictBool = False
    prerequisites: StrictBool = False
    entitlements: StrictBool = False
    cart: StrictBool = False
    reviews: StrictBool = True
    follows: StrictBool = True


# -- booking -------------------------------------------------------------


class Duration(_Block):
    mode: DurationMode = "fixed"
    minUnits: Number = 1
    maxUnits: Number = 1
    incrementUnits: Number = 1


class CompositionBand(_Item):
    key: str
    label: str | None = None
    priceFactor: Number | None = None


class Party(_Block):
    mode: PartyMode = "individual"
    min: Number = 1
    max: Number | None = Field(
        default=None, description="null means the resource's own capacity is the ceiling."
    )
    composition: list[CompositionBand] | None = Field(
        default=None, description="Age bands and similar, each with its own priceFactor."
    )
    matchResourceCapacity: StrictBool = False


class Sequence(_Block):
    enabled: StrictBool = False
    steps: Number = 1
    minGapHours: Number = 0
    maxGapHours: Number | None = None


class SubjectField(_Item):
    key: str
    label: str | None = None
    type: MetaFieldType | None = None
    required: StrictBool | None = None
    options: list[str] | None = None
    helpText: str | None = None


class Subject(_Block):
    enabled: StrictBool = False
    noun: str = "Subject"
    fields: list[SubjectField] = Field(default_factory=list)


class OptionChoice(_Item):
    key: str
    label: str | None = None
    priceMinorUnits: Number | None = None
    requires: list[str] | None = None


class BookingOption(_Item):
    key: str
    type: OptionType = "boolean"
    label: str | None = None
    priceMinorUnits: Number | None = None
    choices: list[OptionChoice] | None = Field(
        default=None, description="Required when type is 'select'."
    )
    helpText: str | None = None


class Booking(_Block):
    unitKind: UnitKind = "time_slot"
    granularity: Granularity = "minute"
    duration: Duration = Field(default_factory=Duration)
    party: Party = Field(default_factory=Party)
    sequence: Sequence = Field(default_factory=Sequence)
    subject: Subject = Field(default_factory=Subject)
    options: list[BookingOption] = Field(default_factory=list)


# -- pricing -------------------------------------------------------------


class Rate(_Block):
    per: RatePeriod = "slot"
    amountMinorUnits: Number = 0


class Tier(_Item):
    key: str
    amountMinorUnits: Number
    label: str | None = None
    quantityCap: Number | None = None
    appliesWhen: dict[str, Any] | None = None
    validFrom: str | None = None
    validUntil: str | None = None


class DistanceBand(_Item):
    maxKm: Number | None = None
    feeMinorUnits: Number = 0


class Fee(_Item):
    key: str | None = None
    kind: FeeKind = "flat"
    label: str | None = None
    amountMinorUnits: Number | None = Field(default=None, description="For kind 'flat'.")
    rateBps: Number | None = Field(default=None, description="For kind 'percent'.")
    bands: list[DistanceBand] | None = Field(
        default=None, description="Required, and non-empty, for kind 'distanceBand'."
    )
    appliesWhen: dict[str, Any] | None = None


class Caps(_Block):
    perBookingMinorUnits: Number | None = None
    perDayMinorUnits: Number | None = Field(
        default=None,
        description="Declared but NOT enforced: it needs the customer's other bookings that day, which is a query, not arithmetic.",
    )


class Deposit(_Block):
    enabled: StrictBool = False
    kind: DepositKind = "percent"
    value: Number = 0
    refundable: StrictBool = True


class Pricing(_Block):
    model: PricingModel = "fixed"
    currency: str = Field(default="EUR", description="A 3-letter ISO 4217 code.")
    currencyExponent: Number = 2
    rate: Rate = Field(default_factory=Rate)
    secondaryRate: Rate | None = None
    tiers: list[Tier] = Field(default_factory=list)
    chargePerPerson: StrictBool = Field(
        default=True,
        description="True reproduces the v1 formula (price x slots x party). False where the party shares one unit, a tennis court costs the same for 2 or 4.",
    )
    caps: Caps = Field(default_factory=Caps)
    fees: list[Fee] = Field(default_factory=list)
    deposit: Deposit = Field(default_factory=Deposit)


# -- payments ------------------------------------------------------------


class ScheduleStep(_Item):
    key: str
    kind: DepositKind = "percent"
    value: Number = 0
    label: str | None = None
    relativeTo: str | None = None
    dueOffsetDays: Number | None = None
    dueOffsetHours: Number | None = None


class NoShowFee(_Block):
    enabled: StrictBool = False
    amountMinorUnits: Number = 0


class Payments(_Block):
    flow: PaymentFlow = "prepay"
    payer: Payer = "customer"
    schedule: list[ScheduleStep] = Field(default_factory=list)
    billingCycle: BillingCycle = "none"
    noShowFee: NoShowFee = Field(
        default_factory=NoShowFee,
        description="NOT YET ENFORCED, needs the payments layer (no payments table exists).",
    )
    usageMetered: StrictBool = False
    adapter: str = Field(
        default="manual",
        description="No PSP exists in this repo. 'manual' = the owner marks a booking paid.",
    )


# -- inventory -----------------------------------------------------------


class Inventory(_Block):
    mode: InventoryMode = "none"
    reservationWindowMinutes: Number = 15
    loanPeriodHours: Number | None = None
    returnRequired: StrictBool = False
    overdueFeePerDayMinorUnits: Number = 0
    restockCycle: str = "none"
    ratioConstraint: dict[str, Any] | None = None


# -- location ------------------------------------------------------------


class Origin(_Item):
    city: str | None = None
    lat: Number | None = None
    lng: Number | None = None


class ServiceArea(_Block):
    radiusKm: Number | None = None
    travelBufferMinutes: Number = 0
    feeBands: list[DistanceBand] = Field(default_factory=list)


class Remote(_Block):
    meetingLinkMode: str = "none"


class Fulfilment(_Block):
    windowMinutes: Number = 60
    cutoffHoursBefore: Number = 0


class Location(_Block):
    modes: list[LocationMode] = Field(default_factory=lambda: ["on_site"])
    default: LocationMode = "on_site"
    timezone: str = Field(
        default="UTC",
        description="The business's own IANA timezone. Absent in v1, which is why an anonymous visitor always saw availability grouped in UTC.",
    )
    distanceUnit: str = "km"
    origin: Origin | None = Field(default=None, description="The distance-from point.")
    serviceArea: ServiceArea = Field(default_factory=ServiceArea)
    remote: Remote = Field(default_factory=Remote)
    fulfilment: Fulfilment = Field(default_factory=Fulfilment)


# -- prerequisites -------------------------------------------------------


class PrereqField(_Item):
    key: str
    label: str | None = None
    type: MetaFieldType | None = None
    required: StrictBool | None = None


class Prerequisite(_Item):
    key: str
    kind: PrereqKind
    appliesTo: PrereqTarget = "customer"
    label: str | None = None
    required: StrictBool | None = None
    blocksConfirmation: StrictBool | None = None
    validityDays: Number | None = None
    verifier: str | None = None
    fields: list[PrereqField] | None = None


# -- timing --------------------------------------------------------------


class Waitlist(_Block):
    enabled: StrictBool = False
    autoPromote: StrictBool = True
    maxPerSlot: Number = 0


class DateWindow(_Item):
    startDate: str
    endDate: str
    key: str | None = None
    label: str | None = None


class Timing(_Block):
    confirmation: ConfirmationMode = "instant"
    approvalWindowHours: Number = Field(
        default=48,
        description="NOT YET ENFORCED, auto-expiring a stale request needs a scheduled job.",
    )
    leadTimeMinutes: Number = 0
    waitlist: Waitlist = Field(default_factory=Waitlist)
    seasons: list[DateWindow] = Field(default_factory=list)
    blackouts: list[DateWindow] = Field(default_factory=list)
    # The five v1 `rules` keys, mirrored back into `rules` by normalize().
    slotDurationMinutes: Number = 30
    maxBookingsPerSlot: Number = 1
    cancellationWindowHours: Number = 24
    advanceBookingWindowDays: Number = 30
    bufferMinutes: Number = 0


# -- recurrence / entitlements / discovery -------------------------------


class Term(_Block):
    mode: str = "fixed"
    noticePeriodDays: Number = 0


class Recurrence(_Block):
    enabled: StrictBool = False
    patterns: list[RecurrencePattern] = Field(default_factory=list)
    maxOccurrences: Number | None = 12
    term: Term = Field(default_factory=Term)


class Plan(_Item):
    key: str
    label: str | None = None
    credits: Number | None = None
    cycle: str | None = None
    discountBps: Number | None = None
    priceMinorUnits: Number | None = None
    appliesToServices: list[str] | None = None


class Entitlements(_Block):
    enabled: StrictBool = False
    kind: EntitlementKind = "none"
    plans: list[Plan] = Field(default_factory=list)


class DiscoveryFacets(_Block):
    price: StrictBool = True
    distance: StrictBool = True
    rating: StrictBool = True
    availability: StrictBool = True
    unitKind: StrictBool = False


class Matching(_Block):
    enabled: StrictBool = False
    source: str = "intake_form"


class Discovery(_Block):
    mode: DiscoveryMode = "browse"
    facets: DiscoveryFacets = Field(default_factory=DiscoveryFacets)
    matching: Matching = Field(default_factory=Matching)


# -- vocabulary ----------------------------------------------------------


class Terms(_Block):
    """Every noun the UI renders. All 17 keys are required to be non-empty
    strings, the frontend's `<Term>` has nothing to fall back to."""

    provider: str = "Business"
    providers: str = "Businesses"
    service: str = "Service"
    services: str = "Services"
    staff: str = "Staff"
    subject: str = "Subject"
    party: str = "Guests"
    resource: str = "Resource"
    resources: str = "Resources"
    slot: str = "Slot"
    slots: str = "Slots"
    booking: str = "Booking"
    bookings: str = "Bookings"
    client: str = "Customer"
    clients: str = "Customers"
    admin: str = "Business"
    admins: str = "Businesses"


class Copy(_Block):
    landingTitle: str = "Book a Resource"
    landingSubtitle: str = "Pick a resource, find an open slot, book it."
    confirmTitle: str = "Booking confirmed"
    emptyStateSlots: str = "No slots available yet."
    emptyStateBookings: str = "You have no bookings yet."
    requestPending: str = "Your request has been sent."
    waitlistJoined: str = "You're on the waitlist."
    quoteRequested: str = "Your quote request has been sent."
    depositDue: str = "A deposit is due to confirm this booking."
    prerequisiteBlocked: str = "Some details are needed before this can be confirmed."


class MetaField(_Item):
    key: str
    type: MetaFieldType | Literal["string"] = Field(
        description="'string' is accepted as an alias for 'text', it shipped in domain.config.medical.example.json and matched nothing in the v1 validator."
    )
    label: str | None = None
    required: StrictBool | None = None
    options: list[str] | None = None


class MetaFields(_Block):
    """Custom fields per entity. Adding one needs no migration, the values land
    in that table's `metadata` jsonb column."""

    providers: list[MetaField] = Field(default_factory=list)
    services: list[MetaField] = Field(default_factory=list)
    resources: list[MetaField] = Field(default_factory=list)
    slots: list[MetaField] = Field(default_factory=list)
    bookings: list[MetaField] = Field(default_factory=list)
    subjects: list[MetaField] = Field(default_factory=list)


# -- deprecated v1 aliases -----------------------------------------------


class LegacyRules(_Block):
    """DEPRECATED. `timing` owns these five keys; `normalize()` mirrors them back
    here so a v1 reader and a v1 config file both keep working."""

    slotDurationMinutes: Number = 30
    maxBookingsPerSlot: Number = 1
    cancellationWindowHours: Number = 24
    advanceBookingWindowDays: Number = 30
    bufferMinutes: Number = 0


class LegacySearchFacets(_Block):
    price: StrictBool = True
    distance: StrictBool = True
    rating: StrictBool = True


class LegacySearch(_Block):
    """DEPRECATED. `discovery` owns this; `normalize()` keeps the two in sync."""

    facets: LegacySearchFacets = Field(default_factory=LegacySearchFacets)


# -- the whole tree ------------------------------------------------------


class DomainConfig(_Block):
    """The complete `domain.config.json` tree, after normalization.

    Every block is also overridable per service through
    `services.metadata.<block>`, see `rules.effective_service_config`. The
    service row wins over these globals.
    """

    configVersion: Number = CONFIG_VERSION
    domain: str = "generic"
    tenancy: Tenancy = Field(default_factory=Tenancy)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    booking: Booking = Field(default_factory=Booking)
    pricing: Pricing = Field(default_factory=Pricing)
    payments: Payments = Field(default_factory=Payments)
    inventory: Inventory = Field(default_factory=Inventory)
    location: Location = Field(default_factory=Location)
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    timing: Timing = Field(default_factory=Timing)
    recurrence: Recurrence = Field(default_factory=Recurrence)
    entitlements: Entitlements = Field(default_factory=Entitlements)
    discovery: Discovery = Field(default_factory=Discovery)
    terms: Terms = Field(default_factory=Terms)
    # Aliased: a field literally named `copy` shadows BaseModel.copy and makes
    # pydantic warn at import. The JSON key is still `copy`, dump by alias.
    copy_: Copy = Field(default_factory=Copy, alias="copy")
    metaFields: MetaFields = Field(default_factory=MetaFields)
    rules: LegacyRules = Field(
        default_factory=LegacyRules, deprecated="Use `timing`, normalize() keeps these in sync."
    )
    search: LegacySearch = Field(
        default_factory=LegacySearch,
        deprecated="Use `discovery`, normalize() keeps these in sync.",
    )


def config_dump(config: DomainConfig | None = None) -> dict[str, Any]:
    """The config as the plain dict the engine passes around.

    Always dumps by alias, so `copy_` lands back under its real JSON key. With
    no argument it returns the full default tree, which is exactly
    `config_schema.DEFAULTS`, and a test holds the two together.
    """
    return (config or DomainConfig()).model_dump(by_alias=True)
