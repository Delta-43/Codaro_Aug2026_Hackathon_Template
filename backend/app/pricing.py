"""Config-driven price quoting.

v1 priced every booking with one hardcoded expression in `routers/bookings.py`::

    price_minor_units = rules["priceMinorUnits"] * len(rows) * party

That is exactly one pricing model — per-slot, multiplied by party — and it is
the reason a per-hour, per-night, per-person, tiered, capped or fee-bearing
niche could not be reached by editing the pivot file.

This module replaces it with `quote()`, which reads the resolved `pricing` block
and returns a total plus an itemised breakdown. **The defaults reproduce the v1
expression exactly** (`rate.per = "slot"`, `chargePerPerson = true`), so an
un-pivoted config prices identically to before.

Order of operations, and it matters:

1. pick the per-unit amount — a matching tier overrides `rate.amountMinorUnits`,
   and `model: "free"` zeroes it (fees below still apply)
2. base = amount x quantity(rate.per) x party factor
3. + secondary rate (an independent axis, e.g. pallets x weeks)
4. + fees (flat / percent of subtotal / distance band)
5. clamp to `caps`
6. derive the deposit from the final total

Not enforced here, and deliberately so: `tiers[].quantityCap` (an early-bird
pool) needs a count of what has already been sold, which is a database question,
not an arithmetic one. It validates and round-trips; it does not yet gate.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any

# Whole-unit periods bill by started unit — half a day of storage is a day.
# An hour is the exception: 90 minutes of a court is genuinely 1.5 hours.
_MINUTES_PER_UNIT = {"day": 1440, "night": 1440, "week": 10080, "month": 43200}


def quote(pricing: dict, ctx: dict) -> dict:
    """Price one booking.

    `pricing` is the resolved `pricing` block (see `rules.effective_service_pricing`).
    `ctx` describes the selection:

        slot_count        int   number of slots held (default 1)
        party_size        int   heads on the booking (default 1)
        person_units      float weighted head count when `booking.party.composition`
                                is in play (defaults to party_size)
        duration_minutes  int   total wall-clock span of the selection
        unit_count        float explicit quantity for `rate.per == "unit"`
        start_local       datetime|None  start in the business timezone (time-of-day tiers)
        now               datetime|None  purchase time (early-bird windows)
        booking_index     int|None  how many bookings this customer already has
        zone              str|None  seat/area zone key
        subject           dict|None the pet/vehicle/child the booking is about
        distance_km       float|None travel distance (distance-band fees)
        addons            list|None resolved `booking.options` lines to add to the
                                total (`{key, label, amountMinorUnits}` each)
        entitlement       dict|None  the resolved plan the customer holds
                                     (`{key, label, discountBps}`), or None

    Returns `{amountMinorUnits, currency, depositMinorUnits, breakdown[]}`.
    """
    currency = pricing.get("currency") or "EUR"
    breakdown: list[dict[str, Any]] = []

    rate = pricing.get("rate") or {}
    per = rate.get("per") or "slot"
    amount = _int(rate.get("amountMinorUnits"))

    tier = match_tier(pricing.get("tiers") or [], ctx)
    if tier is not None and tier.get("amountMinorUnits") is not None:
        amount = _int(tier["amountMinorUnits"])

    # `model` was validated against a nine-value enum and then read by NOTHING —
    # every total came off `rate.per`, so `"model": "free"` on a config that still
    # carried a rate charged full price for it. Free zeroes the RATE, not the
    # booking: a free class with a booking fee is a real pivot (#57), and fees,
    # caps and the deposit still apply below. The other models need no branch —
    # fixed / per_hour / per_person / per_unit / tiered / deposit_balance are
    # exactly what `rate.per`, `tiers` and `deposit` already express; `quote` and
    # `subscription` need the quote flow and the billing adapter, and are listed
    # as unbuilt in scripts/check_pivots.py rather than silently priced as fixed.
    if pricing.get("model") == "free":
        amount = 0

    quantity = _quantity(per, ctx)
    factor = _party_factor(pricing, per, ctx)
    base = round(amount * quantity * factor)
    breakdown.append(
        {
            "key": tier["key"] if tier else "base",
            "label": (tier or {}).get("label") or f"{_money_label(per)}",
            "amountMinorUnits": base,
        }
    )

    total = base

    secondary = pricing.get("secondaryRate")
    if isinstance(secondary, dict) and secondary.get("amountMinorUnits"):
        sec_per = secondary.get("per") or "unit"
        sec = round(_int(secondary["amountMinorUnits"]) * _quantity(sec_per, ctx))
        total += sec
        breakdown.append(
            {"key": "secondary", "label": _money_label(sec_per), "amountMinorUnits": sec}
        )

    # An entitlement the customer holds — a membership, a pass — discounts the
    # SERVICE CHARGE (base + secondary), not the fees below it.
    #
    # `entitlements.plans[].discountBps` was declared, validated and read by
    # nothing: member pricing could only be faked by hand-passing a `zone` the
    # customer could have chosen themselves. This is the hook that makes it real.
    #
    # Discounting before the fee loop is deliberate and is the conservative
    # reading: fees are typically pass-through (a booking fee, a cleaning
    # charge), and percentage fees below therefore compute off the discounted
    # charge. Whether a platform's commission sits on the net or the gross is
    # already an open question in this schema — see scripts/check_pivots.py #65 —
    # and a member discount must not quietly answer it a second way.
    entitlement = ctx.get("entitlement")
    if isinstance(entitlement, dict):
        bps = _int(entitlement.get("discountBps"))
        if bps > 0 and total > 0:
            # Negative line: the breakdown reads as an itemised bill, so a
            # discount belongs in it as a discount, not as a silently smaller base.
            discount = -round(total * min(bps, 10000) / 10000)
            total += discount
            breakdown.append(
                {
                    "key": f"entitlement:{entitlement.get('key')}",
                    "label": entitlement.get("label") or "Member discount",
                    "amountMinorUnits": discount,
                }
            )

    # Paid add-ons the customer chose (`booking.options`), already resolved to
    # `{key, label, amountMinorUnits}` by `rules.resolve_options` — this module
    # only ever sees the `pricing` block, so the caller does the config lookup.
    #
    # Placed AFTER the entitlement discount and BEFORE the fees on purpose: a
    # member discount is on the service, not on the hired kit or the meal, while
    # a percentage fee (cleaning, service charge) is levied on everything sold.
    for addon in (ctx.get("addons") or []):
        if not isinstance(addon, dict):
            continue
        amount = _int(addon.get("amountMinorUnits"))
        if not amount:
            continue
        total += amount
        breakdown.append(
            {
                "key": f"option:{addon.get('key')}",
                "label": addon.get("label") or "Extra",
                "amountMinorUnits": amount,
            }
        )

    for i, fee in enumerate(pricing.get("fees") or []):
        if not isinstance(fee, dict):
            continue
        if fee.get("appliesWhen") and not _matches(fee["appliesWhen"], ctx):
            continue
        value = _fee_amount(fee, total, ctx)
        if not value:
            continue
        total += value
        breakdown.append(
            {
                "key": fee.get("key") or f"fee_{i}",
                "label": fee.get("label") or "Fee",
                "amountMinorUnits": value,
            }
        )

    total = _apply_caps(pricing.get("caps") or {}, total, breakdown)
    total = max(0, total)

    return {
        "amountMinorUnits": total,
        "currency": currency,
        "depositMinorUnits": _deposit(pricing.get("deposit") or {}, total),
        "breakdown": breakdown,
    }


# -- quantity + party ----------------------------------------------------


def _quantity(per: str, ctx: dict) -> float:
    if per == "booking":
        return 1.0
    if per == "slot":
        return float(max(1, _int(ctx.get("slot_count"), 1)))
    if per == "person":
        return float(_person_units(ctx))
    if per == "unit":
        return float(ctx.get("unit_count") or 1)
    if per == "hour":
        return _int(ctx.get("duration_minutes")) / 60.0
    if per in _MINUTES_PER_UNIT:
        # Derived from the selection's span ONLY. `unit_count` used to override
        # this, which quietly broke any config combining a `per: "unit"` rate
        # with a period-based secondaryRate: the unit count (20 pallets) was
        # applied to the period too (20 weeks instead of 4). A period is a
        # duration; a unit is a quantity; they must not share an input.
        minutes = _int(ctx.get("duration_minutes"))
        return float(max(1, math.ceil(minutes / _MINUTES_PER_UNIT[per])))
    return 1.0


def _person_units(ctx: dict) -> float:
    """Weighted head count — `booking.party.composition` lets an adult and a
    child cost different multiples of the same base rate."""
    if ctx.get("person_units") is not None:
        return float(ctx["person_units"])
    return float(max(1, _int(ctx.get("party_size"), 1)))


def _party_factor(pricing: dict, per: str, ctx: dict) -> float:
    """`per: "person"` already counts heads, so multiplying again would square
    it. Otherwise `chargePerPerson` decides — true reproduces the v1 formula
    (price x slots x party); false is the shared-unit case, where a court costs
    the same for two players or four."""
    if per == "person":
        return 1.0
    if pricing.get("chargePerPerson", True):
        return _person_units(ctx)
    return 1.0


# -- tiers ---------------------------------------------------------------


def match_tier(tiers: list, ctx: dict) -> dict | None:
    """First tier whose sales window is open AND whose `appliesWhen` matches.
    Order in the config is the precedence order — put the most specific first."""
    now = ctx.get("now")
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        if not _within_sales_window(tier, now):
            continue
        if _matches(tier.get("appliesWhen") or {}, ctx):
            return tier
    return None


def _within_sales_window(tier: dict, now: datetime | None) -> bool:
    if not tier.get("validFrom") and not tier.get("validUntil"):
        return True
    if now is None:
        return True
    today = now.date()
    start = _as_date(tier.get("validFrom"))
    end = _as_date(tier.get("validUntil"))
    if start and today < start:
        return False
    if end and today > end:
        return False
    return True


def _matches(condition: dict, ctx: dict) -> bool:
    """Every declared clause must hold. An unknown clause key fails closed —
    a typo must not silently widen a discount to everyone."""
    if not condition:
        return True
    for key, expected in condition.items():
        if key == "partySize":
            if not _in_range(_person_units(ctx), expected):
                return False
        elif key == "bookingIndex":
            if ctx.get("booking_index") is None or not _in_range(ctx["booking_index"], expected):
                return False
        elif key == "zone":
            if ctx.get("zone") != expected:
                return False
        elif key == "timeOfDay":
            if not _in_time_window(ctx.get("start_local"), expected):
                return False
        elif key == "subjectField":
            subject = ctx.get("subject") or {}
            if subject.get((expected or {}).get("key")) != (expected or {}).get("equals"):
                return False
        elif key == "distanceKm":
            if ctx.get("distance_km") is None or not _in_range(ctx["distance_km"], expected):
                return False
        else:
            return False
    return True


def _in_range(value: float, expected: Any) -> bool:
    if isinstance(expected, dict):
        low = expected.get("min")
        high = expected.get("max")
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
        return True
    return value == expected


def _in_time_window(start_local: datetime | None, window: Any) -> bool:
    """Handles a window that wraps midnight (an off-peak 18:00-06:00 band)."""
    if start_local is None or not isinstance(window, dict):
        return False
    start = _as_time(window.get("from"))
    end = _as_time(window.get("to"))
    if start is None or end is None:
        return False
    current = start_local.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


# -- fees, caps, deposit -------------------------------------------------


def _fee_amount(fee: dict, subtotal: int, ctx: dict) -> int:
    kind = fee.get("kind") or "flat"
    if kind == "flat":
        return _int(fee.get("amountMinorUnits"))
    if kind == "percent":
        return round(subtotal * _int(fee.get("rateBps")) / 10_000)
    if kind == "distanceBand":
        distance = ctx.get("distance_km")
        if distance is None:
            return 0
        for band in fee.get("bands") or []:
            if not isinstance(band, dict):
                continue
            ceiling = band.get("maxKm")
            if ceiling is None or distance <= ceiling:
                return _int(band.get("feeMinorUnits"))
    return 0


def _apply_caps(caps: dict, total: int, breakdown: list) -> int:
    ceiling = caps.get("perBookingMinorUnits")
    if ceiling is not None and total > _int(ceiling):
        breakdown.append(
            {
                "key": "cap",
                "label": "Capped",
                "amountMinorUnits": _int(ceiling) - total,
            }
        )
        return _int(ceiling)
    return total


def _deposit(deposit: dict, total: int) -> int:
    """A deposit is one of two different things, and they clamp differently.

    A NON-refundable deposit is a prepayment — part of the price — so it can
    never exceed the total. A REFUNDABLE deposit is a damage bond: a hold that
    is returned, and routinely larger than the hire fee (a 300 bond on a 200
    tool hire). Clamping that to the total silently under-secures the asset,
    which is how a pivot testing exactly this case (#98) caught it.
    """
    if not deposit.get("enabled"):
        return 0
    value = _int(deposit.get("value"))
    amount = value if deposit.get("kind") == "flat" else round(total * value / 100)
    if deposit.get("refundable"):
        return max(0, amount)
    return min(max(0, amount), total)


# -- coercion ------------------------------------------------------------


def _int(value: Any, default: int = 0) -> int:
    """A hand-edited config can put a string or null anywhere. Coerce rather
    than 500 — validation already reported the bad value at load time."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _as_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            hours, _, minutes = value.partition(":")
            return time(int(hours), int(minutes or 0))
        except (TypeError, ValueError):
            return None
    return None


def _money_label(per: str) -> str:
    return {
        "booking": "Booking",
        "slot": "Per slot",
        "hour": "Per hour",
        "day": "Per day",
        "night": "Per night",
        "week": "Per week",
        "month": "Per month",
        "person": "Per person",
        "unit": "Per unit",
    }.get(per, "Base")
