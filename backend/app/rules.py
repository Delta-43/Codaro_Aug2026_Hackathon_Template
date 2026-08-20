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
import json
import logging
from datetime import datetime, timedelta, timezone

from app.config import get_config
from app.config_schema import DEFAULTS, deep_merge, validate_overrides


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


def _window_dates(window: dict) -> tuple[str, str]:
    return str(window.get("startDate") or ""), str(window.get("endDate") or "")


def _local_date(ctx: dict) -> str:
    """The slot's date in the BUSINESS's timezone, as `YYYY-MM-DD`.

    `timing.blackouts` and `timing.seasons` are written as local dates — a
    business closing for Christmas closes on its own calendar, not on UTC's — so
    comparing a UTC date would close the wrong day either side of midnight. The
    router passes the resolved zone; UTC is the fallback when it cannot.
    """
    start = parse_ts(ctx["slot_starts_at"])
    name = ctx.get("timezone")
    if name:
        try:
            from zoneinfo import ZoneInfo

            start = start.astimezone(ZoneInfo(str(name)))
        except Exception:
            pass
    return start.date().isoformat()


def _blackouts(windows, ctx) -> None:
    """`timing.blackouts` — dates the business is closed.

    Declared in v2, validated at load for shape, and enforced by nothing: a
    config could black out Christmas and the engine would take bookings all
    through it. Inclusive at both ends, because a closure written 24th–26th
    means the 26th is shut.
    """
    if not windows:
        return
    today = _local_date(ctx)
    for window in windows:
        if not isinstance(window, dict):
            continue
        start, end = _window_dates(window)
        if start and end and start <= today <= end:
            label = window.get("label") or window.get("key") or "that period"
            raise RuleViolation(f"Closed for {label}.")


def _seasons(windows, ctx) -> None:
    """`timing.seasons` — the periods the business actually trades.

    A declared season list is a statement that the business is OPEN then, which
    only means something if it is shut otherwise; a config with no seasons
    trades year-round and this is a no-op. Same inclusive bounds as a blackout.
    """
    if not windows:
        return
    today = _local_date(ctx)
    dated = [w for w in windows if isinstance(w, dict) and all(_window_dates(w))]
    if not dated:
        return
    for window in dated:
        start, end = _window_dates(window)
        if start <= today <= end:
            return
    raise RuleViolation("That date is outside the season this runs in.")


def closure_reason(slot_starts_at: str | datetime, service: dict | None = None) -> str | None:
    """Why this instant is not bookable at all, or None.

    The same two windows `apply_rules` enforces on create (`timing.blackouts`,
    `timing.seasons`), reached from the READ path so the calendar does not offer
    a slot the booking call will refuse. Showing a bookable-looking slot inside a
    declared closure is the failure mode this repo keeps fixing elsewhere; a
    closure the customer only meets at the confirm screen is the same bug.

    Deliberately narrower than `apply_rules`: lead time and the advance window
    are about a slot being too soon or too far, not about the business being
    shut, and they already render as their own states.
    """
    cfg = effective_service_config(service)
    timing = cfg.get("timing") or {}
    if not (timing.get("blackouts") or timing.get("seasons")):
        return None
    ctx = {
        "slot_starts_at": slot_starts_at,
        "timezone": (cfg.get("location") or {}).get("timezone") or "UTC",
    }
    try:
        _blackouts(timing.get("blackouts"), ctx)
        _seasons(timing.get("seasons"), ctx)
    except RuleViolation as e:
        return str(e)
    return None


# -- registry: event -> {config key -> validator} ------------------------

# Events a router may dispatch. An event with an empty map is a live extension
# point: adding `"someNewKey": _some_validator` here plus the key under `timing`
# in domain.config.json makes the rule enforce, and deleting the config key
# disables it again — no router change either way. That is the escape hatch the
# root `CLAUDE.md` promises, and it is why this registry exists rather than a
# pile of ifs.
#
# `advanceBookingWindowDays` IS dispatched now: `seed_config._grid` seeds
# exactly the declared window, so the seed horizon and the config finally agree.
RULES = {
    "booking.create": {
        "leadTimeMinutes": _lead_time,
        # Dispatched now that the seed lays down exactly
        # `advanceBookingWindowDays` of slots (see seed_config._grid). While the
        # grid reached further than the config allowed, enforcing this made half
        # the seeded calendar unbookable, which is why it sat in UNDISPATCHED.
        "advanceBookingWindowDays": _advance_window,
        # Both shipped in v2 and enforced nothing until now — exactly the
        # "config key plus a validator" this registry exists for.
        "blackouts": _blackouts,
        "seasons": _seasons,
    },
    "booking.change": {},
    "booking.approve": {},
    "booking.cancel": {},
    "slot.create": {"bufferMinutes": _buffer},
    "inventory.reserve": {},
    "inventory.return": {},
    "payment.due": {},
}

# Registered, not dispatched.
#
# `maxBookingsPerSlot`: capacity is enforced upstream by `_resolve_selection` +
# the `slot_occupancy` view, which understand party size and multi-slot holds.
# Dispatching `_capacity` here as well would re-apply `min(capacity, maxPerSlot)`
# and cap every shared-capacity slot at the global default of 1, breaking group
# bookings. The validator stays for `check_capacity()` and its tests.
#
# `cancellationWindowHours`: enforced, but by the OTHER path — the service
# resolver maps it to `cancellationCutoffHours` (see `_SERVICE_RULE_MAP`) and the
# cancel/reschedule routes call `within_cutoff()`. It sat under a
# `"booking.change"` event that no router ever dispatches, so the registry
# advertised a second enforcement point that could never fire and a new key added
# beside it would have been a silent no-op. `_cancellation_window` is the same
# rule with a `<` where `within_cutoff` has `>=`; dispatching it would
# double-enforce on a subtly different boundary.
UNDISPATCHED = {
    "maxBookingsPerSlot": _capacity,
    "cancellationWindowHours": _cancellation_window,
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
# `terms`/`copy` are deliberately absent: presentation stays global for
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
    """Deep-merge `override` onto a COPY of `base`. Lists replace wholesale.

    Thin wrapper over `config_schema.deep_merge`, which merges in place. The two
    were separate, identical implementations differing only by that copy, so the
    resolver and the config loader could have disagreed about what merging means."""
    return deep_merge(_copy.deepcopy(base), override)


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


# Memoize the expensive half of override resolution. `_problems_by_block` runs
# `validate()` twice per declared block, and the per-service resolvers
# (`effective_service_config`/`_rules`/`_pricing`) each call `surviving_overrides`
# for the SAME service while serializing a list or pricing a booking — so a row
# with overrides paid that validation several times over.
#
# Keyed on the declared blocks; the cached value holds the `get_config()` object
# it was computed against and is only reused while that object is still current
# (`is` identity). Holding the reference means the config can't be freed — and
# its id reused — while a cache entry lives, so this stays correct however the
# config is reset (`clear_config_cache` OR a bare `get_config.cache_clear()`): a
# reload yields a new config object, the identity check fails, and the entry is
# recomputed. The result is only ever READ downstream (every merge deep-copies
# its own base), so sharing one instance is safe; the deep-copy in
# `effective_service_config` stays per call.
_SURVIVING_CACHE: dict = {}
_SURVIVING_CACHE_MAX = 512


def surviving_overrides(service: dict | None) -> dict:
    """A service's override blocks with any INVALID block removed.

    Single source of truth for "which of this service's overrides actually
    apply", so the config resolver and the pricing resolver cannot disagree about
    it — they did, and it silently zeroed prices (see effective_service_pricing).
    """
    declared = service_overrides(service)
    if not declared:
        return {}
    cfg = get_config()
    dkey = json.dumps(declared, sort_keys=True, default=str)
    entry = _SURVIVING_CACHE.get(dkey)
    if entry is not None and entry[0] is cfg:
        return entry[1]
    bad = _problems_by_block(declared)
    if not bad:
        result = declared
    else:
        log.warning(
            "service %s has invalid config override(s) in %s; falling back to the "
            "global block(s). Problems: %s",
            (service or {}).get("id", "?"),
            sorted(bad),
            "; ".join(p for errs in bad.values() for p in errs),
        )
        result = {k: v for k, v in declared.items() if k not in bad}
    if len(_SURVIVING_CACHE) >= _SURVIVING_CACHE_MAX:
        _SURVIVING_CACHE.clear()
    _SURVIVING_CACHE[dkey] = (cfg, result)
    return result


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


def effective_auto_approve(service: dict | None, *, config: dict | None = None) -> bool:
    """Whether a new booking confirms immediately or lands as a pending request.

    `services.metadata.auto_approve` still wins (it is what the owner's toggle
    writes); `timing.confirmation` supplies the default, so a niche whose whole
    model is request-then-approve sets it once in the pivot file instead of on
    every service.
    """
    metadata = (service or {}).get("metadata") or {}
    if "auto_approve" in metadata:
        return bool(metadata["auto_approve"])
    # `config` lets a caller that has already resolved this service pass it in.
    # Resolving deep-copies and merges all nine OVERRIDABLE_BLOCKS (and, for a
    # service with overrides, re-validates each), so `serialize_service` doing it
    # once per field made a list endpoint pay for it twice per row.
    resolved = config if config is not None else effective_service_config(service)
    return resolved["timing"].get("confirmation") != "request_approve"


def capability(name: str, service: dict | None = None) -> bool:
    """Whether `capabilities.<name>` is on for this service (else globally).

    The block was declared, validated and served from the very first v2 commit
    and read by nothing, so `capabilities.reviews: false` hid the button and left
    the endpoint wide open — the exact "looks live, does nothing" failure the
    config's own audit map exists to prevent. Routers call this before the write;
    the surfaces that have no backend yet are listed as unbuilt in
    `scripts/check_pivots.py` rather than pretended to be gated here.
    """
    # Fail LOUD on an unknown name. `.get(name, True)` meant a typo in a gate
    # (`capability("review", ...)`) silently permitted the write forever — the
    # one failure mode a gate must not have.
    if name not in DEFAULTS["capabilities"]:
        raise KeyError(
            f"unknown capability {name!r}; declare it in config_schema.DEFAULTS"
            f"['capabilities'] first. Known: {sorted(DEFAULTS['capabilities'])}"
        )
    if service is not None:
        return bool(effective_service_config(service)["capabilities"].get(name, True))
    return bool(get_config()["capabilities"].get(name, True))


def payment_state(metadata: dict | None, service: dict | None = None,
                  status: str | None = None) -> dict:
    """What is owed on a booking and whether it has been settled.

    `payments.flow` decided nothing before this: a deployment could declare
    `prepay` or `invoice_after` and the engine recorded no notion of money owed,
    so an owner had no way to tell a paid booking from an unpaid one.

    The state is DERIVED from the flow plus what has been recorded as paid,
    rather than stored as a free-standing field, so it cannot drift out of sync
    with the config the way a persisted enum would after a pivot.

      none         — the product carries no payment at all
      not_required — cancelled/rejected: nothing is owed either way
      paid         — settled (recorded via POST /bookings/{id}/pay)
      deposit_due  — a deposit is owed now, the balance later
      due          — the full amount is owed now (prepay / pay_on_site)
      invoiced     — nothing owed at booking time; billed afterwards
    """
    md = metadata or {}
    payments_cfg = effective_service_config(service)["payments"] or {}
    flow = payments_cfg.get("flow") or "none"
    # WHO settles it (`payments.payer`) — the customer, a third party (an estate,
    # an insurer, an employer), or a split. It changes nothing about what is
    # owed, so it rides along with the amounts rather than gating them; the
    # client uses it to address the invoice to the right party.
    payer = payments_cfg.get("payer") or "customer"
    total = int(md.get("price_minor_units") or 0)
    deposit = int(md.get("deposit_minor_units") or 0)
    paid = int(md.get("amount_paid_minor_units") or 0)

    if flow == "none":
        state = "none"
    elif status in ("cancelled", "rejected"):
        # A cancelled booking owes nothing. Any refund is the business's own
        # process; the engine does not pretend to run one.
        state = "not_required"
    elif paid >= total and total > 0:
        state = "paid"
    elif flow == "invoice_after":
        state = "invoiced"
    elif deposit > 0 and paid < deposit:
        state = "deposit_due"
    elif total > 0:
        state = "due"
    else:
        state = "none"

    return {
        "flow": flow,
        "payer": payer,
        "state": state,
        "totalMinorUnits": total,
        "depositMinorUnits": deposit,
        "paidMinorUnits": paid,
        "outstandingMinorUnits": max(0, total - paid) if state not in ("none", "not_required") else 0,
        # The label must come from the same chain as the amounts: a seeded row
        # with no stored currency was reported as EUR while quote/create billed
        # the service's effective currency.
        "currency": md.get("currency")
        or effective_service_pricing(service).get("currency")
        or "EUR",
    }


def blocking_prerequisites(service: dict | None = None) -> list[dict]:
    """Prerequisites that must be satisfied before a booking may CONFIRM.

    `prerequisites` is a list, so it is not in OVERRIDABLE_BLOCKS and stays
    global — `service` is accepted for symmetry and future per-service support.

    The block shipped in v2 and gated nothing: a config could declare a required
    committee approval or a licence check and the engine would confirm the
    booking anyway, which is the exact failure `capability()` exists to prevent,
    one level up.
    """
    out = []
    for p in get_config().get("prerequisites") or []:
        if isinstance(p, dict) and p.get("blocksConfirmation"):
            out.append(p)
    return out


def unmet_prerequisites(metadata: dict | None, service: dict | None = None) -> list[str]:
    """Which blocking prerequisites this booking has NOT satisfied.

    Satisfaction is recorded on the booking (`metadata.prerequisites_met`), not
    on the customer: the same person can be cleared for one booking and not
    another, and a licence checked last year is not evidence about today.
    """
    met = set((metadata or {}).get("prerequisites_met") or [])
    return [p["key"] for p in blocking_prerequisites(service)
            if p.get("key") and p["key"] not in met]


def entitlement_plan(plan_key: str, service: dict | None = None) -> dict | None:
    """The config's `entitlements.plans[]` entry for `plan_key`, or None.

    Plans live in `domain.config.json`, not the database, so a stored
    entitlement row names its plan by key. A key that no longer resolves — the
    plan was renamed or retired — yields None and the entitlement goes inert
    rather than erroring: history must survive a config edit.
    """
    if not plan_key:
        return None
    block = effective_service_config(service)["entitlements"] if service is not None \
        else get_config()["entitlements"]
    for plan in block.get("plans") or []:
        if isinstance(plan, dict) and plan.get("key") == plan_key:
            return plan
    return None


def resolve_entitlement(rows: list[dict], service: dict | None = None,
                        now: datetime | None = None) -> dict | None:
    """Pick the entitlement that applies to a booking, resolved against config.

    `rows` are this customer's `entitlements` rows. Returns the engine-facing
    shape `pricing.quote()` expects — `{key, label, discountBps, row, plan}` —
    or None when the customer holds nothing that applies.

    Selection rules, in order:
      * the row must be `active` and inside its `starts_at`/`ends_at` window;
      * its `plan_key` must still resolve in the config;
      * a `pass`/`credits` plan must have a credit left to spend;
      * the plan must cover this service (`appliesToServices` empty = all).
    Ties break on the LARGEST discount, so a customer holding two plans is never
    quietly charged the worse of the two.
    """
    now = now or datetime.now(timezone.utc)
    service_id = (service or {}).get("id")
    best: dict | None = None
    for row in rows or []:
        if row.get("status") != "active":
            continue
        starts, ends = row.get("starts_at"), row.get("ends_at")
        if starts and parse_ts(starts) > now:
            continue
        if ends and parse_ts(ends) <= now:
            continue
        plan = entitlement_plan(row.get("plan_key"), service)
        if plan is None:
            continue
        applies = plan.get("appliesToServices") or []
        if applies and service_id and service_id not in applies:
            continue
        total = row.get("credits_total")
        if total is not None and int(row.get("credits_used") or 0) >= int(total):
            continue
        candidate = {
            "key": plan.get("key"),
            "label": plan.get("label") or plan.get("key"),
            "discountBps": int(plan.get("discountBps") or 0),
            "creditsRemaining": None if total is None
            else int(total) - int(row.get("credits_used") or 0),
            "row": row,
            "plan": plan,
        }
        if best is None or candidate["discountBps"] > best["discountBps"]:
            best = candidate
    return best


def within_cutoff(slot_starts_at: str | datetime, cutoff_hours, now: datetime | None = None) -> bool:
    """True when `now` is inside the cancellation/change cutoff of a slot start
    (the point past which a client may no longer cancel/reschedule)."""
    now = now or datetime.now(timezone.utc)
    return now >= parse_ts(slot_starts_at) - timedelta(hours=cutoff_hours)


# -- booking-shape resolvers ---------------------------------------------
#
# `booking.party.composition`, `booking.options` and `booking.subject` shipped in
# v2 and were read by nothing: the config could declare child pricing, paid
# add-ons and a per-subject intake and the booking path ignored all three. The
# pricing engine already accepts `person_units` and `subject` in its context —
# nothing ever built them. These three turn a request body into exactly those
# inputs, validating against the SERVICE's resolved `booking` block so a
# per-service override is honoured like every other block.
#
# They raise RuleViolation (not ApiError) so this module stays free of FastAPI;
# the routers map it to INVALID_RANGE the same way they do for `apply_rules`.


def _booking_block(service: dict | None) -> dict:
    return effective_service_config(service).get("booking") or {}


def resolve_party_bands(
    bands: dict | None, party_size: int, service: dict | None = None
) -> tuple[float | None, dict | None]:
    """Turn `{adult: 2, child: 1}` into a weighted head count.

    `party.composition` gives each band a `priceFactor`, so three heads are not
    automatically three units of the rate: 2 adults + 1 child at 0.5 is 2.5.
    Returns `(person_units, normalised_bands)`, both None when the deployment
    declares no composition or the caller sent none — in which case pricing
    falls back to the raw party size, exactly as before.

    The counts must add up to `partySize`, because both numbers reach the
    engine: the party size holds capacity and the bands price it, and a
    disagreement means one of the two is wrong.
    """
    composition = (_booking_block(service).get("party") or {}).get("composition")
    if not composition:
        return None, None
    if not bands:
        return None, None
    known = {b.get("key"): b for b in composition if isinstance(b, dict) and b.get("key")}
    counts: dict[str, int] = {}
    for key, count in bands.items():
        if key not in known:
            raise RuleViolation(f"Unknown party band {key!r}.")
        n = int(count or 0)
        if n < 0:
            raise RuleViolation(f"Party band {key!r} cannot be negative.")
        if n:
            counts[key] = n
    if not counts:
        return None, None
    if sum(counts.values()) != int(party_size):
        raise RuleViolation(
            f"The party bands add up to {sum(counts.values())}, not the party size "
            f"of {int(party_size)}."
        )
    units = 0.0
    for key, n in counts.items():
        factor = known[key].get("priceFactor")
        units += n * (1.0 if factor is None else float(factor))
    return units, counts


def resolve_options(
    selections: dict | None, service: dict | None = None
) -> list[dict]:
    """Turn `{kitHire: true, mealPlan: "lunch"}` into priced add-on lines.

    Each line is `{key, label, amountMinorUnits}` — the shape `pricing.quote()`
    adds to the subtotal, so an add-on is charged, shown in the breakdown, and
    covered by percentage fees and the deposit like any other part of the price.

    A boolean option contributes its own `priceMinorUnits`; a select option
    contributes the chosen `choices[]` entry's. An unknown option key or choice
    is a rejection, not a silent zero: a client sending `mealPlan: "banquet"`
    against a config that never declared it must not book a free banquet.
    """
    declared = _booking_block(service).get("options") or []
    if not selections:
        return []
    by_key = {o.get("key"): o for o in declared if isinstance(o, dict) and o.get("key")}
    lines: list[dict] = []
    for key, value in selections.items():
        option = by_key.get(key)
        if option is None:
            raise RuleViolation(f"Unknown option {key!r}.")
        label = option.get("label") or key
        if option.get("type") == "select":
            if value in (None, False, ""):
                continue
            choice = next(
                (c for c in (option.get("choices") or [])
                 if isinstance(c, dict) and c.get("key") == value),
                None,
            )
            if choice is None:
                raise RuleViolation(f"Unknown choice {value!r} for option {key!r}.")
            amount = int(choice.get("priceMinorUnits") or 0)
            lines.append({
                "key": key,
                "label": f"{label} — {choice.get('label') or choice.get('key')}",
                "choice": choice.get("key"),
                "amountMinorUnits": amount,
            })
        else:
            if not value:
                continue
            lines.append({
                "key": key,
                "label": label,
                "choice": True,
                "amountMinorUnits": int(option.get("priceMinorUnits") or 0),
            })
    return lines


def resolve_subject(subject: dict | None, service: dict | None = None) -> dict | None:
    """Validate the thing the booking is ABOUT (`booking.subject`).

    A vet books a pet, a garage books a vehicle, a school books a child. The
    block declares the noun and the fields; this keeps only declared fields and
    refuses a missing required one, so the intake is enforced at the booking
    rather than discovered at the counter.

    `pricing.match_tier` already reads `ctx["subject"]` for a `subjectField`
    tier, which is why the validated dict is returned rather than just checked.
    """
    block = _booking_block(service).get("subject") or {}
    if not block.get("enabled"):
        return None
    fields = [f for f in (block.get("fields") or []) if isinstance(f, dict) and f.get("key")]
    given = subject or {}
    out: dict = {}
    for field in fields:
        key = field["key"]
        value = given.get(key)
        blank = value is None or (isinstance(value, str) and not value.strip())
        if blank:
            if field.get("required"):
                noun = block.get("noun") or "Subject"
                raise RuleViolation(f"{noun}: {field.get('label') or key} is required.")
            continue
        if field.get("type") == "select":
            allowed = field.get("options") or []
            if allowed and value not in allowed:
                raise RuleViolation(f"{field.get('label') or key} must be one of {allowed}.")
        out[key] = value
    return out or None
