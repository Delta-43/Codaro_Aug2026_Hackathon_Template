"""Data-driven rules engine.

Each business rule is one key in ``domain.config.json`` `rules` plus one
small validator here, wired into an event-keyed registry. A new constraint
never needs a refactor — just a new config key, a ~4-line validator and one
registry entry. Deleting a key from the config disables its rule with no code
change: that is the pivot story.

Routers call :func:`apply_rules(event, ctx)` — never a validator directly.
:func:`check_cancellation_window` / :func:`check_capacity` are thin wrappers
kept for the test suite, which imports them by name; no router calls them.
"""
from __future__ import annotations

import copy as _copy
import logging
from datetime import datetime, timedelta, timezone

from app.config import get_config
from app.config_schema import validate_overrides


log = logging.getLogger(__name__)


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


def _lead_time(minutes, ctx) -> None:
    """Minimum notice: reject a booking made fewer than `minutes` before the
    start. 0 disables it, same convention as bufferMinutes."""
    if not minutes:
        return
    starts_at = parse_ts(ctx["slot_starts_at"])
    if starts_at - datetime.now(timezone.utc) < timedelta(minutes=minutes):
        raise RuleViolation(
            f"This {_term('slot').lower()} needs at least {minutes} minutes' notice."
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

# Events a router may dispatch. An event with an empty map is a live extension
# point: adding `"someNewKey": _some_validator` here plus the key under `timing`
# in domain.config.json makes the rule enforce, and deleting the config key
# disables it again — no router change either way. That is the escape hatch the
# README promises, and it is why this registry exists rather than a pile of ifs.
#
# `advanceBookingWindowDays` is registered but deliberately NOT dispatched: the
# demo seed lays down slots 56 days out (seed_data.py grids) while the shipped
# config allows 30, so enforcing it today would make half the seeded calendar
# unbookable. Wire it once the seed horizon and the config agree.
RULES = {
    "booking.create": {"leadTimeMinutes": _lead_time},
    "booking.change": {"cancellationWindowHours": _cancellation_window},
    "booking.approve": {},
    "booking.cancel": {},
    "slot.create": {"bufferMinutes": _buffer},
    "inventory.reserve": {},
    "inventory.return": {},
    "payment.due": {},
}

# Registered, not dispatched.
#
# `advanceBookingWindowDays`: see the note above (56-day seed vs 30-day config).
# `maxBookingsPerSlot`: capacity is enforced upstream by `_resolve_selection` +
# the `slot_occupancy` view, which understand party size and multi-slot holds.
# Dispatching `_capacity` here as well would re-apply `min(capacity, maxPerSlot)`
# and cap every shared-capacity slot at the global default of 1, breaking group
# bookings. The validator stays for `check_capacity()` and its tests.
UNDISPATCHED = {
    "advanceBookingWindowDays": _advance_window,
    "maxBookingsPerSlot": _capacity,
}


def apply_rules(event: str, ctx: dict, timing: dict | None = None) -> None:
    """Run every configured validator for ``event``. Absent/None config keys
    are skipped gracefully — deleting a key disables its rule.

    Reads `timing` (the v2 home of these numbers). `config_schema.normalize`
    mirrors the same values into the deprecated `rules` block, so a v1 config
    file resolves identically.

    ``timing`` is the RESOLVED block for the service being acted on — pass
    ``effective_service_config(service)["timing"]``. Reading the global block
    unconditionally made this the one resolver that skipped the service layer:
    `timing` is in `OVERRIDABLE_BLOCKS`, the write gate accepted a service's
    `leadTimeMinutes`, and then nothing enforced it. Omit it only where there is
    genuinely no service in scope; the global block is the fallback."""
    configured = timing if timing is not None else get_config().get("timing", {})
    for key, validator in RULES.get(event, {}).items():
        if configured.get(key) is not None:
            validator(configured[key], ctx)


# -- thin wrappers imported by name from tests / routers -----------------


def check_cancellation_window(slot_starts_at: str | datetime) -> None:
    _cancellation_window(
        get_config()["timing"]["cancellationWindowHours"],
        {"slot_starts_at": slot_starts_at},
    )


def check_capacity(booked_count: int, capacity: int) -> None:
    _capacity(
        get_config()["timing"]["maxBookingsPerSlot"],
        {"booked_count": booked_count, "capacity": capacity},
    )


# -- per-service rules (frontend contract) -------------------------------
#
# The new frontend models rules PER SERVICE (slot duration, min/max slots per
# booking, cancellation cutoff, price/currency, booking model). A service's own
# column wins; where it is null/absent, `domain.config.json` `rules` supplies the
# global default — so config becomes "vocabulary + defaults" rather than "the
# rules". This is the single place that merge happens; routers read the resolved
# dict, never raw service columns, so the fallback behaviour lives in one spot.

# resolved name -> (service column, dotted config path or None, hard default)
#
# v1 could only point at a key inside `rules`, which is why price, currency and
# min/max slots had no config path at all. Paths are now dotted and resolved
# against the whole config, so every one of these has a global default a pivot
# can set. The service column still wins where it is set.
_SERVICE_RULE_MAP = {
    "slotDurationMinutes": ("slot_duration_minutes", "timing.slotDurationMinutes", 30),
    "cancellationCutoffHours": ("cancellation_cutoff_hours", "timing.cancellationWindowHours", 24),
    "minSlotsPerBooking": ("min_slots_per_booking", "booking.duration.minUnits", 1),
    "maxSlotsPerBooking": ("max_slots_per_booking", "booking.duration.maxUnits", 1),
    "priceMinorUnits": ("price_minor_units", "pricing.rate.amountMinorUnits", 0),
    "currency": ("currency", "pricing.currency", "EUR"),
    "bookingModel": ("booking_model", None, "one_to_one"),
}

# The v2 blocks a service may override wholesale via `services.metadata.<block>`.
# `terms`/`copy`/`theme` are deliberately absent: presentation stays global for
# now (per-service vocabulary is a frontend change, not a backend one).
OVERRIDABLE_BLOCKS = (
    "booking",
    "pricing",
    "payments",
    "inventory",
    "location",
    "timing",
    "recurrence",
    "entitlements",
    "capabilities",
)


def _dig(tree: dict, path: str):
    """Resolve a dotted path, returning None if any hop is missing."""
    node = tree
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _merge(base: dict, override) -> dict:
    """Deep-merge `override` onto a copy of `base`. Lists replace wholesale."""
    out = _copy.deepcopy(base)
    if not isinstance(override, dict):
        return out
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def effective_service_rules(service: dict | None) -> dict:
    """Resolve a service's effective rule values: its own column, else the global
    `domain.config.json` default, else a hard fallback. Keys are the frontend's
    camelCase names."""
    svc = service or {}
    cfg = get_config()
    # An EXPLICIT per-service override outranks the column. The columns are
    # `NOT NULL DEFAULT`, so resolving them first made every `timing` /
    # `booking.duration` override permanently inert — accepted with a 200 by the
    # write gate and then silently ignored by `within_cutoff` and
    # `_resolve_selection`.
    declared = surviving_overrides(svc)
    out: dict = {}
    for name, (col, path, default) in _SERVICE_RULE_MAP.items():
        value = _dig(declared, path) if path is not None else None
        if value is None:
            value = svc.get(col)
        if value is None and path is not None:
            value = _dig(cfg, path)
        out[name] = value if value is not None else default
    return out


def service_overrides(service: dict | None) -> dict:
    """The override blocks a service actually declares, ignoring the rest of its
    metadata (`image_url`, `auto_approve`, ...)."""
    metadata = (service or {}).get("metadata") or {}
    return {b: metadata[b] for b in OVERRIDABLE_BLOCKS if isinstance(metadata.get(b), dict)}


def service_override_problems(service: dict | None) -> list[str]:
    """Validation errors in a service's own override blocks. Empty when clean.
    Exposed so an owner-facing surface can show a business its own bad config
    instead of it only ever appearing in a server log.

    Attributed per block (same source of truth as `surviving_overrides`), so what
    an owner is shown is exactly the set of blocks that will be ignored."""
    bad = _problems_by_block(service_overrides(service))
    return [p for _block, errs in sorted(bad.items()) for p in errs]


def _problems_by_block(declared: dict) -> dict[str, list[str]]:
    """Override problems attributed to the block that actually causes them.

    Each declared block is validated ALONE against the deployment's own config,
    so the block that introduces an error is the block that gets blamed. Reading
    the blame off the error's leading path segment instead was wrong for exactly
    the cross-block violations `validate()` exists to catch: a service declaring
    `payments: {"flow": "prepay"}` on a `capabilities.payments: false` deployment
    produces an error named `capabilities` — a block the service never declared,
    so the bad `payments` block was KEPT and applied while the warning below
    claimed a fallback that never happened.

    A block absent from the result is clean and safe to merge.
    """
    if not declared:
        return {}
    cfg = get_config()
    problems = {b: validate_overrides({b: v}, cfg) for b, v in declared.items()}
    return {b: errs for b, errs in problems.items() if errs}


def surviving_overrides(service: dict | None) -> dict:
    """A service's override blocks with any INVALID block removed.

    Single source of truth for "which of this service's overrides actually
    apply", so the config resolver and the pricing resolver cannot disagree about
    it — they did, and it silently zeroed prices (see effective_service_pricing).
    """
    declared = service_overrides(service)
    if not declared:
        return {}
    bad = _problems_by_block(declared)
    if not bad:
        return declared
    log.warning(
        "service %s has invalid config override(s) in %s; falling back to the "
        "global block(s). Problems: %s",
        (service or {}).get("id", "?"),
        sorted(bad),
        "; ".join(p for errs in bad.values() for p in errs),
    )
    return {k: v for k, v in declared.items() if k not in bad}


def effective_service_config(service: dict | None) -> dict:
    """The full v2 config as it applies to ONE service.

    Same precedence idea as `effective_service_rules`, lifted from single keys to
    whole blocks: `services.metadata.<block>` deep-merges over the global block.
    This is what makes a marketplace work — two businesses on the same deployment
    can price, gate and schedule completely differently without either of them
    touching `domain.config.json`.

    **Invalid override blocks are dropped, not merged.** The global config is
    validated at load; per-service overrides were not, so a bad block reached the
    pricing path unchecked. The write path (`POST`/`PATCH /services`) now rejects
    them outright, but seeded rows, direct DB edits and anything written before
    that gate existed still have to be survivable — so a bad block falls back to
    the global one and is logged, rather than 500-ing a customer's booking over a
    business's typo. Only the offending block is dropped; the rest still apply.
    """
    cfg = get_config()
    declared = surviving_overrides(service)
    return {
        block: _merge(cfg.get(block) or {}, declared.get(block))
        for block in OVERRIDABLE_BLOCKS
    }


def effective_service_pricing(service: dict | None) -> dict:
    """The `pricing` block for one service, with the legacy columns folded in.

    `services.price_minor_units` / `.currency` remain the source of truth for a
    service that has not opted into a richer model, so an un-pivoted deployment
    prices exactly as it did before. An explicit `services.metadata.pricing`
    overrides them.
    """
    svc = service or {}
    # Read the SURVIVING block, not the raw metadata. Reading the raw one meant a
    # rejected `pricing` override still suppressed the legacy-column fold-in, so a
    # service with a typo'd block priced at the global default (0 by default)
    # instead of its own `price_minor_units` — a silent zero-price bug.
    declared = surviving_overrides(svc).get("pricing") or {}
    pricing = _merge(get_config().get("pricing") or {}, declared)

    if _dig(declared, "rate.amountMinorUnits") is None and svc.get("price_minor_units") is not None:
        pricing["rate"] = {**pricing.get("rate", {}), "amountMinorUnits": svc["price_minor_units"]}
    if declared.get("currency") is None and svc.get("currency"):
        pricing["currency"] = svc["currency"]
    return pricing


def effective_auto_approve(service: dict | None) -> bool:
    """Whether a new booking confirms immediately or lands as a pending request.

    `services.metadata.auto_approve` still wins (it is what the owner's toggle
    writes); `timing.confirmation` supplies the default, so a niche whose whole
    model is request-then-approve sets it once in the pivot file instead of on
    every service.
    """
    metadata = (service or {}).get("metadata") or {}
    if "auto_approve" in metadata:
        return bool(metadata["auto_approve"])
    return effective_service_config(service)["timing"].get("confirmation") != "request_approve"


def capability(name: str, service: dict | None = None) -> bool:
    """Whether `capabilities.<name>` is on for this service (else globally).

    The block was declared, validated and served from the very first v2 commit
    and read by nothing, so `capabilities.reviews: false` hid the button and left
    the endpoint wide open — the exact "looks live, does nothing" failure the
    config's own audit map exists to prevent. Routers call this before the write;
    the surfaces that have no backend yet are listed as unbuilt in
    `scripts/check_pivots.py` rather than pretended to be gated here.
    """
    if service is not None:
        return bool(effective_service_config(service)["capabilities"].get(name, True))
    return bool(get_config()["capabilities"].get(name, True))


def within_cutoff(slot_starts_at: str | datetime, cutoff_hours, now: datetime | None = None) -> bool:
    """True when `now` is inside the cancellation/change cutoff of a slot start
    (the point past which a client may no longer cancel/reschedule)."""
    now = now or datetime.now(timezone.utc)
    return now >= parse_ts(slot_starts_at) - timedelta(hours=cutoff_hours)
