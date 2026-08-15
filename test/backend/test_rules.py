"""Unit tests for the data-driven rules engine (backend/app/rules.py).

Every assertion here is about *config-driven* behaviour: the same code path
must produce a different verdict when the number in `domain.config.json`
changes.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.rules import (
    RuleViolation,
    check_cancellation_window,
    check_capacity,
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
        (0, 5, 0, False),   # maxBookingsPerSlot=0 closes bookings entirely
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
