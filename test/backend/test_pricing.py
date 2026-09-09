# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for `app.pricing.quote`, the config-driven price engine.

v1 priced every booking with one hardcoded expression in `routers/bookings.py`::

    price_minor_units = rules["priceMinorUnits"] * len(rows) * party

That is exactly one pricing model. `quote()` replaces it with a resolved
`pricing` block, and the **first thing these tests pin is that the defaults
reproduce that expression exactly**, an un-pivoted deployment must not
re-price a single booking. Everything after that is the new reach: per hour /
night / person / unit, tiers, fees, caps and deposits.

Pure arithmetic: no config file, no Supabase, no FastAPI.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config_schema import normalize, validate
from app.pricing import _fee_amount, match_tier, quote


def pricing(**overrides) -> dict:
    """A resolved `pricing` block shaped like `config_schema.DEFAULTS`."""
    block = {
        "model": "fixed",
        "currency": "EUR",
        "currencyExponent": 2,
        "rate": {"per": "slot", "amountMinorUnits": 0},
        "secondaryRate": None,
        "tiers": [],
        "chargePerPerson": True,
        "caps": {"perBookingMinorUnits": None, "perDayMinorUnits": None},
        "fees": [],
        "deposit": {"enabled": False, "kind": "percent", "value": 0, "refundable": True},
    }
    block.update(overrides)
    return block


def at(hour: int, minute: int = 0) -> datetime:
    """A local start time, for time-of-day tiers."""
    return datetime(2026, 6, 15, hour, minute, tzinfo=timezone.utc)


# ======================================================================
# v1 parity, the whole point of the default block
# ======================================================================


@pytest.mark.parametrize("slots", [1, 2, 3])
@pytest.mark.parametrize("party", [1, 2, 5])
@pytest.mark.parametrize("price", [0, 1, 500, 4500])
def test_default_pricing_reproduces_the_v1_formula_exactly(slots, party, price):
    """`priceMinorUnits * slot_count * party_size`, the expression the router
    used to inline. Every combination, so a refactor of `quote` cannot quietly
    reprice the existing catalog."""
    result = quote(
        pricing(rate={"per": "slot", "amountMinorUnits": price}),
        {"slot_count": slots, "party_size": party},
    )
    assert result["amountMinorUnits"] == price * slots * party


def test_quote_returns_the_documented_envelope():
    result = quote(pricing(rate={"per": "slot", "amountMinorUnits": 1000}), {"slot_count": 1})
    assert set(result) == {"amountMinorUnits", "currency", "depositMinorUnits", "breakdown"}
    assert result["currency"] == "EUR"
    assert result["depositMinorUnits"] == 0
    assert result["breakdown"] == [
        {"key": "base", "label": "Per slot", "amountMinorUnits": 1000}
    ]


def test_currency_comes_from_the_pricing_block():
    assert quote(pricing(currency="PLN"), {})["currency"] == "PLN"
    assert quote({}, {})["currency"] == "EUR"  # empty block still resolves


def test_an_empty_context_defaults_to_one_slot_and_one_head():
    result = quote(pricing(rate={"per": "slot", "amountMinorUnits": 2500}), {})
    assert result["amountMinorUnits"] == 2500


# ======================================================================
# rate.per, every period in RATE_PERIODS
# ======================================================================


def test_per_booking_ignores_slot_count():
    """A flat booking fee: three slots cost what one costs."""
    block = pricing(rate={"per": "booking", "amountMinorUnits": 3000})
    assert quote(block, {"slot_count": 3, "party_size": 1})["amountMinorUnits"] == 3000


def test_per_booking_still_multiplies_by_party_when_charging_per_person():
    block = pricing(rate={"per": "booking", "amountMinorUnits": 3000})
    assert quote(block, {"slot_count": 3, "party_size": 4})["amountMinorUnits"] == 12000


@pytest.mark.parametrize(
    ("minutes", "expected_units"),
    [(30, 0.5), (60, 1.0), (90, 1.5), (150, 2.5)],
)
def test_per_hour_is_fractional(minutes, expected_units):
    """90 minutes of a court is genuinely 1.5 hours, the one period that does
    not round up."""
    block = pricing(rate={"per": "hour", "amountMinorUnits": 2000})
    result = quote(block, {"duration_minutes": minutes, "slot_count": 3})
    assert result["amountMinorUnits"] == round(2000 * expected_units)


@pytest.mark.parametrize(
    ("per", "minutes", "expected_units"),
    [
        ("day", 60, 1),        # half a day of storage is a day
        ("day", 1440, 1),
        ("day", 1441, 2),
        ("night", 1440, 1),
        ("night", 1500, 2),
        ("week", 10080, 1),
        ("week", 10081, 2),
        ("month", 43200, 1),
        ("month", 43201, 2),
    ],
)
def test_whole_unit_periods_bill_by_started_unit(per, minutes, expected_units):
    block = pricing(rate={"per": per, "amountMinorUnits": 1100})
    result = quote(block, {"duration_minutes": minutes})
    assert result["amountMinorUnits"] == 1100 * expected_units


def test_a_whole_unit_period_never_bills_less_than_one_unit():
    block = pricing(rate={"per": "night", "amountMinorUnits": 9900})
    assert quote(block, {"duration_minutes": 0})["amountMinorUnits"] == 9900


@pytest.mark.parametrize("per", ["day", "night", "week", "month"])
@pytest.mark.parametrize("unit_count", [0, 1, 5, 20])
def test_a_whole_unit_period_ignores_unit_count_entirely(per, unit_count):
    """A period is a duration; a unit is a quantity. `duration_minutes` is the
    ONLY input to a day/night/week/month quantity, whatever `unit_count` is in
    the ctx belongs to a `per: "unit"` rate and must not leak onto the period
    axis."""
    block = pricing(rate={"per": per, "amountMinorUnits": 1000})
    span = {"day": 2880, "night": 2880, "week": 20160, "month": 86400}[per]
    with_count = quote(block, {"duration_minutes": span, "unit_count": unit_count})
    without = quote(block, {"duration_minutes": span})
    assert with_count["amountMinorUnits"] == without["amountMinorUnits"] == 2000
    assert with_count["breakdown"] == without["breakdown"]


@pytest.mark.parametrize("per", ["day", "night", "week", "month"])
def test_a_whole_unit_period_with_no_duration_is_one_unit_not_the_unit_count(per):
    """The minimum-one floor still comes from the span, not from `unit_count`."""
    block = pricing(rate={"per": per, "amountMinorUnits": 1000})
    assert quote(block, {"unit_count": 7})["amountMinorUnits"] == 1000
    assert quote(block, {"duration_minutes": 0, "unit_count": 7})["amountMinorUnits"] == 1000


def test_per_unit_uses_the_explicit_unit_count():
    block = pricing(rate={"per": "unit", "amountMinorUnits": 250})
    assert quote(block, {"unit_count": 12, "party_size": 1})["amountMinorUnits"] == 3000
    # ...and defaults to one unit when the caller says nothing.
    assert quote(block, {})["amountMinorUnits"] == 250


def test_per_unit_ignores_the_duration_the_way_periods_ignore_the_unit_count():
    """The other half of the split: a `unit` quantity is not derived from the
    span, so a long booking of 3 pallets is still 3 pallets."""
    block = pricing(rate={"per": "unit", "amountMinorUnits": 250})
    long_stay = quote(block, {"unit_count": 3, "duration_minutes": 40320, "party_size": 1})
    assert long_stay["amountMinorUnits"] == 750


def test_a_unit_rate_and_a_period_secondary_rate_do_not_share_unit_count():
    """Regression, warehouse pallet-space: 20 pallets at 300 each for a 28-day
    term, plus 1000 per week of storage. `unit_count` used to override the
    duration-derived period quantity, so the 20 pallets were billed as 20 WEEKS
    (6000 + 20000 = 26000) instead of 4 (6000 + 4000 = 10000).

    Both breakdown lines are pinned, not just the total: for some inputs the two
    axes trade off and the bug is invisible in the sum alone."""
    block = pricing(
        currency="PLN",
        rate={"per": "unit", "amountMinorUnits": 300},
        secondaryRate={"per": "week", "amountMinorUnits": 1000},
    )
    result = quote(block, {"unit_count": 20, "duration_minutes": 40320, "party_size": 1})

    assert result["amountMinorUnits"] == 10000
    assert result["breakdown"] == [
        {"key": "base", "label": "Per unit", "amountMinorUnits": 6000},
        {"key": "secondary", "label": "Per week", "amountMinorUnits": 4000},
    ]


def test_a_period_secondary_rate_rounds_up_independently_of_the_unit_rate():
    """Same shape, a part-week term: the secondary axis still bills by started
    week (29 days -> 5 weeks) while the unit axis stays at the pallet count."""
    block = pricing(
        rate={"per": "unit", "amountMinorUnits": 300},
        secondaryRate={"per": "week", "amountMinorUnits": 1000},
    )
    result = quote(block, {"unit_count": 20, "duration_minutes": 41760, "party_size": 1})
    assert [line["amountMinorUnits"] for line in result["breakdown"]] == [6000, 5000]
    assert result["amountMinorUnits"] == 11000


def test_per_person_counts_heads_once_and_only_once():
    """`per: "person"` already counts heads; multiplying by party again would
    square it (4 people at 1000 must be 4000, never 16000)."""
    block = pricing(rate={"per": "person", "amountMinorUnits": 1000})
    result = quote(block, {"party_size": 4, "slot_count": 3})
    assert result["amountMinorUnits"] == 4000


def test_per_person_ignores_charge_per_person_being_false_too():
    block = pricing(rate={"per": "person", "amountMinorUnits": 1000}, chargePerPerson=False)
    assert quote(block, {"party_size": 4})["amountMinorUnits"] == 4000


# ======================================================================
# chargePerPerson, the shared-unit case
# ======================================================================


@pytest.mark.parametrize("party", [1, 2, 4, 9])
def test_charge_per_person_false_means_party_does_not_multiply(party):
    """A tennis court costs the same for two players or four."""
    block = pricing(rate={"per": "slot", "amountMinorUnits": 4000}, chargePerPerson=False)
    result = quote(block, {"slot_count": 2, "party_size": party})
    assert result["amountMinorUnits"] == 8000


def test_charge_per_person_defaults_to_true_when_the_key_is_absent():
    block = pricing(rate={"per": "slot", "amountMinorUnits": 1000})
    del block["chargePerPerson"]
    assert quote(block, {"slot_count": 1, "party_size": 3})["amountMinorUnits"] == 3000


def test_weighted_person_units_replace_the_raw_head_count():
    """`booking.party.composition` lets an adult and a child cost different
    multiples of the same base rate."""
    block = pricing(rate={"per": "person", "amountMinorUnits": 1000})
    result = quote(block, {"party_size": 3, "person_units": 2.5})
    assert result["amountMinorUnits"] == 2500


# ======================================================================
# tiers, appliesWhen
# ======================================================================


def _tiered(*tiers, base=1000, **overrides):
    return pricing(rate={"per": "slot", "amountMinorUnits": base}, tiers=list(tiers), **overrides)


def test_a_matching_tier_overrides_the_base_rate_and_labels_the_breakdown():
    block = _tiered(
        {"key": "group", "label": "Group rate", "amountMinorUnits": 600,
         "appliesWhen": {"partySize": {"min": 4}}}
    )
    result = quote(block, {"slot_count": 1, "party_size": 4})
    assert result["amountMinorUnits"] == 2400  # 600 x 1 slot x 4 heads
    assert result["breakdown"][0] == {
        "key": "group", "label": "Group rate", "amountMinorUnits": 2400
    }


def test_a_non_matching_tier_leaves_the_base_rate_alone():
    block = _tiered(
        {"key": "group", "amountMinorUnits": 600, "appliesWhen": {"partySize": {"min": 4}}}
    )
    result = quote(block, {"slot_count": 1, "party_size": 2})
    assert result["amountMinorUnits"] == 2000
    assert result["breakdown"][0]["key"] == "base"


@pytest.mark.parametrize(
    ("party", "matches"),
    [(1, False), (2, True), (5, True), (6, False)],
)
def test_party_size_range_is_inclusive_at_both_ends(party, matches):
    tier = {"key": "band", "amountMinorUnits": 100, "appliesWhen": {"partySize": {"min": 2, "max": 5}}}
    assert (match_tier([tier], {"party_size": party}) is tier) is matches


def test_a_scalar_party_size_clause_is_an_exact_match():
    tier = {"key": "solo", "amountMinorUnits": 100, "appliesWhen": {"partySize": 1}}
    assert match_tier([tier], {"party_size": 1}) is tier
    assert match_tier([tier], {"party_size": 2}) is None


def test_config_order_is_the_tier_precedence_order():
    """First match wins, so the most specific tier goes first."""
    specific = {"key": "big", "amountMinorUnits": 100, "appliesWhen": {"partySize": {"min": 8}}}
    general = {"key": "any", "amountMinorUnits": 900, "appliesWhen": {}}
    assert match_tier([specific, general], {"party_size": 10}) is specific
    assert match_tier([general, specific], {"party_size": 10}) is general


@pytest.mark.parametrize(
    ("hour", "matches"),
    [(8, False), (9, True), (14, True), (16, True), (17, False), (23, False)],
)
def test_time_of_day_window_is_half_open(hour, matches):
    """[from, to), an off-peak band ending at 17:00 does not cover 17:00."""
    tier = {"key": "offpeak", "amountMinorUnits": 500,
            "appliesWhen": {"timeOfDay": {"from": "09:00", "to": "17:00"}}}
    assert (match_tier([tier], {"start_local": at(hour)}) is tier) is matches


@pytest.mark.parametrize(
    ("hour", "matches"),
    [(17, False), (18, True), (23, True), (0, True), (5, True), (6, False), (12, False)],
)
def test_a_time_of_day_window_that_wraps_midnight(hour, matches):
    """An 18:00-06:00 night band has to match on both sides of midnight."""
    tier = {"key": "night", "amountMinorUnits": 500,
            "appliesWhen": {"timeOfDay": {"from": "18:00", "to": "06:00"}}}
    assert (match_tier([tier], {"start_local": at(hour)}) is tier) is matches


def test_a_time_of_day_tier_cannot_match_without_a_local_start():
    """No start time means no evidence the window applies, fail closed."""
    tier = {"key": "night", "amountMinorUnits": 500,
            "appliesWhen": {"timeOfDay": {"from": "18:00", "to": "06:00"}}}
    assert match_tier([tier], {}) is None


def test_zone_clause_matches_a_seat_or_area_key():
    tier = {"key": "front", "amountMinorUnits": 9000, "appliesWhen": {"zone": "stalls"}}
    assert match_tier([tier], {"zone": "stalls"}) is tier
    assert match_tier([tier], {"zone": "balcony"}) is None
    assert match_tier([tier], {}) is None


@pytest.mark.parametrize(("index", "matches"), [(0, True), (1, False), (4, False)])
def test_booking_index_clause_targets_a_first_session_rate(index, matches):
    tier = {"key": "intro", "amountMinorUnits": 0, "appliesWhen": {"bookingIndex": {"max": 0}}}
    assert (match_tier([tier], {"booking_index": index}) is tier) is matches


def test_booking_index_clause_fails_closed_when_the_caller_did_not_resolve_it():
    """The router does not pass `booking_index` yet; an intro tier must not fire
    for everyone in the meantime."""
    tier = {"key": "intro", "amountMinorUnits": 0, "appliesWhen": {"bookingIndex": {"max": 0}}}
    assert match_tier([tier], {"party_size": 1}) is None


def test_subject_field_clause_matches_the_thing_the_booking_is_about():
    tier = {"key": "xl", "amountMinorUnits": 8000,
            "appliesWhen": {"subjectField": {"key": "size", "equals": "large"}}}
    assert match_tier([tier], {"subject": {"size": "large"}}) is tier
    assert match_tier([tier], {"subject": {"size": "small"}}) is None
    assert match_tier([tier], {"subject": {}}) is None
    assert match_tier([tier], {}) is None


def test_every_declared_clause_must_hold():
    tier = {"key": "combo", "amountMinorUnits": 100,
            "appliesWhen": {"zone": "stalls", "partySize": {"min": 2}}}
    assert match_tier([tier], {"zone": "stalls", "party_size": 2}) is tier
    assert match_tier([tier], {"zone": "stalls", "party_size": 1}) is None
    assert match_tier([tier], {"zone": "balcony", "party_size": 4}) is None


def test_an_unknown_applies_when_clause_fails_closed():
    """A typo must not silently widen a discount to every customer."""
    tier = {"key": "typo", "amountMinorUnits": 1,
            "appliesWhen": {"partySizes": {"min": 1}}}
    assert match_tier([tier], {"party_size": 4}) is None
    result = quote(_tiered(tier), {"slot_count": 1, "party_size": 4})
    assert result["amountMinorUnits"] == 4000  # base rate, discount not applied


def test_an_empty_applies_when_matches_everything():
    tier = {"key": "flat", "amountMinorUnits": 700}
    assert match_tier([tier], {}) is tier


def test_a_non_dict_tier_entry_is_skipped_rather_than_crashing():
    tier = {"key": "ok", "amountMinorUnits": 700}
    assert match_tier(["nonsense", None, tier], {}) is tier


# --- tier sales windows -------------------------------------------------


def _early_bird(**window):
    return {"key": "early", "amountMinorUnits": 500, **window}


def test_a_tier_is_inactive_before_its_valid_from():
    tier = _early_bird(validFrom="2026-06-01", validUntil="2026-06-30")
    assert match_tier([tier], {"now": datetime(2026, 5, 31, 23, 0, tzinfo=timezone.utc)}) is None


def test_a_tier_is_active_inside_its_sales_window():
    tier = _early_bird(validFrom="2026-06-01", validUntil="2026-06-30")
    assert match_tier([tier], {"now": datetime(2026, 6, 15, tzinfo=timezone.utc)}) is tier


@pytest.mark.parametrize("day", [1, 30])
def test_the_sales_window_is_inclusive_at_both_ends(day):
    tier = _early_bird(validFrom="2026-06-01", validUntil="2026-06-30")
    assert match_tier([tier], {"now": datetime(2026, 6, day, 12, 0, tzinfo=timezone.utc)}) is tier


def test_a_tier_is_inactive_after_its_valid_until():
    tier = _early_bird(validFrom="2026-06-01", validUntil="2026-06-30")
    assert match_tier([tier], {"now": datetime(2026, 7, 1, tzinfo=timezone.utc)}) is None


def test_an_open_ended_sales_window_only_checks_the_end_it_declares():
    assert match_tier([_early_bird(validUntil="2026-06-30")],
                      {"now": datetime(2020, 1, 1, tzinfo=timezone.utc)}) is not None
    assert match_tier([_early_bird(validFrom="2026-06-01")],
                      {"now": datetime(2020, 1, 1, tzinfo=timezone.utc)}) is None


def test_the_expired_tier_is_skipped_and_the_next_one_still_matches():
    expired = _early_bird(validUntil="2026-01-01")
    standard = {"key": "standard", "amountMinorUnits": 900}
    now = {"now": datetime(2026, 6, 15, tzinfo=timezone.utc)}
    assert match_tier([expired, standard], now) is standard


# ======================================================================
# secondary rate
# ======================================================================


def test_a_secondary_rate_adds_an_independent_axis():
    """e.g. a per-booking handling charge on top of a per-slot rate."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        secondaryRate={"per": "booking", "amountMinorUnits": 250},
    )
    result = quote(block, {"slot_count": 2, "party_size": 1})
    assert result["amountMinorUnits"] == 2250
    assert result["breakdown"][1] == {
        "key": "secondary", "label": "Booking", "amountMinorUnits": 250
    }


def test_a_zero_or_absent_secondary_rate_adds_nothing():
    base = pricing(rate={"per": "slot", "amountMinorUnits": 1000})
    assert quote(base, {"slot_count": 1})["amountMinorUnits"] == 1000
    zeroed = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        secondaryRate={"per": "booking", "amountMinorUnits": 0},
    )
    result = quote(zeroed, {"slot_count": 1})
    assert result["amountMinorUnits"] == 1000
    assert len(result["breakdown"]) == 1


# ======================================================================
# fees
# ======================================================================


def test_a_flat_fee_is_added_once():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 5000},
        fees=[{"key": "clean", "label": "Cleaning", "kind": "flat", "amountMinorUnits": 1500}],
    )
    result = quote(block, {"slot_count": 2, "party_size": 1})
    assert result["amountMinorUnits"] == 11500
    assert result["breakdown"][-1] == {
        "key": "clean", "label": "Cleaning", "amountMinorUnits": 1500
    }


def test_a_percent_fee_is_basis_points_of_the_running_subtotal():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        fees=[{"key": "service", "kind": "percent", "rateBps": 1250}],
    )
    result = quote(block, {"slot_count": 1, "party_size": 1})
    assert result["amountMinorUnits"] == 11250  # 12.5% of 10000


def test_fees_compound_in_declaration_order():
    """A percent fee declared after a flat one is charged on the flat one too,
    order in the config is the order of operations."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        fees=[
            {"key": "clean", "kind": "flat", "amountMinorUnits": 2000},
            {"key": "service", "kind": "percent", "rateBps": 1000},
        ],
    )
    result = quote(block, {"slot_count": 1})
    assert result["amountMinorUnits"] == 13200  # (10000 + 2000) + 10% of 12000


@pytest.mark.parametrize(
    ("distance", "expected_fee"),
    [(0, 0), (5, 0), (5.5, 500), (10, 500), (11, 1500), (400, 1500)],
)
def test_a_distance_band_fee_picks_the_first_band_that_fits(distance, expected_fee):
    block = pricing(
        rate={"per": "booking", "amountMinorUnits": 3000},
        fees=[
            {
                "key": "travel",
                "kind": "distanceBand",
                "bands": [
                    {"maxKm": 5, "feeMinorUnits": 0},
                    {"maxKm": 10, "feeMinorUnits": 500},
                    {"maxKm": None, "feeMinorUnits": 1500},
                ],
            }
        ],
    )
    result = quote(block, {"party_size": 1, "distance_km": distance})
    assert result["amountMinorUnits"] == 3000 + expected_fee


def test_a_distance_band_fee_is_skipped_when_no_distance_is_known():
    block = pricing(
        rate={"per": "booking", "amountMinorUnits": 3000},
        fees=[{"key": "travel", "kind": "distanceBand",
               "bands": [{"maxKm": None, "feeMinorUnits": 1500}]}],
    )
    result = quote(block, {"party_size": 1})
    assert result["amountMinorUnits"] == 3000
    assert len(result["breakdown"]) == 1


def test_a_fee_with_an_applies_when_only_charges_when_it_matches():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        fees=[{"key": "large_party", "kind": "flat", "amountMinorUnits": 2000,
               "appliesWhen": {"partySize": {"min": 6}}}],
    )
    assert quote(block, {"slot_count": 1, "party_size": 2})["amountMinorUnits"] == 2000
    assert quote(block, {"slot_count": 1, "party_size": 6})["amountMinorUnits"] == 8000


def test_a_zero_valued_fee_leaves_no_breakdown_line():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        fees=[{"key": "nothing", "kind": "flat", "amountMinorUnits": 0}],
    )
    assert len(quote(block, {"slot_count": 1})["breakdown"]) == 1


# ======================================================================
# caps
# ======================================================================


def test_a_per_booking_cap_clamps_the_total_and_records_the_discount():
    block = pricing(
        rate={"per": "day", "amountMinorUnits": 5000},
        caps={"perBookingMinorUnits": 20000, "perDayMinorUnits": None},
    )
    result = quote(block, {"duration_minutes": 1440 * 10, "party_size": 1})
    assert result["amountMinorUnits"] == 20000  # 10 days x 5000 = 50000, capped
    assert result["breakdown"][-1] == {
        "key": "cap", "label": "Capped", "amountMinorUnits": -30000
    }


def test_a_cap_above_the_total_changes_nothing():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        caps={"perBookingMinorUnits": 99999, "perDayMinorUnits": None},
    )
    result = quote(block, {"slot_count": 2, "party_size": 1})
    assert result["amountMinorUnits"] == 2000
    assert all(line["key"] != "cap" for line in result["breakdown"])


def test_a_null_cap_is_no_cap():
    block = pricing(rate={"per": "slot", "amountMinorUnits": 1000},
                    caps={"perBookingMinorUnits": None, "perDayMinorUnits": None})
    assert quote(block, {"slot_count": 50})["amountMinorUnits"] == 50000


def test_the_cap_applies_after_fees_not_before():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 8000},
        fees=[{"key": "clean", "kind": "flat", "amountMinorUnits": 5000}],
        caps={"perBookingMinorUnits": 10000, "perDayMinorUnits": None},
    )
    assert quote(block, {"slot_count": 1, "party_size": 1})["amountMinorUnits"] == 10000


# ======================================================================
# deposit
# ======================================================================


def test_no_deposit_unless_it_is_enabled():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": False, "kind": "percent", "value": 50, "refundable": True},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 0


@pytest.mark.parametrize(("percent", "expected"), [(0, 0), (10, 1000), (50, 5000), (100, 10000)])
def test_a_percent_deposit_is_a_share_of_the_final_total(percent, expected):
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": "percent", "value": percent, "refundable": True},
    )
    result = quote(block, {"slot_count": 1, "party_size": 1})
    assert result["amountMinorUnits"] == 10000
    assert result["depositMinorUnits"] == expected


def test_a_flat_deposit_is_taken_as_declared():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": "flat", "value": 2500, "refundable": False},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 2500


# ----------------------------------------------------------------------
# `refundable` selects between two different things
#
# A NON-refundable deposit is a PREPAYMENT, part of the price, so it can
# never exceed the total. A REFUNDABLE deposit is a damage BOND: a hold that
# comes back, and routinely larger than the hire fee (a 300 bond on a 200 tool
# hire). Clamping a bond to the total silently under-secures the asset, which
# is what a hire pivot with a 30000 bond on a 20000 hire exposed.
# ----------------------------------------------------------------------


def test_a_non_refundable_percent_deposit_over_a_hundred_is_clamped_to_the_total():
    """A prepayment of 150% is nonsense, you cannot pre-pay more than the price."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": "percent", "value": 150, "refundable": False},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 10000


def test_a_non_refundable_flat_deposit_larger_than_the_booking_is_clamped_to_the_total():
    """Never ask for more up front than the booking costs."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 1000},
        deposit={"enabled": True, "kind": "flat", "value": 9999, "refundable": False},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 1000


@pytest.mark.parametrize(
    ("percent", "expected"), [(0, 0), (10, 1000), (50, 5000), (100, 10000)]
)
def test_a_non_refundable_percent_deposit_under_the_total_is_untouched_by_the_clamp(
    percent, expected
):
    """The clamp only ever binds above 100%, every share at or below it is
    the plain arithmetic, identical to the bond branch."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": "percent", "value": percent, "refundable": False},
    )
    assert quote(block, {"slot_count": 1, "party_size": 1})["depositMinorUnits"] == expected


def test_a_refundable_flat_bond_may_exceed_the_total():
    """The motivating case: a 30000 bond secures a 20000 tool hire. Clamping it
    to 20000 would hand back a hold worth less than the asset."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 20000},
        deposit={"enabled": True, "kind": "flat", "value": 30000, "refundable": True},
    )
    result = quote(block, {"slot_count": 1, "party_size": 1})
    assert result["amountMinorUnits"] == 20000
    assert result["depositMinorUnits"] == 30000


def test_a_refundable_percent_bond_over_a_hundred_is_not_clamped():
    """150% of the hire is a legitimate bond, so it prices as 1.5x the total."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": "percent", "value": 150, "refundable": True},
    )
    result = quote(block, {"slot_count": 1})
    assert result["amountMinorUnits"] == 10000
    assert result["depositMinorUnits"] == 15000


@pytest.mark.parametrize("refundable", [True, False])
@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("flat", -5000),
        ("percent", -50),
        ("flat", "nonsense"),
        ("percent", "nonsense"),
        ("flat", None),
        ("percent", None),
    ],
)
def test_neither_branch_can_produce_a_negative_deposit(kind, value, refundable):
    """A negative or unparseable `value` floors at 0 on both branches, a
    hand-edited config must never hand money back through the deposit field."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": kind, "value": value, "refundable": refundable},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 0


@pytest.mark.parametrize("refundable", [True, False])
@pytest.mark.parametrize("kind", ["flat", "percent"])
def test_a_disabled_deposit_is_zero_whichever_kind_it_would_have_been(kind, refundable):
    """`enabled` is checked before `refundable`, the bond branch is not a way
    around the off switch."""
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        deposit={"enabled": True, "kind": kind, "value": 30000, "refundable": refundable},
    )
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] > 0

    block["deposit"] = dict(block["deposit"], enabled=False)
    assert quote(block, {"slot_count": 1})["depositMinorUnits"] == 0


def test_the_refundable_default_is_true_so_an_unnamed_deposit_is_a_bond():
    """This is a behavioural default someone could flip by accident: because
    `DEFAULTS["pricing"]["deposit"]["refundable"]` is True, a config that turns
    a deposit on without naming `refundable` gets the UNCLAMPED bond branch."""
    assert normalize({})["pricing"]["deposit"]["refundable"] is True

    resolved = normalize({"pricing": {"deposit": {"enabled": True, "kind": "flat", "value": 30000}}})
    assert validate(resolved) == []
    assert resolved["pricing"]["deposit"]["refundable"] is True

    block = dict(resolved["pricing"], rate={"per": "slot", "amountMinorUnits": 20000})
    assert quote(block, {"slot_count": 1, "party_size": 1})["depositMinorUnits"] == 30000


def test_the_deposit_is_derived_from_the_capped_total_not_the_raw_one():
    block = pricing(
        rate={"per": "slot", "amountMinorUnits": 10000},
        caps={"perBookingMinorUnits": 4000, "perDayMinorUnits": None},
        deposit={"enabled": True, "kind": "percent", "value": 50, "refundable": True},
    )
    result = quote(block, {"slot_count": 5, "party_size": 1})
    assert result["amountMinorUnits"] == 4000
    assert result["depositMinorUnits"] == 2000


# ======================================================================
# robustness, a hand-edited config must not 500 the booking path
# ======================================================================


def test_a_string_amount_is_coerced_rather_than_crashing():
    block = pricing(rate={"per": "slot", "amountMinorUnits": "1500"})
    assert quote(block, {"slot_count": 2, "party_size": 1})["amountMinorUnits"] == 3000


def test_a_null_amount_prices_at_zero():
    block = pricing(rate={"per": "slot", "amountMinorUnits": None})
    assert quote(block, {"slot_count": 3, "party_size": 2})["amountMinorUnits"] == 0


def test_the_total_is_never_negative():
    block = pricing(rate={"per": "slot", "amountMinorUnits": 100},
                    fees=[{"key": "credit", "kind": "flat", "amountMinorUnits": -9999}])
    assert quote(block, {"slot_count": 1})["amountMinorUnits"] == 0


def test_a_non_dict_fee_entry_is_skipped():
    block = pricing(rate={"per": "slot", "amountMinorUnits": 1000},
                    fees=["nonsense", None, {"key": "ok", "kind": "flat", "amountMinorUnits": 100}])
    assert quote(block, {"slot_count": 1})["amountMinorUnits"] == 1100


def test_an_unknown_rate_period_falls_back_to_a_quantity_of_one():
    block = pricing(rate={"per": "fortnight", "amountMinorUnits": 700})
    assert quote(block, {"slot_count": 4, "party_size": 1})["amountMinorUnits"] == 700


# ======================================================================
# unknown fee kinds, why validate() now rejects them
# ======================================================================


def test_a_typo_fee_kind_contributes_nothing_which_is_why_validate_rejects_it():
    """`kind: "percentage"` is a plausible hand-edit for "percent". `_fee_amount`
    matches no branch and falls through to 0, so the fee disappears from every
    quote, no error, no breakdown line, just a permanently under-charged
    booking. That silence is the reason `config_schema.validate` now makes it a
    load-time error (see `test_config_schema.test_an_unknown_fee_kind_...`)."""
    typo = {"key": "service", "label": "Service fee", "kind": "percentage", "rateBps": 1250}

    assert _fee_amount(typo, 10_000, {}) == 0

    block = pricing(rate={"per": "slot", "amountMinorUnits": 10_000}, fees=[typo])
    result = quote(block, {"slot_count": 1, "party_size": 1})
    assert result["amountMinorUnits"] == 10_000  # the fee simply vanished
    assert [line["key"] for line in result["breakdown"]] == ["base"]

    problems = validate(normalize({"pricing": {"fees": [typo]}}))
    assert any("pricing.fees[0].kind" in problem for problem in problems), problems


@pytest.mark.parametrize("kind", ["percentage", "distance_band", "PERCENT", "flat "])
def test_every_unrecognised_fee_kind_is_silently_free(kind):
    """One parametrized proof that *no* unknown kind fails loudly at quote time,
    the validator is the only thing standing between a typo and a lost fee."""
    fee = {"key": "x", "label": "X", "kind": kind, "amountMinorUnits": 5000, "rateBps": 1000}
    assert _fee_amount(fee, 10_000, {}) == 0


@pytest.mark.parametrize("kind", ["", None])
def test_a_falsy_fee_kind_is_charged_as_flat_but_still_rejected_at_load(kind):
    """`_fee_amount` does `fee.get("kind") or "flat"`, so an empty/null kind
    prices as flat, while `validate` reads `fee.get("kind", "flat")` and reports
    it. The validator being the stricter of the two is the safe direction, a
    config that means "flat" should say so."""
    fee = {"key": "x", "label": "X", "kind": kind, "amountMinorUnits": 5000}
    assert _fee_amount(fee, 10_000, {}) == 5000
    assert any(
        "pricing.fees[0].kind" in problem
        for problem in validate(normalize({"pricing": {"fees": [fee]}}))
    )


def test_an_omitted_fee_kind_still_means_flat():
    """The default is real behaviour, not an accident: a fee with no `kind` is a
    flat amount, at quote time and in the validator alike."""
    fee = {"key": "clean", "label": "Cleaning", "amountMinorUnits": 1500}
    assert _fee_amount(fee, 10_000, {}) == 1500
    assert validate(normalize({"pricing": {"fees": [fee]}})) == []
