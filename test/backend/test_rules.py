"""Unit tests for the data-driven rules engine (backend/app/rules.py).

Every assertion here is about *config-driven* behaviour: the same code path
must produce a different verdict when the number in `domain.config.json`
changes.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.rules import RuleViolation, check_cancellation_window, check_capacity


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
