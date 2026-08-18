"""Unit tests for the data-driven rules engine (backend/app/rules.py).

Every assertion here is about *config-driven* behaviour: the same code path
must produce a different verdict when the number in `domain.config.json`
changes.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config_schema import normalize, validate
from app.config import get_config
from app.rules import (
    RULES,
    UNDISPATCHED,
    RuleViolation,
    _advance_window,
    _capacity,
    _lead_time,
    apply_rules,
    check_cancellation_window,
    check_capacity,
    effective_auto_approve,
    effective_service_config,
    effective_service_pricing,
    effective_service_rules,
    within_cutoff,
)


def in_hours(hours: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# --------------------------------------------------------------------
# cancellationWindowHours
# --------------------------------------------------------------------


def test_cancellation_allowed_well_outside_the_window(domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    check_cancellation_window(in_hours(72))  # must not raise


def test_cancellation_blocked_inside_the_window(domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    with pytest.raises(RuleViolation) as excinfo:
        check_cancellation_window(in_hours(1))
    assert "24" in str(excinfo.value)


def test_cancellation_blocked_for_a_slot_in_the_past(domain_config):
    domain_config(rules={"cancellationWindowHours": 24})
    with pytest.raises(RuleViolation):
        check_cancellation_window(in_hours(-5))


@pytest.mark.parametrize(
    ("hours_ahead", "allowed"),
    [
        (24.02, True),   # just outside the 24h window
        (23.98, False),  # just inside it
    ],
)
def test_cancellation_window_boundary(domain_config, hours_ahead, allowed):
    domain_config(rules={"cancellationWindowHours": 24})
    if allowed:
        check_cancellation_window(in_hours(hours_ahead))
    else:
        with pytest.raises(RuleViolation):
            check_cancellation_window(in_hours(hours_ahead))


def test_cancellation_window_value_comes_from_the_config(domain_config):
    slot = in_hours(5)

    domain_config(rules={"cancellationWindowHours": 24})
    with pytest.raises(RuleViolation):
        check_cancellation_window(slot)

    domain_config(rules={"cancellationWindowHours": 2})
    check_cancellation_window(slot)  # same slot, looser config -> allowed

    domain_config(rules={"cancellationWindowHours": 0})
    check_cancellation_window(in_hours(0.01))  # window disabled entirely


def test_cancellation_window_message_quotes_the_configured_value(domain_config):
    domain_config(rules={"cancellationWindowHours": 48})
    with pytest.raises(RuleViolation) as excinfo:
        check_cancellation_window(in_hours(1))
    assert "48h" in str(excinfo.value)


def test_cancellation_window_handles_a_naive_datetime(domain_config):
    """A naive timestamp (no offset) is coerced to UTC by parse_ts, so a
    far-future naive slot is safely outside the window (no TypeError)."""
    domain_config(rules={"cancellationWindowHours": 24})
    naive = datetime.now() + timedelta(hours=72)
    check_cancellation_window(naive)  # 72h out, 24h window -> no raise


# --------------------------------------------------------------------
# maxBookingsPerSlot / capacity
# --------------------------------------------------------------------


def test_capacity_allows_a_free_slot(domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    check_capacity(booked_count=0, capacity=1)


def test_capacity_blocks_a_full_slot(domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    with pytest.raises(RuleViolation) as excinfo:
        check_capacity(booked_count=1, capacity=1)
    assert "fully booked" in str(excinfo.value)


@pytest.mark.parametrize(
    ("max_per_slot", "capacity", "booked", "allowed"),
    [
        (5, 3, 2, True),    # min(3, 5) = 3 -> room for one more
        (5, 3, 3, False),   # the row's capacity is the binding limit
        (2, 10, 1, True),   # min(10, 2) = 2
        (2, 10, 2, False),  # the config is the binding limit
        (1, 1, 0, True),
    ],
)
def test_capacity_uses_min_of_row_capacity_and_config(
    domain_config, max_per_slot, capacity, booked, allowed
):
    domain_config(rules={"maxBookingsPerSlot": max_per_slot})
    if allowed:
        check_capacity(booked_count=booked, capacity=capacity)
    else:
        with pytest.raises(RuleViolation):
            check_capacity(booked_count=booked, capacity=capacity)


def test_a_zero_max_bookings_per_slot_config_is_rejected_at_load(domain_config):
    """`maxBookingsPerSlot: 0` closes bookings entirely — an unshippable config.
    v2's validator refuses to load it, so it can no longer be smuggled in through
    a config file (which is why the arithmetic below is asserted directly)."""
    config = normalize(domain_config())
    config["timing"]["maxBookingsPerSlot"] = 0
    problems = validate(config)
    assert any("timing.maxBookingsPerSlot" in problem for problem in problems), problems


def test_capacity_validator_still_takes_the_min_when_handed_a_zero(domain_config):
    """The `min(capacity, max_per_slot)` arithmetic is unchanged: a 0 ceiling
    blocks even an empty slot. Called directly, because a config declaring 0 no
    longer loads."""
    domain_config()
    with pytest.raises(RuleViolation):
        _capacity(0, {"booked_count": 0, "capacity": 5})


def test_capacity_limit_follows_the_config_file(domain_config):
    domain_config(rules={"maxBookingsPerSlot": 1})
    with pytest.raises(RuleViolation):
        check_capacity(booked_count=1, capacity=10)

    domain_config(rules={"maxBookingsPerSlot": 4})
    check_capacity(booked_count=1, capacity=10)  # same numbers, wider config


def test_capacity_blocks_an_oversold_slot(domain_config):
    domain_config(rules={"maxBookingsPerSlot": 2})
    with pytest.raises(RuleViolation):
        check_capacity(booked_count=7, capacity=2)


# --------------------------------------------------------------------
# effective_service_rules — per-service value, else global, else hard default
# --------------------------------------------------------------------


def test_service_column_wins_over_global(domain_config):
    """A service's own column beats the domain.config.json global default."""
    domain_config(rules={"slotDurationMinutes": 30, "cancellationWindowHours": 24})
    service = {"slot_duration_minutes": 45, "cancellation_cutoff_hours": 12}
    rules = effective_service_rules(service)
    assert rules["slotDurationMinutes"] == 45
    assert rules["cancellationCutoffHours"] == 12


def test_global_config_used_when_service_column_is_null(domain_config):
    """A null service column falls back to the global config default."""
    domain_config(rules={"slotDurationMinutes": 60, "cancellationWindowHours": 36})
    service = {"slot_duration_minutes": None, "cancellation_cutoff_hours": None}
    rules = effective_service_rules(service)
    assert rules["slotDurationMinutes"] == 60
    assert rules["cancellationCutoffHours"] == 36


def test_hard_default_used_when_no_service_and_no_global(domain_config):
    """Keys with no global mapping fall to the hard default when the service is
    absent — min/max slots (1/1), price (0), currency (EUR), model (one_to_one)."""
    domain_config()  # default fixture config has no min/max/price/currency keys
    rules = effective_service_rules(None)
    assert rules["minSlotsPerBooking"] == 1
    assert rules["maxSlotsPerBooking"] == 1
    assert rules["priceMinorUnits"] == 0
    assert rules["currency"] == "EUR"
    assert rules["bookingModel"] == "one_to_one"


def test_service_columns_populate_all_camelcase_keys(domain_config):
    domain_config()
    service = {
        "slot_duration_minutes": 1440,
        "cancellation_cutoff_hours": 48,
        "min_slots_per_booking": 1,
        "max_slots_per_booking": 7,
        "price_minor_units": 4500,
        "currency": "PLN",
        "booking_model": "unit_selection",
    }
    rules = effective_service_rules(service)
    assert rules == {
        "slotDurationMinutes": 1440,
        "cancellationCutoffHours": 48,
        "minSlotsPerBooking": 1,
        "maxSlotsPerBooking": 7,
        "priceMinorUnits": 4500,
        "currency": "PLN",
        "bookingModel": "unit_selection",
    }


# --------------------------------------------------------------------
# within_cutoff — the change/cancel closing point (no clock guessing)
# --------------------------------------------------------------------

_START = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)


def test_within_cutoff_false_well_before_the_window():
    now = _START - timedelta(hours=48)  # 48h out, 24h cutoff -> still open
    assert within_cutoff(_START, 24, now=now) is False


def test_within_cutoff_true_inside_the_window():
    now = _START - timedelta(hours=1)  # 1h out, 24h cutoff -> closed
    assert within_cutoff(_START, 24, now=now) is True


def test_within_cutoff_boundary_is_inclusive():
    now = _START - timedelta(hours=24)  # exactly at the boundary
    assert within_cutoff(_START, 24, now=now) is True


def test_within_cutoff_after_start_is_true():
    now = _START + timedelta(hours=1)
    assert within_cutoff(_START, 24, now=now) is True


def test_within_cutoff_accepts_iso_string():
    now = _START - timedelta(hours=48)
    assert within_cutoff(_START.isoformat(), 24, now=now) is False


# --------------------------------------------------------------------
# effective_service_config — a service overrides a whole v2 block
# --------------------------------------------------------------------


def test_effective_service_config_returns_every_overridable_block(domain_config):
    domain_config()
    resolved = effective_service_config(None)
    for block in (
        "booking",
        "pricing",
        "payments",
        "inventory",
        "location",
        "timing",
        "recurrence",
        "entitlements",
        "capabilities",
    ):
        assert block in resolved, block
    # Presentation stays global — a service may not re-word the app.
    for block in ("terms", "copy", "theme"):
        assert block not in resolved


def test_service_metadata_block_overrides_the_global_block(domain_config):
    """This is what makes a marketplace work: two businesses on one deployment
    price and schedule differently without touching domain.config.json."""
    domain_config(timing={"cancellationWindowHours": 24, "leadTimeMinutes": 0})
    service = {"metadata": {"timing": {"leadTimeMinutes": 90}}}
    resolved = effective_service_config(service)
    assert resolved["timing"]["leadTimeMinutes"] == 90
    # ...and the keys it did NOT declare still come from the global block.
    assert resolved["timing"]["cancellationWindowHours"] == 24


def test_service_metadata_merges_deeply_and_replaces_lists(domain_config):
    domain_config()
    service = {
        "metadata": {
            "pricing": {
                "rate": {"per": "hour"},
                "fees": [{"key": "clean", "kind": "flat", "amountMinorUnits": 500}],
            }
        }
    }
    pricing = effective_service_config(service)["pricing"]
    assert pricing["rate"]["per"] == "hour"
    # sibling key inside the same nested dict survives the merge
    assert pricing["rate"]["amountMinorUnits"] == 0
    assert pricing["fees"] == [{"key": "clean", "kind": "flat", "amountMinorUnits": 500}]


def test_effective_service_config_does_not_mutate_the_cached_config(domain_config):
    """A per-service override must not leak into the process-wide config."""
    domain_config()
    effective_service_config({"metadata": {"pricing": {"currency": "PLN"}}})
    assert effective_service_config(None)["pricing"]["currency"] == "EUR"


# --------------------------------------------------------------------
# effective_service_pricing — legacy columns fold into the pricing block
# --------------------------------------------------------------------


def test_service_price_columns_win_over_the_global_pricing_block(domain_config):
    """An un-pivoted service prices exactly as it did in v1: its own
    `price_minor_units`/`currency` columns are the source of truth."""
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 100}})
    pricing = effective_service_pricing({"price_minor_units": 4500, "currency": "PLN"})
    assert pricing["rate"]["amountMinorUnits"] == 4500
    assert pricing["currency"] == "PLN"
    # per is untouched by the column fold-in
    assert pricing["rate"]["per"] == "slot"


def test_global_pricing_applies_when_the_service_columns_are_null(domain_config):
    domain_config(pricing={"currency": "GBP", "rate": {"per": "hour", "amountMinorUnits": 250}})
    pricing = effective_service_pricing({"price_minor_units": None, "currency": None})
    assert pricing["rate"]["amountMinorUnits"] == 250
    assert pricing["currency"] == "GBP"
    assert pricing["rate"]["per"] == "hour"


def test_declared_metadata_pricing_beats_the_legacy_columns(domain_config):
    """Opting into the richer model overrides the columns rather than fighting
    them — otherwise a service could never move off per-slot pricing."""
    domain_config()
    service = {
        "price_minor_units": 4500,
        "currency": "PLN",
        "metadata": {
            "pricing": {"currency": "USD", "rate": {"per": "night", "amountMinorUnits": 9900}}
        },
    }
    pricing = effective_service_pricing(service)
    assert pricing["rate"]["amountMinorUnits"] == 9900
    assert pricing["currency"] == "USD"
    assert pricing["rate"]["per"] == "night"


def test_partial_metadata_pricing_still_lets_the_columns_supply_the_rest(domain_config):
    """`metadata.pricing` that declares only `per` leaves the amount/currency to
    the columns — a service can change the unit without restating its price."""
    domain_config()
    service = {
        "price_minor_units": 4500,
        "currency": "PLN",
        "metadata": {"pricing": {"rate": {"per": "day"}}},
    }
    pricing = effective_service_pricing(service)
    assert pricing["rate"]["per"] == "day"
    assert pricing["rate"]["amountMinorUnits"] == 4500
    assert pricing["currency"] == "PLN"


def test_service_rule_map_reads_price_from_the_config_when_the_column_is_null(domain_config):
    """v2 gave price/currency/min/max a global config path; v1 had none."""
    domain_config(
        pricing={"currency": "CZK", "rate": {"per": "slot", "amountMinorUnits": 777}},
        booking={"duration": {"mode": "fixed", "minUnits": 2, "maxUnits": 6, "incrementUnits": 1}},
    )
    rules = effective_service_rules(None)
    assert rules["priceMinorUnits"] == 777
    assert rules["currency"] == "CZK"
    assert rules["minSlotsPerBooking"] == 2
    assert rules["maxSlotsPerBooking"] == 6


# --------------------------------------------------------------------
# effective_auto_approve — timing.confirmation is the new global default
# --------------------------------------------------------------------


def test_auto_approve_defaults_to_true_for_instant_confirmation(domain_config):
    domain_config(timing={"confirmation": "instant"})
    assert effective_auto_approve(None) is True
    assert effective_auto_approve({"metadata": {}}) is True


def test_request_approve_confirmation_flips_the_global_default(domain_config):
    """A niche whose whole model is request-then-approve sets it once in the
    pivot file instead of on every service."""
    domain_config(timing={"confirmation": "request_approve"})
    assert effective_auto_approve(None) is False


def test_service_metadata_auto_approve_overrides_the_config(domain_config):
    domain_config(timing={"confirmation": "request_approve"})
    assert effective_auto_approve({"metadata": {"auto_approve": True}}) is True

    domain_config(timing={"confirmation": "instant"})
    assert effective_auto_approve({"metadata": {"auto_approve": False}}) is False


def test_service_metadata_timing_block_can_flip_auto_approve(domain_config):
    """The per-service block override reaches confirmation too, so one business
    on a marketplace can screen requests while the rest confirm instantly."""
    domain_config(timing={"confirmation": "instant"})
    service = {"metadata": {"timing": {"confirmation": "request_approve"}}}
    assert effective_auto_approve(service) is False


# --------------------------------------------------------------------
# timing.leadTimeMinutes -> RULES["booking.create"] (rules._lead_time)
# --------------------------------------------------------------------
#
# Minimum notice. It was declared in the config tree but read by nothing until
# `booking.create` started dispatching it, so these tests are what keeps it
# wired: the validator itself, and the registry entry that makes the router
# call it.


def test_lead_time_of_zero_disables_the_rule():
    """0 is the "off" value, same convention as bufferMinutes — a slot starting
    right now, or one that already started, is not this rule's problem."""
    _lead_time(0, {"slot_starts_at": in_hours(0)})
    _lead_time(0, {"slot_starts_at": in_hours(-5)})
    _lead_time(None, {"slot_starts_at": in_hours(0)})


def test_lead_time_rejects_a_start_inside_the_notice_window():
    with pytest.raises(RuleViolation) as excinfo:
        _lead_time(120, {"slot_starts_at": in_hours(1)})
    message = str(excinfo.value)
    assert "120" in message
    # Vocabulary comes from the config, never hardcoded: terms.slot is "Window"
    # in the fixture pivot file.
    assert "window" in message


def test_lead_time_allows_a_start_outside_the_notice_window():
    _lead_time(120, {"slot_starts_at": in_hours(3)})  # must not raise


def test_lead_time_rejects_a_start_already_in_the_past():
    with pytest.raises(RuleViolation):
        _lead_time(30, {"slot_starts_at": in_hours(-1)})


@pytest.mark.parametrize(("minutes", "hours_out", "blocked"), [
    (60, 0.25, True),
    (60, 2, False),
    (1440, 12, True),
    (1440, 48, False),
])
def test_lead_time_is_driven_by_the_configured_number(minutes, hours_out, blocked, domain_config):
    """Same code path, different verdict per config value — dispatched through
    `apply_rules`, exactly as the router calls it."""
    domain_config(timing={"leadTimeMinutes": minutes})
    ctx = {"slot_starts_at": in_hours(hours_out)}
    if blocked:
        with pytest.raises(RuleViolation):
            apply_rules("booking.create", ctx)
    else:
        apply_rules("booking.create", ctx)


def test_booking_create_is_a_no_op_on_a_config_that_never_mentions_lead_time(domain_config):
    domain_config()  # the untouched fixture: no `timing` block at all
    assert get_config()["timing"]["leadTimeMinutes"] == 0
    apply_rules("booking.create", {"slot_starts_at": in_hours(0.01)})  # must not raise


def test_lead_time_declared_on_the_v1_rules_path_is_not_enforced(domain_config):
    """`leadTimeMinutes` is v2-only: it is not one of the five aliased keys, so
    only `timing.leadTimeMinutes` enforces. Pinned so the footgun is visible if
    someone declares it under the deprecated `rules` block."""
    domain_config(rules={"leadTimeMinutes": 120})
    assert get_config()["timing"]["leadTimeMinutes"] == 0
    apply_rules("booking.create", {"slot_starts_at": in_hours(0.1)})  # must not raise


# --------------------------------------------------------------------
# the registry itself: what is dispatched, and what deliberately is not
# --------------------------------------------------------------------


def test_booking_create_dispatches_exactly_the_lead_time_rule():
    assert RULES["booking.create"] == {"leadTimeMinutes": _lead_time}


def test_max_bookings_per_slot_is_not_dispatched_on_any_event():
    """Regression guard. Capacity is enforced upstream by `_resolve_selection` +
    the `slot_occupancy` view, which understand party size and multi-slot holds.
    Re-registering `_capacity` here would re-apply `min(capacity, maxPerSlot)`
    and cap every shared-capacity slot at the shipped default of 1."""
    for event, mapping in RULES.items():
        assert "maxBookingsPerSlot" not in mapping, event


def test_the_undispatched_registry_is_exactly_the_two_known_keys():
    assert UNDISPATCHED == {
        "advanceBookingWindowDays": _advance_window,
        "maxBookingsPerSlot": _capacity,
    }


def test_undispatched_keys_are_disjoint_from_everything_dispatched():
    dispatched = {key for mapping in RULES.values() for key in mapping}
    assert dispatched.isdisjoint(UNDISPATCHED)


def test_dispatching_capacity_would_cap_a_shared_slot_at_the_global_default():
    """The arithmetic that makes the exclusion necessary: with the shipped
    `maxBookingsPerSlot: 1`, a capacity-8 slot that already holds 4 heads reads
    as full, so a group booking is refused."""
    with pytest.raises(RuleViolation):
        _capacity(1, {"booked_count": 4, "capacity": 8})
    _capacity(8, {"booked_count": 4, "capacity": 8})  # the real ceiling: no raise


def test_apply_rules_skips_an_event_with_no_validators():
    for event in ("booking.approve", "booking.cancel", "inventory.reserve",
                  "inventory.return", "payment.due"):
        apply_rules(event, {})  # must not raise, must not need any ctx


def test_apply_rules_on_an_unknown_event_is_a_no_op():
    apply_rules("booking.teleport", {})
