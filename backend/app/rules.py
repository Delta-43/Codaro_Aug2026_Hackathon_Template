"""Data-driven rules engine. Each rule is one config key (domain.config.json
`rules`) plus one small validator here — a new constraint should never need
a refactor, just a new entry in RULES and a key in the config."""
from datetime import datetime, timezone

from app.config import get_config


class RuleViolation(Exception):
    pass


def check_cancellation_window(slot_starts_at: datetime) -> None:
    hours = get_config()["rules"]["cancellationWindowHours"]
    remaining = (slot_starts_at - datetime.now(timezone.utc)).total_seconds() / 3600
    if remaining < hours:
        raise RuleViolation(
            f"Cannot cancel/reschedule within {hours}h of the slot start."
        )


def check_capacity(booked_count: int, capacity: int) -> None:
    max_per_slot = get_config()["rules"]["maxBookingsPerSlot"]
    if booked_count >= min(capacity, max_per_slot):
        raise RuleViolation("This slot is fully booked.")


# TODO: add advanceBookingWindowDays / bufferMinutes validators as booking
# logic is implemented.
