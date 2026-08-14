"""Data-driven rules engine.

Each business rule is one key in ``domain.config.json`` `rules` plus one
small validator here, wired into an event-keyed registry. A new constraint
never needs a refactor — just a new config key, a ~4-line validator and one
registry entry. Deleting a key from the config disables its rule with no code
change: that is the pivot story.

Routers call :func:`apply_rules(event, ctx)` — never a validator directly —
except :func:`check_cancellation_window` / :func:`check_capacity`, kept as
thin wrappers because the tests and routers import them by name.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_config


class RuleViolation(Exception):
    pass


def parse_ts(value: str | datetime) -> datetime:
    """Parse an ISO timestamp to an *aware* UTC datetime.

    Stored PostgREST timestamps usually carry ``+00:00``, but a naive string
    (no offset) yields a naive datetime that would raise ``TypeError`` when
    compared to ``now(timezone.utc)``. Coerce naive → UTC so comparisons are
    always aware-vs-aware.
    """
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _term(name: str) -> str:
    return get_config().get("terms", {}).get(name, name)


# -- validators (value from config, ctx from the router) -----------------


def _cancellation_window(hours, ctx) -> None:
    starts_at = parse_ts(ctx["slot_starts_at"])
    remaining = (starts_at - datetime.now(timezone.utc)).total_seconds() / 3600
    if remaining < hours:
        raise RuleViolation(
            f"Cannot cancel/reschedule within {hours}h of the "
            f"{_term('slot').lower()} start."
        )


def _capacity(max_per_slot, ctx) -> None:
    if ctx["booked_count"] >= min(ctx["capacity"], max_per_slot):
        raise RuleViolation(f"This {_term('slot').lower()} is fully booked.")


def _advance_window(days, ctx) -> None:
    starts_at = parse_ts(ctx["slot_starts_at"])
    latest = datetime.now(timezone.utc) + timedelta(days=days)
    if starts_at > latest:
        raise RuleViolation(
            f"This {_term('slot').lower()} is more than {days} days away."
        )


def _buffer(minutes, ctx) -> None:
    """Reject a slot that overlaps another slot of the same resource once each
    is padded by ``bufferMinutes`` on both sides."""
    if not minutes:
        return
    pad = timedelta(minutes=minutes)
    new_start = parse_ts(ctx["starts_at"]) - pad
    new_end = parse_ts(ctx["ends_at"]) + pad
    for other in ctx.get("existing_slots", []):
        o_start = parse_ts(other["starts_at"])
        o_end = parse_ts(other["ends_at"])
        if new_start < o_end and o_start < new_end:
            raise RuleViolation(
                f"This {_term('slot').lower()} overlaps another within "
                f"{minutes} minutes."
            )


# -- registry: event -> {config key -> validator} ------------------------

RULES = {
    "booking.create": {
        "maxBookingsPerSlot": _capacity,
        "advanceBookingWindowDays": _advance_window,
    },
    "booking.change": {"cancellationWindowHours": _cancellation_window},
    "slot.create": {"bufferMinutes": _buffer},
}


def apply_rules(event: str, ctx: dict) -> None:
    """Run every configured validator for ``event``. Absent/None config keys
    are skipped gracefully — deleting a key disables its rule."""
    configured = get_config().get("rules", {})
    for key, validator in RULES.get(event, {}).items():
        if configured.get(key) is not None:
            validator(configured[key], ctx)


# -- thin wrappers imported by name from tests / routers -----------------


def check_cancellation_window(slot_starts_at: str | datetime) -> None:
    _cancellation_window(
        get_config()["rules"]["cancellationWindowHours"],
        {"slot_starts_at": slot_starts_at},
    )


def check_capacity(booked_count: int, capacity: int) -> None:
    _capacity(
        get_config()["rules"]["maxBookingsPerSlot"],
        {"booked_count": booked_count, "capacity": capacity},
    )
