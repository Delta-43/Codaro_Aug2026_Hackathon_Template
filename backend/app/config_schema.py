# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Domain config v2 — defaults, v1 aliasing, and validation.

`domain.config.json` is the pivot file. v1 shipped five sections
(`terms`/`rules`/`copy`/`metaFields`) that between them expressed exactly
one kind of business: a time-slot calendar with a price per slot. v2 adds the
blocks that let the *shape* of the offering pivot too — pricing, payments,
inventory, location, prerequisites, timing.

Three jobs live here, and nothing else. This module is pure dict work: no
database, no FastAPI, no imports from `app.*`, so the CI validator can import it
directly.

* **DEFAULTS** — the complete v2 tree. A pivot file declares only what it
  changes; everything else resolves from here, so a half-written config still
  boots.
* **normalize()** — deep-merges a raw file over DEFAULTS, then keeps the v1
  aliases (`rules` <-> `timing`, `search` <-> `discovery`) consistent in *both*
  directions, so a v1 file runs unchanged. Note the engine itself now reads only
  the v2 keys — `routers/slots.py` and `rules.apply_rules` both go through
  `timing`, and the frontend reads `search.facets`. The `rules` mirror is kept
  purely for a v1 *reader*; nothing in this repo consumes it.
* **validate()** — turns a typo into a load-time error instead of a 500 on
  whichever request happens to read the bad key first. The whole premise of this
  file is that it gets hand-edited under time pressure; failing loudly at the
  edit is the point.

Adding a field: put it in DEFAULTS (that alone makes it readable everywhere and
overridable per service), and add a check to `validate()` only if a wrong value
would corrupt data rather than just look odd.
"""
from __future__ import annotations

import copy as _copy
from typing import Any

CONFIG_VERSION = 2

# -- enum vocabularies ---------------------------------------------------
#
# Kept as plain frozensets rather than Enums so a config value is always a
# JSON-native string and an unknown value is a validation error, never an
# import-time crash.

UNIT_KINDS = frozenset(
    {
        "time_slot", "staff", "asset", "seat", "room",
        "class_capacity", "stock_item", "subscription_slot", "project",
    }
)
GRANULARITIES = frozenset({"minute", "hour", "day", "night", "week", "month", "none"})

# How long one `booking.granularity` unit lasts, in minutes. This is the DEFAULT
# slot length for a config that does not state one — `booking.granularity`
# already says what the business sells (a night, a day, a month), so making the
# calendar contradict it takes a deliberate `timing.slotDurationMinutes`.
#
# Without this every pivot fell back to a flat 30, so a hotel declaring
# `granularity: "night"` seeded 30-minute rooms and a monthly storage unit
# seeded 30-minute leases. `seed_config._grid()` has always had a `>= 1440`
# branch for day-sized units; nothing could ever reach it.
#
# `minute` keeps 30: it means "this business runs a minute-based grid", not
# "one minute", and 30 is the conventional step. `none` means no time grid at
# all, so a day-sized unit is the least-wrong shape for a calendar that still
# has to render something.
GRANULARITY_SLOT_MINUTES = {
    "minute": 30,
    "hour": 60,
    "day": 1440,
    "night": 1440,
    "week": 10080,
    "month": 43200,  # 30 days — calendar months vary; the grid needs one number
    "none": 1440,
}
DURATION_MODES = frozenset({"fixed", "variable", "customer_chosen", "open_ended"})
PARTY_MODES = frozenset({"individual", "group", "buyout"})
PRICING_MODELS = frozenset(
    {
        "fixed", "per_hour", "per_person", "per_unit", "tiered",
        "quote", "deposit_balance", "subscription", "free",
    }
)
RATE_PERIODS = frozenset(
    {"booking", "slot", "hour", "day", "night", "week", "month", "person", "unit"}
)
INVENTORY_MODES = frozenset({"none", "finite", "rentable", "consumable", "serialised"})
LOCATION_MODES = frozenset({"on_site", "at_customer", "remote", "delivery", "pickup"})
PREREQ_KINDS = frozenset(
    {"id_check", "licence", "intake_form", "waiver", "membership", "approval", "credential"}
)
PREREQ_TARGETS = frozenset({"customer", "tenant", "subject"})
CONFIRMATION_MODES = frozenset({"instant", "request_approve"})
PAYMENT_FLOWS = frozenset({"prepay", "pay_on_site", "invoice_after", "split", "none"})
PAYERS = frozenset({"customer", "third_party"})
BILLING_CYCLES = frozenset({"none", "weekly", "monthly", "annual"})
ENTITLEMENT_KINDS = frozenset({"none", "credits", "membership", "pass"})
DISCOVERY_MODES = frozenset({"browse", "reverse"})
TENANCY_MODES = frozenset({"single", "multi"})
META_FIELD_TYPES = frozenset({"text", "number", "boolean", "date", "select", "file"})
FEE_KINDS = frozenset({"flat", "percent", "distanceBand"})
DEPOSIT_KINDS = frozenset({"percent", "flat"})
OPTION_TYPES = frozenset({"boolean", "select"})
RECURRENCE_PATTERNS = frozenset({"weekly", "biweekly", "monthly"})

# `metaFields[].type: "string"` shipped in domain.config.medical.example.json and
# matched nothing in the v1 validator, so it silently validated nothing. Accept it
# as an alias for "text" rather than breaking a config that is already in the repo.
META_FIELD_TYPE_ALIASES = {"string": "text"}

# The five v1 `rules` keys. They now live under `timing` and are mirrored back
# into `rules` so nothing that reads the old path breaks.
_TIMING_ALIASES = (
    "slotDurationMinutes",
    "maxBookingsPerSlot",
    "cancellationWindowHours",
    "advanceBookingWindowDays",
    "bufferMinutes",
)


DEFAULTS: dict[str, Any] = {
    "configVersion": CONFIG_VERSION,
    "domain": "generic",

    "tenancy": {
        "mode": "multi",
        "providerCode": None,
        # Defaults to `mode == "multi"` in normalize() when the file omits it —
        # a marketplace onboards businesses, a single-business site does not.
        "selfOnboarding": None,
        "tenantVerification": {"required": False, "credentials": []},
        "commission": {"enabled": False, "rateBps": 0, "chargedOn": "completion"},
    },

    # The on/off spine. A false capability means the UI hides the surface AND the
    # backend refuses the write — not one without the other. That held for
    # `reviews` and `follows` only once they were actually gated (they are, in
    # bookings.py / providers.py); the rest name surfaces that do not exist yet,
    # so there is nothing to refuse and scripts/check_pivots.py lists them as
    # unbuilt. Wiring a new capability means writing its gate at the same time.
    "capabilities": {
        "payments": True,
        "inventory": False,
        "waitlist": False,
        "quotes": False,
        "recurrence": False,
        "prerequisites": False,
        "entitlements": False,
        "cart": False,
        "reviews": True,
        "follows": True,
    },

    "booking": {
        "unitKind": "time_slot",
        "granularity": "minute",
        "duration": {"mode": "fixed", "minUnits": 1, "maxUnits": 1, "incrementUnits": 1},
        "party": {
            "mode": "individual",
            "min": 1,
            "max": None,          # null => the resource's own capacity is the ceiling
            "composition": None,  # [{key, label, priceFactor}] — age bands etc.
            "matchResourceCapacity": False,
        },
        "sequence": {"enabled": False, "steps": 1, "minGapHours": 0, "maxGapHours": None},
        "subject": {"enabled": False, "noun": "Subject", "fields": []},
        "options": [],
    },

    "pricing": {
        "model": "fixed",
        "currency": "EUR",
        "currencyExponent": 2,
        "rate": {"per": "slot", "amountMinorUnits": 0},
        "secondaryRate": None,
        "tiers": [],
        # True reproduces the v1 formula (price x slots x party). Set false where
        # the party shares one unit — a tennis court costs the same for 2 or 4.
        "chargePerPerson": True,
        # perBookingMinorUnits is enforced by pricing.quote(). perDayMinorUnits is
        # NOT: it needs the customer's other bookings that day, which is a query,
        # not arithmetic. Declared so a config can express it; see TODO.
        "caps": {"perBookingMinorUnits": None, "perDayMinorUnits": None},
        "fees": [],
        "deposit": {"enabled": False, "kind": "percent", "value": 0, "refundable": True},
    },

    "payments": {
        "flow": "prepay",
        "payer": "customer",
        "schedule": [],
        "billingCycle": "none",
        # NOT YET ENFORCED — needs the payments layer (no payments table exists).
        "noShowFee": {"enabled": False, "amountMinorUnits": 0},
        "usageMetered": False,
        # No PSP exists in this repo. "manual" = the owner marks a booking paid,
        # which is enough to exercise every flow above end to end.
        "adapter": "manual",
    },

    "inventory": {
        "mode": "none",
        "reservationWindowMinutes": 15,
        "loanPeriodHours": None,
        "returnRequired": False,
        "overdueFeePerDayMinorUnits": 0,
        "restockCycle": "none",
        "ratioConstraint": None,
    },

    "location": {
        "modes": ["on_site"],
        "default": "on_site",
        # The business's own timezone. Absent in v1, which is why an anonymous
        # visitor always saw availability grouped in UTC.
        "timezone": "UTC",
        "distanceUnit": "km",
        "origin": None,  # {city, lat, lng} — the distance-from point
        "serviceArea": {"radiusKm": None, "travelBufferMinutes": 0, "feeBands": []},
        "remote": {"meetingLinkMode": "none"},
        "fulfilment": {"windowMinutes": 60, "cutoffHoursBefore": 0},
    },

    "prerequisites": [],

    "timing": {
        "confirmation": "instant",
        # NOT YET ENFORCED — auto-expiring a stale request needs a scheduled job.
        "approvalWindowHours": 48,
        # Enforced on booking.create via the rules registry (`rules._lead_time`).
        "leadTimeMinutes": 0,
        "waitlist": {"enabled": False, "autoPromote": True, "maxPerSlot": 0},
        "seasons": [],
        "blackouts": [],
        # The five v1 `rules` keys, mirrored back into `rules` by normalize().
        "slotDurationMinutes": 30,
        "maxBookingsPerSlot": 1,
        "cancellationWindowHours": 24,
        "advanceBookingWindowDays": 30,
        "bufferMinutes": 0,
    },

    "recurrence": {
        "enabled": False,
        "patterns": [],
        "maxOccurrences": 12,
        "term": {"mode": "fixed", "noticePeriodDays": 0},
    },

    "entitlements": {"enabled": False, "kind": "none", "plans": []},

    "discovery": {
        "mode": "browse",
        "facets": {
            "price": True,
            "distance": True,
            "rating": True,
            "availability": True,
            "unitKind": False,
        },
        "matching": {"enabled": False, "source": "intake_form"},
    },

    "terms": {
        "provider": "Business", "providers": "Businesses",
        "service": "Service", "services": "Services",
        "staff": "Staff", "subject": "Subject", "party": "Guests",
        "resource": "Resource", "resources": "Resources",
        "slot": "Slot", "slots": "Slots",
        "booking": "Booking", "bookings": "Bookings",
        "client": "Customer", "clients": "Customers",
        "admin": "Business", "admins": "Businesses",
    },

    "copy": {
        "landingTitle": "Book a Resource",
        "landingSubtitle": "Pick a resource, find an open slot, book it.",
        "confirmTitle": "Booking confirmed",
        "emptyStateSlots": "No slots available yet.",
        "emptyStateBookings": "You have no bookings yet.",
        "requestPending": "Your request has been sent.",
        "waitlistJoined": "You're on the waitlist.",
        "quoteRequested": "Your quote request has been sent.",
        "depositDue": "A deposit is due to confirm this booking.",
        "prerequisiteBlocked": "Some details are needed before this can be confirmed.",
    },

    "metaFields": {
        "providers": [], "services": [], "resources": [],
        "slots": [], "bookings": [], "subjects": [],
    },

    # Deprecated v1 aliases. Kept populated by normalize() so a v1 reader and a
    # v1 config file both keep working; `timing` / `discovery` are the truth.
    "rules": {
        "slotDurationMinutes": 30,
        "maxBookingsPerSlot": 1,
        "cancellationWindowHours": 24,
        "advanceBookingWindowDays": 30,
        "bufferMinutes": 0,
    },
    "search": {"facets": {"price": True, "distance": True, "rating": True}},
}


def deep_merge(base: dict, override: Any) -> dict:
    """Recursively merge `override` onto `base`, IN PLACE. Lists replace
    wholesale — a config that declares `pricing.tiers` means *those* tiers, not
    those plus the defaults.

    Public because `rules.py` had a second, identical implementation that only
    differed by copying first; it now wraps this one."""
    if not isinstance(override, dict):
        return base
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def normalize(raw: dict | None) -> dict:
    """Resolve a raw pivot file into the full v2 tree.

    Deep-merges over DEFAULTS, then reconciles the two v1 aliases. Precedence for
    an aliased value is: explicit v2 path -> explicit v1 path -> default. The
    resolved value is written back to *both* paths, so `cfg["timing"]["bufferMinutes"]`
    and `cfg["rules"]["bufferMinutes"]` can never disagree.
    """
    raw = raw or {}
    cfg = deep_merge(_copy.deepcopy(DEFAULTS), raw)
    # v1's `theme` block (primaryColor/radius) is gone: the frontend owns its own
    # palette. Dropped rather than rejected so an old pivot file still boots — it
    # simply has no effect on the UI.
    cfg.pop("theme", None)

    raw_timing = raw.get("timing") if isinstance(raw.get("timing"), dict) else {}
    raw_rules = raw.get("rules") if isinstance(raw.get("rules"), dict) else {}
    for key in _TIMING_ALIASES:
        if key in raw_timing:
            value = raw_timing[key]
        elif key in raw_rules:
            value = raw_rules[key]
        elif key == "slotDurationMinutes":
            # Undeclared slot length follows `booking.granularity` rather than a
            # flat 30, so the calendar matches the unit the config says is sold.
            # An explicit value on either path still wins (both branches above).
            #
            # `normalize` runs before `validate`, so `granularity` here may still
            # be any JSON value — including an unhashable list/dict, which would
            # make a bare `.get()` raise TypeError and escape as a 500 instead of
            # the ConfigError the caller expects. Non-strings fall through to the
            # default and let `validate` report the real problem.
            granularity = cfg["booking"].get("granularity")
            value = DEFAULTS["timing"][key]
            if isinstance(granularity, str):
                value = GRANULARITY_SLOT_MINUTES.get(granularity, value)
        else:
            value = DEFAULTS["timing"][key]
        cfg["timing"][key] = value
        cfg["rules"][key] = value

    raw_discovery = raw.get("discovery") if isinstance(raw.get("discovery"), dict) else {}
    raw_search = raw.get("search") if isinstance(raw.get("search"), dict) else {}
    declared_facets = {
        **(raw_search.get("facets") or {}),
        **(raw_discovery.get("facets") or {}),
    }
    facets = {**DEFAULTS["discovery"]["facets"], **declared_facets}
    cfg["discovery"]["facets"] = facets
    # `search.facets` keeps only the three keys the v1 shape declared, so a v1
    # consumer never sees a key it can't render.
    cfg["search"]["facets"] = {k: facets[k] for k in ("price", "distance", "rating")}

    if cfg["tenancy"].get("selfOnboarding") is None:
        cfg["tenancy"]["selfOnboarding"] = cfg["tenancy"].get("mode") == "multi"

    cfg["configVersion"] = int(cfg.get("configVersion") or CONFIG_VERSION)
    return cfg


# -- validation ----------------------------------------------------------


def check_shape(raw: dict, expected: dict | None = None, prefix: str = "") -> list[str]:
    """Type-check blocks against DEFAULTS BEFORE `normalize()` touches them.

    `normalize()` and `validate()` both assume a block is the shape DEFAULTS says
    it is. A hand-edited `"timing": []` or `"tenancy": "single"` therefore raised
    TypeError/AttributeError out of the load path instead of being reported —
    which turned a typo into a 500 from /config/reload and a traceback at
    startup, exactly what load-time validation exists to prevent.

    It recurses, because the top level was never where the assumption lived:
    `validate()` indexes `booking["duration"]["mode"]` and `pricing["rate"]["per"]`,
    so a nested `"duration": 5` escaped the top-level check and hit the same
    AttributeError. Only keys DEFAULTS declares are inspected — an unknown key is
    the extension point and passes through, exactly as before.
    """
    errors: list[str] = []
    expected = DEFAULTS if expected is None else expected
    for key, value in (raw or {}).items():
        if key not in expected:
            continue
        want = expected[key]
        path = f"{prefix}{key}"
        if isinstance(want, dict):
            if not isinstance(value, dict):
                errors.append(f"{path} must be an object, got {type(value).__name__}")
            else:
                errors.extend(check_shape(value, want, f"{path}."))
        elif isinstance(want, list) and not isinstance(value, list):
            errors.append(f"{path} must be a list, got {type(value).__name__}")
    if not prefix:
        version = (raw or {}).get("configVersion")
        if version is not None and (
            isinstance(version, bool) or not isinstance(version, (int, float))
        ):
            errors.append(f"configVersion must be a number, got {version!r}")
    return errors


class ConfigError(ValueError):
    """A pivot file that would break the engine. Raised at load, not at request."""


def _enum(errors: list[str], value: Any, allowed: frozenset, path: str) -> None:
    # `value not in frozenset` raises TypeError on a dict/list, and a hand-edited
    # config puts objects in scalar positions all the time
    # (`patterns: [{"every": "week"}]`). That must be a listed problem, not a
    # traceback — an unhandled error here would surface as a 500 from
    # /config/reload instead of the 422 the endpoint promises.
    if isinstance(value, (dict, list, set, bytearray)) or value not in allowed:
        errors.append(f"{path} must be one of {sorted(allowed)}, got {value!r}")


def _int(errors: list[str], value: Any, path: str, *, minimum: int | None = None,
         allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{path} must be a number, got {value!r}")
        return
    if minimum is not None and value < minimum:
        errors.append(f"{path} must be >= {minimum}, got {value!r}")


def _bool(errors: list[str], value: Any, path: str) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path} must be true or false, got {value!r}")


def validate(cfg: dict) -> list[str]:
    """Check a NORMALIZED config. Returns a list of human-readable problems;
    empty means good. Only checks things that would corrupt data or hard-crash a
    request — a silly colour is not this function's business."""
    errors: list[str] = []

    _enum(errors, cfg["tenancy"].get("mode"), TENANCY_MODES, "tenancy.mode")
    if cfg["tenancy"]["mode"] == "single" and not cfg["tenancy"].get("providerCode"):
        errors.append(
            "tenancy.providerCode is required when tenancy.mode is 'single' "
            "(it is how the app resolves its one business)"
        )
    _int(errors, cfg["tenancy"]["commission"].get("rateBps"), "tenancy.commission.rateBps", minimum=0)

    for key, value in cfg["capabilities"].items():
        _bool(errors, value, f"capabilities.{key}")

    booking = cfg["booking"]
    _enum(errors, booking.get("unitKind"), UNIT_KINDS, "booking.unitKind")
    _enum(errors, booking.get("granularity"), GRANULARITIES, "booking.granularity")
    _enum(errors, booking["duration"].get("mode"), DURATION_MODES, "booking.duration.mode")
    _int(errors, booking["duration"].get("minUnits"), "booking.duration.minUnits", minimum=1)
    _int(errors, booking["duration"].get("maxUnits"), "booking.duration.maxUnits", minimum=1)
    if isinstance(booking["duration"].get("minUnits"), int) and isinstance(
        booking["duration"].get("maxUnits"), int
    ):
        if booking["duration"]["minUnits"] > booking["duration"]["maxUnits"]:
            errors.append("booking.duration.minUnits must not exceed booking.duration.maxUnits")
    _enum(errors, booking["party"].get("mode"), PARTY_MODES, "booking.party.mode")
    _int(errors, booking["party"].get("min"), "booking.party.min", minimum=1)
    _int(errors, booking["party"].get("max"), "booking.party.max", minimum=1, allow_none=True)
    if isinstance(booking["party"].get("min"), int) and isinstance(booking["party"].get("max"), int):
        if booking["party"]["min"] > booking["party"]["max"]:
            errors.append("booking.party.min must not exceed booking.party.max")
    # `party.composition[].priceFactor` reaches `rules.resolve_party_bands` as
    # `float(factor)`, so a non-numeric one would 500 a booking rather than fail
    # here at the edit. Absent/None is fine (defaults to 1.0 there).
    composition = booking["party"].get("composition")
    if isinstance(composition, list):
        for i, band in enumerate(composition):
            if not isinstance(band, dict) or not band.get("key"):
                errors.append(f"booking.party.composition[{i}] must be an object with a key")
                continue
            _int(errors, band.get("priceFactor"),
                 f"booking.party.composition[{i}].priceFactor", minimum=0, allow_none=True)

    pricing = cfg["pricing"]
    _enum(errors, pricing.get("model"), PRICING_MODELS, "pricing.model")
    _enum(errors, (pricing.get("rate") or {}).get("per"), RATE_PERIODS, "pricing.rate.per")
    _int(errors, (pricing.get("rate") or {}).get("amountMinorUnits"),
         "pricing.rate.amountMinorUnits", minimum=0)
    _int(errors, pricing.get("currencyExponent"), "pricing.currencyExponent", minimum=0)
    if not isinstance(pricing.get("currency"), str) or len(pricing.get("currency") or "") != 3:
        errors.append(f"pricing.currency must be a 3-letter ISO 4217 code, got {pricing.get('currency')!r}")
    if pricing.get("secondaryRate") is not None:
        _enum(errors, pricing["secondaryRate"].get("per"), RATE_PERIODS, "pricing.secondaryRate.per")
        _int(errors, pricing["secondaryRate"].get("amountMinorUnits"),
             "pricing.secondaryRate.amountMinorUnits", minimum=0)
    for i, tier in enumerate(pricing.get("tiers") or []):
        if not isinstance(tier, dict):
            errors.append(f"pricing.tiers[{i}] must be an object")
            continue
        if not tier.get("key"):
            errors.append(f"pricing.tiers[{i}].key is required")
        _int(errors, tier.get("amountMinorUnits"), f"pricing.tiers[{i}].amountMinorUnits", minimum=0)

    for i, fee in enumerate(pricing.get("fees") or []):
        if not isinstance(fee, dict):
            errors.append(f"pricing.fees[{i}] must be an object")
            continue
        kind = fee.get("kind", "flat")
        _enum(errors, kind, FEE_KINDS, f"pricing.fees[{i}].kind")
        if kind == "percent":
            _int(errors, fee.get("rateBps"), f"pricing.fees[{i}].rateBps", minimum=0)
        elif kind == "distanceBand":
            bands = fee.get("bands")
            if not bands or not isinstance(bands, list):
                errors.append(
                    f"pricing.fees[{i}].bands must be a non-empty list for a distanceBand fee"
                )
            else:
                for b, band in enumerate(bands):
                    if not isinstance(band, dict):
                        errors.append(f"pricing.fees[{i}].bands[{b}] must be an object")
                        continue
                    _int(errors, band.get("maxKm"), f"pricing.fees[{i}].bands[{b}].maxKm",
                         minimum=0, allow_none=True)
                    _int(errors, band.get("feeMinorUnits"),
                         f"pricing.fees[{i}].bands[{b}].feeMinorUnits", minimum=0)
        elif kind == "flat":
            _int(errors, fee.get("amountMinorUnits"), f"pricing.fees[{i}].amountMinorUnits", minimum=0)
    _enum(errors, (pricing.get("deposit") or {}).get("kind"), DEPOSIT_KINDS, "pricing.deposit.kind")
    # These three reach pricing arithmetic through `pricing._int`, which coerces
    # junk to 0 — an unvalidated cap of "free" would zero every price at quote
    # time instead of failing here at the edit.
    _int(errors, (pricing.get("deposit") or {}).get("value"),
         "pricing.deposit.value", minimum=0)
    caps = pricing.get("caps") or {}
    _int(errors, caps.get("perBookingMinorUnits"),
         "pricing.caps.perBookingMinorUnits", minimum=0, allow_none=True)
    _int(errors, caps.get("perDayMinorUnits"),
         "pricing.caps.perDayMinorUnits", minimum=0, allow_none=True)

    payments = cfg["payments"]
    _enum(errors, payments.get("flow"), PAYMENT_FLOWS, "payments.flow")
    _enum(errors, payments.get("payer"), PAYERS, "payments.payer")
    _enum(errors, payments.get("billingCycle"), BILLING_CYCLES, "payments.billingCycle")
    if cfg["capabilities"]["payments"] is False and payments["flow"] != "none":
        errors.append(
            "capabilities.payments is false, so payments.flow must be 'none' "
            f"(got {payments['flow']!r}) — otherwise the UI hides a step the API still enforces"
        )

    for i, step in enumerate(payments.get("schedule") or []):
        if not isinstance(step, dict):
            errors.append(f"payments.schedule[{i}] must be an object")
            continue
        if not step.get("key"):
            errors.append(f"payments.schedule[{i}].key is required")
        _enum(errors, step.get("kind", "percent"), DEPOSIT_KINDS, f"payments.schedule[{i}].kind")
        _int(errors, step.get("value"), f"payments.schedule[{i}].value", minimum=0)

    for i, option in enumerate(booking.get("options") or []):
        if not isinstance(option, dict):
            errors.append(f"booking.options[{i}] must be an object")
            continue
        if not option.get("key"):
            errors.append(f"booking.options[{i}].key is required")
        _enum(errors, option.get("type", "boolean"), OPTION_TYPES, f"booking.options[{i}].type")
        if option.get("type") == "select" and not option.get("choices"):
            errors.append(f"booking.options[{i}].choices is required for a select option")

    for i, pattern in enumerate(cfg["recurrence"].get("patterns") or []):
        _enum(errors, pattern, RECURRENCE_PATTERNS, f"recurrence.patterns[{i}]")
    # `serialize_service` does `int(recurrence.maxOccurrences or 1)`, so a
    # non-numeric value 500s /services rather than failing here. 0/None coerce to
    # 1 downstream, so only reject a genuinely non-numeric value.
    _int(errors, cfg["recurrence"].get("maxOccurrences"), "recurrence.maxOccurrences",
         minimum=0, allow_none=True)
    for i, plan in enumerate(cfg["entitlements"].get("plans") or []):
        if not isinstance(plan, dict) or not plan.get("key"):
            errors.append(f"entitlements.plans[{i}] must be an object with a key")
            continue
        # `discountBps` reaches `serialize_entitlement`/`resolve_entitlement` as
        # `int(discountBps or 0)`; a non-numeric one 500s those reads.
        _int(errors, plan.get("discountBps"), f"entitlements.plans[{i}].discountBps",
             minimum=0, allow_none=True)

    _enum(errors, cfg["inventory"].get("mode"), INVENTORY_MODES, "inventory.mode")
    _int(errors, cfg["inventory"].get("reservationWindowMinutes"),
         "inventory.reservationWindowMinutes", minimum=0)

    location = cfg["location"]
    modes = location.get("modes")
    if not isinstance(modes, list) or not modes:
        errors.append("location.modes must be a non-empty list")
    else:
        for i, mode in enumerate(modes):
            _enum(errors, mode, LOCATION_MODES, f"location.modes[{i}]")
        if location.get("default") not in modes:
            errors.append(
                f"location.default ({location.get('default')!r}) must be one of location.modes {modes}"
            )
    if not _is_valid_timezone(location.get("timezone")):
        errors.append(f"location.timezone must be a valid IANA zone, got {location.get('timezone')!r}")

    for i, prereq in enumerate(cfg.get("prerequisites") or []):
        if not isinstance(prereq, dict):
            errors.append(f"prerequisites[{i}] must be an object")
            continue
        if not prereq.get("key"):
            errors.append(f"prerequisites[{i}].key is required")
        _enum(errors, prereq.get("kind"), PREREQ_KINDS, f"prerequisites[{i}].kind")
        _enum(errors, prereq.get("appliesTo", "customer"), PREREQ_TARGETS,
              f"prerequisites[{i}].appliesTo")

    timing = cfg["timing"]
    _enum(errors, timing.get("confirmation"), CONFIRMATION_MODES, "timing.confirmation")
    _int(errors, timing.get("slotDurationMinutes"), "timing.slotDurationMinutes", minimum=1)
    _int(errors, timing.get("maxBookingsPerSlot"), "timing.maxBookingsPerSlot", minimum=1)
    _int(errors, timing.get("cancellationWindowHours"), "timing.cancellationWindowHours", minimum=0)
    _int(errors, timing.get("advanceBookingWindowDays"), "timing.advanceBookingWindowDays", minimum=0)
    _int(errors, timing.get("bufferMinutes"), "timing.bufferMinutes", minimum=0)
    _int(errors, timing.get("leadTimeMinutes"), "timing.leadTimeMinutes", minimum=0)
    # These MUST carry a dotted path: `validate_overrides` filters errors by their
    # leading path segment, so a pathless message is silently dropped and a
    # malformed window sails through the per-service write gate.
    for key in ("seasons", "blackouts"):
        for i, window in enumerate(timing.get(key) or []):
            if not isinstance(window, dict) or not window.get("startDate") or not window.get("endDate"):
                errors.append(f"timing.{key}[{i}] needs startDate and endDate")

    _enum(errors, cfg["entitlements"].get("kind"), ENTITLEMENT_KINDS, "entitlements.kind")
    _enum(errors, cfg["discovery"].get("mode"), DISCOVERY_MODES, "discovery.mode")

    for term, value in cfg["terms"].items():
        if not isinstance(value, str) or not value:
            errors.append(f"terms.{term} must be a non-empty string")
    for key, value in cfg["copy"].items():
        if not isinstance(value, str) or not value:
            errors.append(f"copy.{key} must be a non-empty string")

    errors.extend(validate_meta_fields(cfg.get("metaFields") or {}))
    return errors


def validate_overrides(overrides: dict, base: dict | None = None) -> list[str]:
    """Validate a PARTIAL config — the blocks one service overrides.

    `validate()` only ever ran on the global file at load, so per-service
    overrides (`services.metadata.<block>`) reached the pricing and scheduling
    paths completely unchecked. That is the same class of bug as a metaField
    descriptor that silently validates nothing, except it applies to money.

    The trick is to merge the overrides onto a known-good base and then keep only
    the errors belonging to a block the caller actually declared — otherwise a
    service overriding `pricing` would be blamed for the deployment's unrelated
    `tenancy` settings.

    `base` must be the deployment's own resolved config, because every
    cross-block invariant depends on it. Validating against DEFAULTS instead got
    it wrong in both directions: it accepted `payments.flow: "prepay"` on a
    deployment with `capabilities.payments: false` (the exact contradiction
    `validate()` exists to catch), and rejected `location.modes: ["remote"]` on a
    deployment whose `location.default` was already `"remote"`. DEFAULTS remains
    the fallback so the function is still usable without a loaded config.

    Shape is checked first, for the same reason `load_config` checks it before
    `normalize()`: `validate()` indexes into a block assuming its declared type,
    so a malformed override (`"pricing": {"rate": 5}`) raised an AttributeError
    straight out of this function. On the global path that was caught and
    reported; here it escaped as a 500 from every read that resolves a service.
    """
    if not overrides:
        return []
    declared = {k: v for k, v in overrides.items() if k in DEFAULTS}
    if not declared:
        return []
    shape = check_shape(declared)
    if shape:
        return shape
    # Report exactly the errors the override INTRODUCES, by diffing against the
    # base's own errors. Filtering by the error's leading path segment looked
    # equivalent but silently dropped cross-block violations: overriding
    # `payments.flow` on a `capabilities.payments: false` deployment produces an
    # error named after `capabilities`, which the caller never declared.
    baseline = base or DEFAULTS
    try:
        before = set(validate(baseline))
        merged = deep_merge(_copy.deepcopy(baseline), declared)
        return [e for e in validate(merged) if e not in before]
    except Exception as e:  # backstop: no shape bug may escape as a 500
        return [f"{', '.join(sorted(declared))} could not be read: {type(e).__name__}: {e}"]


def validate_meta_fields(meta_fields: dict) -> list[str]:
    """metaFields is the no-migration extension point, so a malformed descriptor
    silently disabling validation is the worst possible failure mode."""
    errors: list[str] = []
    for entity, fields in meta_fields.items():
        if not isinstance(fields, list):
            errors.append(f"metaFields.{entity} must be a list (use [] when the domain adds none)")
            continue
        for i, field in enumerate(fields):
            path = f"metaFields.{entity}[{i}]"
            if not isinstance(field, dict):
                errors.append(f"{path} must be an object")
                continue
            for required in ("key", "label", "type"):
                if not isinstance(field.get(required), str) or not field.get(required):
                    errors.append(f"{path}.{required} must be a non-empty string")
            ftype = field.get("type")
            if isinstance(ftype, str):
                resolved = META_FIELD_TYPE_ALIASES.get(ftype, ftype)
                if resolved not in META_FIELD_TYPES:
                    errors.append(
                        f"{path}.type must be one of {sorted(META_FIELD_TYPES)} "
                        f"(or the alias 'string'), got {ftype!r}"
                    )
            if field.get("type") in ("select",) and not field.get("options"):
                errors.append(f"{path}.options is required for a select field")
    return errors


def _is_valid_timezone(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name)
        return True
    except Exception:
        return False
