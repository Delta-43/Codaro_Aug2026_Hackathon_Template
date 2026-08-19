"""Bookings — the reworked booking loop.

A booking spans one-or-more contiguous, same-resource slots (`booking_slots`),
carries a party size, and computes its reference/price/span/status server-side
(the client's totals are never trusted). Capacity is re-checked at commit from
`slot_occupancy` (which sums party size). Rule violations surface as the
frontend's ApiError codes via `app.errors`.

Reads/writes of a user's own rows go through the RLS-scoped user client;
occupancy/aggregation and slot timings read via the service key (system work).
All endpoints here return a single serialized Booking except `GET /bookings`,
which returns a list.
"""
from __future__ import annotations

import calendar
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

import logging

from app.auth import AuthUser, enforce_rls_write, require_owner, require_user
from app.db import get_supabase, get_user_client, maybe_row
from app.errors import (
    CAPACITY_EXCEEDED,
    CUTOFF_PASSED,
    INVALID_RANGE,
    NOT_FOUND,
    SLOT_UNAVAILABLE,
    api_error,
)
from app.meta import merged_metadata
from app.models import BookingCreateReq, ClientReviewReq, QuoteReq, ReviewReq, RescheduleReq
from app.pricing import quote
from app.rules import (
    RuleViolation,
    apply_rules,
    capability,
    effective_auto_approve,
    effective_service_config,
    effective_service_pricing,
    effective_service_rules,
    blocking_prerequisites,
    payment_state,
    resolve_entitlement,
    unmet_prerequisites,
    within_cutoff,
)
from app.routers.waitlist import promote_from_waitlist
from app.serialize import (
    _parse,
    effective_booking_status,
    iso_utc,
    serialize_booking,
    serialize_quote,
)
from app.clock import now_utc
from app.references import booking_reference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bookings", tags=["bookings"])

# Keys `create_booking` writes into `bookings.metadata` itself. A client-supplied
# `metaFields.bookings` value carrying one of these names is dropped, not merged.
_ENGINE_BOOKING_KEYS = (
    "party_size", "reference", "price_minor_units", "currency", "price_breakdown",
    "deposit_minor_units", "provider_id", "service_id", "resource_id", "user_id",
    "slot_ids", "change_history", "cancelled_at_utc",
)

# --- lookups ---------------------------------------------------------------


def _load_service(db, service_id: str) -> dict:
    row = maybe_row(db.table("services").select("*").eq("id", service_id))
    if row is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")
    return row


def _occ_by_id(db, slot_ids: list[str]) -> dict[str, dict]:
    if not slot_ids:
        return {}
    rows = db.table("slot_occupancy").select("*").in_("slot_id", slot_ids).execute().data or []
    return {r["slot_id"]: r for r in rows}


def _slot_ids_map(uc, booking_ids: list[str]) -> dict[str, list[str]]:
    if not booking_ids:
        return {}
    rows = (
        uc.table("booking_slots").select("booking_id,slot_id").in_("booking_id", booking_ids).execute().data
        or []
    )
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["booking_id"], []).append(r["slot_id"])
    return out


def _slot_time_map(db, slot_ids: list[str]) -> dict[str, tuple]:
    if not slot_ids:
        return {}
    rows = db.table("slots").select("id,starts_at,ends_at").in_("id", slot_ids).execute().data or []
    return {r["id"]: (r["starts_at"], r["ends_at"]) for r in rows}


def _reviews_map(db, booking_ids: list[str]) -> dict[str, dict]:
    if not booking_ids:
        return {}
    rows = db.table("reviews").select("*").in_("booking_id", booking_ids).execute().data or []
    out: dict[str, dict] = {}
    for r in rows:  # one review per booking; keep the last seen
        out[r["booking_id"]] = r
    return out


def _name_map(db, table: str, ids: set[str]) -> dict[str, str]:
    """Batch id→name lookup for a table (providers/services). One query for the
    whole booking list, so the client doesn't fetch each provider/service by id."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.table(table).select("id,name").in_("id", list(ids)).execute().data or []
    return {r["id"]: r.get("name") or "" for r in rows}


def _names_for(db, md: dict) -> dict:
    """provider_name/service_name kwargs for a single booking's metadata, so a
    mutation response embeds the same names the list/get (`_enrich`) paths do."""
    pid, sid = md.get("provider_id"), md.get("service_id")
    return {
        "provider_name": _name_map(db, "providers", {pid}).get(pid, ""),
        "service_name": _name_map(db, "services", {sid}).get(sid, ""),
    }


def _ordered_span(slot_ids: list[str], time_map: dict[str, tuple]) -> tuple[list[str], str | None, str | None]:
    """Order slot ids by start; return (ordered_ids, first_start, last_end)."""
    known = [sid for sid in slot_ids if sid in time_map]
    known.sort(key=lambda sid: _parse(time_map[sid][0]))
    if not known:
        return slot_ids, None, None
    return known, time_map[known[0]][0], time_map[known[-1]][1]


# --- selection resolution (capacity / contiguity / party) ------------------


def _resolve_selection(
    rules: dict,
    occ: dict[str, dict],
    slot_ids: list[str],
    resource_id: str,
    party_size: int,
    credit: set[str],
) -> list[dict]:
    """Validate a slot selection at commit time and return the occupancy rows in
    start order. `rules` is the resolved per-service rule dict
    (`effective_service_rules`); `credit` is the set of slots the booking already
    holds (party size credited back, for reschedule overlap). Raises ApiError."""
    if not slot_ids:
        raise api_error(INVALID_RANGE, "Choose at least one time.")

    rows: list[dict] = []
    for sid in slot_ids:
        r = occ.get(sid)
        if r is None:
            raise api_error(NOT_FOUND, "That time no longer exists.")
        if r["resource_id"] != resource_id:
            raise api_error(INVALID_RANGE, "All times must be for the same option.")
        rows.append(r)

    lo, hi = rules["minSlotsPerBooking"], rules["maxSlotsPerBooking"]
    n = len(rows)
    if n < lo or n > hi:
        if hi == 1:
            raise api_error(INVALID_RANGE, "Only one slot can be booked at a time.")
        raise api_error(INVALID_RANGE, f"Select between {lo} and {hi} times.")

    rows.sort(key=lambda r: _parse(r["starts_at"]))
    for i in range(1, n):
        if _parse(rows[i]["starts_at"]) != _parse(rows[i - 1]["ends_at"]):
            raise api_error(INVALID_RANGE, "Times must be back-to-back with no gaps.")

    now = now_utc()
    for r in rows:
        if _parse(r["ends_at"]) <= now:
            raise api_error(SLOT_UNAVAILABLE, "That time has already passed.")
        cap = r["capacity"]
        if cap <= 0:
            raise api_error(SLOT_UNAVAILABLE, "That time is blocked.")
        if party_size > cap:
            raise api_error(CAPACITY_EXCEEDED, "Party size exceeds the capacity for that time.")
        booked = r["booked_count"] - (party_size if r["slot_id"] in credit else 0)
        if cap - booked < party_size:
            raise api_error(
                SLOT_UNAVAILABLE,
                "That time was just taken. We've refreshed availability.",
                details={"slotId": r["slot_id"]},
            )
    return rows


# --- enrichment ------------------------------------------------------------


def _enrich(db, uc, bookings: list[dict], *, include_client: bool = False) -> list[dict]:
    """Serialize bookings with their slot ids, span, and review, batched.
    `include_client=True` adds the booking's client email (owner-only view)."""
    ids = [b["id"] for b in bookings]
    sids_map = _slot_ids_map(uc, ids)
    all_sids = {s for b in bookings for s in (sids_map.get(b["id"]) or [b["slot_id"]])}
    time_map = _slot_time_map(db, list(all_sids))
    reviews = _reviews_map(db, ids)
    metas = [b.get("metadata") or {} for b in bookings]
    prov_names = _name_map(db, "providers", {m.get("provider_id") for m in metas})
    svc_names = _name_map(db, "services", {m.get("service_id") for m in metas})
    now = now_utc()

    out = []
    for b in bookings:
        sids = sids_map.get(b["id"]) or ([b["slot_id"]] if b.get("slot_id") else [])
        ordered, start, end = _ordered_span(sids, time_map)
        md = b.get("metadata") or {}
        out.append(
            serialize_booking(
                b,
                slot_ids=ordered,
                start_utc=start,
                end_utc=end,
                review=reviews.get(b["id"]),
                now=now,
                include_client=include_client,
                provider_name=prov_names.get(md.get("provider_id"), ""),
                service_name=svc_names.get(md.get("service_id"), ""),
            )
        )
    return out


def _load_own(uc, booking_id: str) -> dict:
    """Load a booking through the user client (RLS scopes to own/owner). 404 if
    missing or not visible to this user."""
    row = maybe_row(uc.table("bookings").select("*").eq("id", booking_id))
    if row is None:
        raise api_error(NOT_FOUND, "That booking could not be found.")
    return row


def _assert_owns_booking(db, booking: dict, owner: AuthUser) -> None:
    """Defense-in-depth: verify the owner owns the provider this booking belongs
    to before they act on it. RLS's is_owner() lets any owner update any booking,
    so this narrows owner actions to their own providers (403 otherwise)."""
    provider_id = (booking.get("metadata") or {}).get("provider_id")
    provider = maybe_row(db.table("providers").select("owner_id").eq("id", provider_id))
    if not provider or provider.get("owner_id") != owner.id:
        raise HTTPException(403, "You can only manage bookings for your own business.")


def _span_of(db, booking: dict, uc) -> tuple[list[str], str | None, str | None]:
    sids = _slot_ids_map(uc, [booking["id"]]).get(booking["id"]) or (
        [booking["slot_id"]] if booking.get("slot_id") else []
    )
    time_map = _slot_time_map(db, sids)
    return _ordered_span(sids, time_map)


# --- endpoints -------------------------------------------------------------


@router.get("")
def list_bookings(scope: str = "all", user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    rows = uc.table("bookings").select("*").execute().data or []
    bookings = _enrich(db, uc, rows)

    now_iso = iso_utc(now_utc())

    def is_upcoming(b: dict) -> bool:
        # A rejected request is not an upcoming booking even though its slot is in
        # the future; only live statuses count as upcoming.
        return bool(
            b["endUtc"]
            and b["endUtc"] > now_iso
            and b["status"] not in ("completed", "rejected")
        )

    if scope == "upcoming":
        bookings = [b for b in bookings if is_upcoming(b)]
        bookings.sort(key=lambda b: b["startUtc"] or "")
    elif scope == "past":
        bookings = [b for b in bookings if not is_upcoming(b)]
        bookings.sort(key=lambda b: b["startUtc"] or "", reverse=True)
    else:
        bookings.sort(key=lambda b: b["startUtc"] or "", reverse=True)
    return bookings


@router.get("/{booking_id}")
def get_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    return _enrich(db, uc, [booking])[0]


def _entitlement(db, user_id: str | None, service: dict | None) -> dict | None:
    """The entitlement this customer holds that applies to this service.

    Read through the SERVICE key rather than a JWT-scoped client: the quote path
    and the create path must agree, and an owner approving a pending request
    prices a booking that is not their own row. RLS still protects the customer's
    own reads via `GET /me/entitlements`.
    """
    if not user_id or not capability("entitlements", service):
        return None
    try:
        rows = (
            db.table("entitlements").select("*")
            .eq("user_id", user_id).eq("status", "active").execute().data
            or []
        )
    except Exception:
        # An entitlement is a discount, never a gate: a lookup failure must not
        # take down booking. Worst case the customer pays list price and the
        # owner refunds — far better than a 500 on the commit path.
        logger.exception("Could not load entitlements for %s", user_id)
        return None
    return resolve_entitlement(rows, service)


_PATTERN_DELTAS = {"weekly": 7, "biweekly": 14}


def _occurrence_starts(first_start, pattern: str, count: int) -> list:
    """The start instants of a repeating series, first occurrence included.

    Weekly/biweekly step whole days, so they survive a DST change with the
    wall-clock time intact only if the caller re-localises; slots are stored in
    UTC and matched by exact instant below, so a series that crosses a DST
    boundary simply finds no slot for that occurrence and reports it skipped
    rather than silently booking an hour out.

    Monthly steps by calendar month and CLAMPS to the last valid day, so a
    series starting on the 31st does not skip February.
    """
    out = [first_start]
    for i in range(1, count):
        if pattern in _PATTERN_DELTAS:
            out.append(first_start + timedelta(days=_PATTERN_DELTAS[pattern] * i))
        else:  # monthly
            month = first_start.month - 1 + i
            year = first_start.year + month // 12
            month = month % 12 + 1
            day = min(first_start.day, calendar.monthrange(year, month)[1])
            out.append(first_start.replace(year=year, month=month, day=day))
    return out


def _slots_at(db, resource_id: str, starts: list) -> dict:
    """Map each wanted start instant to the slot on that resource, if one exists.

    A recurring booking can only land on a slot the business actually opened —
    the engine never invents availability. An occurrence with no slot is
    reported back as skipped rather than quietly dropped.
    """
    if not starts:
        return {}
    lo, hi = min(starts), max(starts)
    rows = (
        db.table("slots").select("*").eq("resource_id", resource_id)
        .gte("starts_at", iso_utc(lo)).lte("starts_at", iso_utc(hi))
        .execute().data
        or []
    )
    by_instant = {}
    for row in rows:
        parsed = _parse(row["starts_at"])
        if parsed is not None:
            by_instant[parsed] = row
    return {s: by_instant[s] for s in starts if s in by_instant}


def _consume_credit(db, entitlement: dict | None, booking_id: str) -> None:
    """Spend one credit off a `pass`/`credits` entitlement.

    Only credit-bearing plans have a `credits_total`; a membership discounts
    every booking and consumes nothing, so it is left alone.

    Deliberately AFTER the booking row exists and deliberately best-effort: the
    booking is the thing the customer is owed, and failing to decrement a
    counter must not undo it or 500 the request. The alternative — decrement
    first, then insert — spends a credit for a booking that may never exist,
    which is the worse failure. The booking records which entitlement it used,
    so a missed decrement is reconcilable.
    """
    if not entitlement:
        return
    row = entitlement.get("row") or {}
    if row.get("credits_total") is None:
        return
    try:
        db.table("entitlements").update(
            {"credits_used": int(row.get("credits_used") or 0) + 1}
        ).eq("id", row["id"]).execute()
    except Exception:
        logger.exception(
            "Could not spend a credit on entitlement %s for booking %s",
            row.get("id"), booking_id,
        )


def _price(service: dict | None, rows: list, party: int,
           entitlement: dict | None = None) -> dict:
    """Quote a selection through the config-driven pricing engine.

    v1 computed `priceMinorUnits * len(rows) * party` inline here. The default
    `pricing` block reproduces that exactly, so an un-pivoted service prices
    identically — but a service that declares `metadata.pricing` can now bill per
    hour, per night, per person, by tier, with fees, caps and a deposit.

    `booking_index` (a customer's prior-booking count, for first-session tiers)
    is not passed yet: it needs a count query on the hot booking path, so it
    stays unresolved until that is worth paying for.
    """
    pricing = effective_service_pricing(service)
    start, end = _parse(rows[0]["starts_at"]), _parse(rows[-1]["ends_at"])
    duration = int((end - start).total_seconds() // 60) if start and end else 0
    tz = _business_tz(service)
    return quote(
        pricing,
        {
            "slot_count": len(rows),
            "party_size": party,
            "duration_minutes": duration,
            "now": now_utc(),
            "start_local": start.astimezone(tz) if start else None,
            "entitlement": entitlement,
        },
    )


def _business_tz(service: dict | None):
    """The business's own timezone — time-of-day pricing tiers (peak/off-peak)
    are meaningless in UTC."""
    name = effective_service_config(service)["location"].get("timezone") or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


@router.post("/quote")
def quote_selection(payload: QuoteReq, user: AuthUser = Depends(require_user)):
    """Price a selection without committing it.

    Runs `_resolve_selection` + `_price` — byte for byte the path
    `create_booking` takes — so the number shown on the confirm screen is the
    number that will be charged. The frontend previously multiplied
    `priceMinorUnits * slots * party` itself; that is only the DEFAULT pricing
    block's formula, so every `per_hour` / `per_person` / `tiered` /
    `subscription` / `free` service quoted one price and billed another, and a
    declared fee, cap or deposit was invisible until after the booking existed.

    Read-only: no row is written and no capacity is held. It still validates the
    selection, so an unbookable range surfaces the same ApiError the create
    would raise rather than a price for something that cannot be booked.
    """
    db = get_supabase()
    service = _load_service(db, payload.service_id)
    rules = effective_service_rules(service)
    party = max(1, int(payload.party_size or 1))
    occ = _occ_by_id(db, payload.slot_ids)
    rows = _resolve_selection(rules, occ, payload.slot_ids, payload.resource_id, party, credit=set())
    ent = _entitlement(db, user.id, service)
    return serialize_quote(_price(service, rows, party, ent), service, entitlement=ent)


@router.post("")
def create_booking(payload: BookingCreateReq, user: AuthUser = Depends(require_user)):
    if not user.email:
        raise api_error(NOT_FOUND, "Authenticated user has no email to book under.")
    db = get_supabase()
    service = _load_service(db, payload.service_id)
    rules = effective_service_rules(service)
    party = max(1, int(payload.party_size or 1))

    occ = _occ_by_id(db, payload.slot_ids)
    rows = _resolve_selection(rules, occ, payload.slot_ids, payload.resource_id, party, credit=set())
    ordered = [r["slot_id"] for r in rows]
    start, end = rows[0]["starts_at"], rows[-1]["ends_at"]

    # Manual-approve services (autoApprove=false) land the booking as a pending
    # request the owner acts on in the Requests tab; the default confirms it
    # immediately. Pending holds no capacity (slot_occupancy counts only
    # 'confirmed'), so capacity is re-checked at approval time.
    # Config-driven gates for this event. Empty by default (leadTimeMinutes is 0),
    # so this is a no-op until a pivot turns one on — that is the whole point of
    # the registry: a new constraint is a config key plus a validator, never a
    # change here.
    try:
        apply_rules(
            "booking.create",
            {"slot_starts_at": rows[0]["starts_at"]},
            # THIS service's resolved timing, not the global block. `timing` is in
            # OVERRIDABLE_BLOCKS and the write gate accepts a per-service
            # `leadTimeMinutes` — reading the global block here made this the one
            # resolver that skipped the service layer, so the override was
            # accepted with a 200 and then enforced by nothing.
            effective_service_config(service)["timing"],
        )
    except RuleViolation as e:
        raise api_error(INVALID_RANGE, str(e))

    auto_approve = effective_auto_approve(service)
    # A blocking prerequisite outranks auto-approve: an instant-confirmation
    # service that also demands a committee sign-off must NOT confirm, or the
    # gate is decorative. Pending holds no capacity, so the seat stays live
    # until the prerequisite is actually cleared.
    pending_prereqs = (
        [p["key"] for p in blocking_prerequisites(service) if p.get("key")]
        if capability("prerequisites", service) else []
    )
    status = "confirmed" if auto_approve and not pending_prereqs else "pending"
    entitlement = _entitlement(db, user.id, service)
    priced = _price(service, rows, party, entitlement)

    metadata = {
        # `metaFields.bookings` domain data (the shipped medical example declares
        # a `reason` field) merged UNDER every engine-owned key below, which
        # always win — a domain field must never be able to rewrite a price.
        **merged_metadata("bookings", payload.metadata, reserved=_ENGINE_BOOKING_KEYS),
        "party_size": party,
        "reference": booking_reference(),
        "price_minor_units": priced["amountMinorUnits"],
        "currency": priced["currency"],
        "price_breakdown": priced["breakdown"],
        "deposit_minor_units": priced["depositMinorUnits"],
        # Which entitlement priced this, so a discount is auditable and a missed
        # credit decrement can be reconciled against the bookings that used it.
        "entitlement_key": (entitlement or {}).get("key"),
        "entitlement_id": ((entitlement or {}).get("row") or {}).get("id"),
        # Recorded per BOOKING, not per customer: the same person can be
        # cleared for one booking and not another.
        "prerequisites_met": [],
        "prerequisites_pending": pending_prereqs,
        "provider_id": service["provider_id"],
        "service_id": service["id"],
        "resource_id": payload.resource_id,
        "user_id": user.id,
        "slot_ids": ordered,
        "change_history": [],
    }
    row = {
        "slot_id": ordered[0],  # first slot, for base-table compatibility
        "client_email": user.email,
        "client_id": user.id,
        "status": status,
        "history": [{"status": status, "at": iso_utc(now_utc())}],
        "metadata": metadata,
    }
    uc = get_user_client(user.token)
    inserted = uc.table("bookings").insert(row).execute().data
    inserted = enforce_rls_write(inserted, entity="booking")
    _consume_credit(db, entitlement, inserted[0]["id"] if inserted else "?")
    booking = inserted[0]
    uc.table("booking_slots").insert(
        [{"booking_id": booking["id"], "slot_id": sid} for sid in ordered]
    ).execute()
    out = serialize_booking(
        booking, slot_ids=ordered, start_utc=start, end_utc=end, review=None,
        service=service, **_names_for(db, metadata)
    )
    out["series"] = _book_repeats(
        db, uc, user, payload, service, rows, party, booking["id"], metadata,
    )
    return out


def _book_repeats(db, uc, user, payload, service, rows, party, first_id, first_md) -> dict | None:
    """Book the remaining occurrences of a repeating series.

    Returns `{id, pattern, bookedIds, skipped}` or None when the request asked
    for no repeat. The FIRST occurrence is already committed by the caller — it
    is the booking the customer selected, and it must succeed or fail on its
    own merits. Every later occurrence is best-effort: it lands only if the
    business actually opened a slot at that instant with room for the party.

    Occurrences that cannot be booked are REPORTED, not silently dropped. A
    series that quietly books 3 of 12 while the customer believes they have 12
    is the worst outcome here, so the caller gets both lists back.
    """
    repeat = payload.repeat
    if repeat is None or int(repeat.count or 1) <= 1:
        return None
    cfg = effective_service_config(service)["recurrence"]
    if not cfg.get("enabled") or not capability("recurrence", service):
        raise api_error(INVALID_RANGE, "This service cannot be booked as a repeating series.")
    if repeat.pattern not in (cfg.get("patterns") or []):
        allowed = ", ".join(cfg.get("patterns") or []) or "none"
        raise api_error(INVALID_RANGE, f"Unsupported repeat pattern. Allowed: {allowed}.")

    # The config's ceiling wins over whatever the client asked for.
    limit = int(cfg.get("maxOccurrences") or 1)
    count = max(1, min(int(repeat.count), limit))
    first_start = _parse(rows[0]["starts_at"])
    if first_start is None:
        return None

    series_id = first_id  # the first booking's id names the series
    # The whole SPAN repeats, not just its first slot: a two-hour clean booked
    # weekly needs both slots each week. Shifting only the first would fail
    # `minSlotsPerBooking` on every occurrence of any multi-slot service.
    span = [_parse(r["starts_at"]) for r in rows]
    offsets = [(t - first_start) for t in span if t is not None]
    occurrence_starts = _occurrence_starts(first_start, repeat.pattern, count)[1:]
    all_wanted = [o + d for o in occurrence_starts for d in offsets]
    found = _slots_at(db, payload.resource_id, all_wanted)
    rules = effective_service_rules(service)
    booked, skipped = [], []

    for start_at in occurrence_starts:
        wanted_span = [start_at + d for d in offsets]
        slots = [found.get(t) for t in wanted_span]
        if any(sl is None for sl in slots):
            skipped.append({"startUtc": iso_utc(start_at), "reason": "NO_SLOT"})
            continue
        slot_ids = [sl["id"] for sl in slots]
        try:
            occ = _occ_by_id(db, slot_ids)
            occ_rows = _resolve_selection(
                rules, occ, slot_ids, payload.resource_id, party, credit=set()
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            skipped.append({"startUtc": iso_utc(start_at),
                            "reason": detail.get("code") or "UNAVAILABLE"})
            continue
        slot_ids = [r["slot_id"] for r in occ_rows]  # canonical start order
        ent = _entitlement(db, user.id, service)
        occ_priced = _price(service, occ_rows, party, ent)
        md = {
            **first_md,
            "reference": booking_reference(),
            "price_minor_units": occ_priced["amountMinorUnits"],
            "price_breakdown": occ_priced["breakdown"],
            "deposit_minor_units": occ_priced["depositMinorUnits"],
            "entitlement_key": (ent or {}).get("key"),
            "entitlement_id": ((ent or {}).get("row") or {}).get("id"),
            "slot_ids": slot_ids,
            "series_id": series_id,
        }
        status = "confirmed" if effective_auto_approve(service) else "pending"
        made = uc.table("bookings").insert({
            "slot_id": slot_ids[0],
            "client_email": user.email,
            "client_id": user.id,
            "status": status,
            "history": [{"status": status, "at": iso_utc(now_utc())}],
            "metadata": md,
        }).execute().data
        made = enforce_rls_write(made, entity="booking")
        _consume_credit(db, ent, made[0]["id"])
        uc.table("booking_slots").insert(
            [{"booking_id": made[0]["id"], "slot_id": sid} for sid in slot_ids]
        ).execute()
        booked.append(made[0]["id"])

    return {
        "id": series_id,
        "pattern": repeat.pattern,
        "requested": count,
        "bookedIds": [first_id] + booked,
        "skipped": skipped,
    }


@router.post("/{booking_id}/reschedule")
def reschedule_booking(
    booking_id: str, payload: RescheduleReq, user: AuthUser = Depends(require_user)
):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))
    rules = effective_service_rules(service)

    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    if effective_booking_status(booking["status"], cur_end) != "confirmed":
        raise api_error(CUTOFF_PASSED, "Only upcoming bookings can be moved.")
    cutoff = rules["cancellationCutoffHours"]
    if not user.is_owner and cur_start and within_cutoff(cur_start, cutoff):
        raise api_error(CUTOFF_PASSED, f"Changes closed — within {cutoff}h of the start.")

    party = int(md.get("party_size", 1))
    resource_id = md.get("resource_id")
    occ = _occ_by_id(db, payload.new_slot_ids)
    rows = _resolve_selection(
        rules, occ, payload.new_slot_ids, resource_id, party, credit=set(cur_ids)
    )
    ordered = [r["slot_id"] for r in rows]
    new_start, new_end = rows[0]["starts_at"], rows[-1]["ends_at"]

    # Atomic slot swap: replace the join rows, then update the booking.
    uc.table("booking_slots").delete().eq("booking_id", booking_id).execute()
    uc.table("booking_slots").insert(
        [{"booking_id": booking_id, "slot_id": sid} for sid in ordered]
    ).execute()

    md["slot_ids"] = ordered
    repriced = _price(service, rows, party, _entitlement(db, user.id, service))
    md["price_minor_units"] = repriced["amountMinorUnits"]
    md["currency"] = repriced["currency"]
    md["price_breakdown"] = repriced["breakdown"]
    md["deposit_minor_units"] = repriced["depositMinorUnits"]
    md.setdefault("change_history", []).append(
        {
            "at_utc": iso_utc(now_utc()),
            "from_start_utc": iso_utc(cur_start),
            "to_start_utc": iso_utc(new_start),
        }
    )
    history = booking["history"] + [{"status": "rescheduled", "at": iso_utc(now_utc())}]
    updated = (
        uc.table("bookings")
        .update({"slot_id": ordered[0], "status": "confirmed", "history": history, "metadata": md})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    review = _reviews_map(db, [booking_id]).get(booking_id)
    return serialize_booking(
        updated[0], slot_ids=ordered, start_utc=new_start, end_utc=new_end, review=review,
        **_names_for(db, md),
    )


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    if booking["status"] == "cancelled":  # idempotent
        review = _reviews_map(db, [booking_id]).get(booking_id)
        return serialize_booking(
            booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review,
            **_names_for(db, booking.get("metadata") or {}),
        )

    if effective_booking_status(booking["status"], cur_end) == "completed":
        raise api_error(CUTOFF_PASSED, "Completed bookings can't be cancelled.")
    if not user.is_owner:
        md = booking.get("metadata") or {}
        rules = effective_service_rules(_load_service(db, md.get("service_id")))
        cutoff = rules["cancellationCutoffHours"]
        if cur_start and within_cutoff(cur_start, cutoff):
            raise api_error(CUTOFF_PASSED, f"Changes closed — within {cutoff}h of the start.")

    md = dict(booking.get("metadata") or {})
    md["cancelled_at_utc"] = iso_utc(now_utc())
    history = booking["history"] + [
        {"status": "cancelled", "at": iso_utc(now_utc()), **({"actor": "owner"} if user.is_owner else {})}
    ]
    updated = (
        uc.table("bookings")
        .update({"status": "cancelled", "history": history, "metadata": md})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    # A cancellation is the moment a seat frees. Hand it to the head of the
    # queue if the config asks for that (`timing.waitlist.autoPromote`).
    promote_from_waitlist(db, cur_ids, _load_service(db, md.get("service_id")))
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=None,
        **_names_for(db, md),
    )


@router.post("/{booking_id}/review")
def review_booking(booking_id: str, payload: ReviewReq, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    if effective_booking_status(booking["status"], cur_end) != "completed":
        raise api_error(NOT_FOUND, "Only completed bookings can be reviewed.")

    md = booking.get("metadata") or {}
    # `capabilities.reviews: false` hid the button and left the endpoint wide
    # open — the block's own contract is that a false capability hides the
    # surface AND refuses the write. Resolved per service, so one business on a
    # marketplace can run without reviews.
    service = maybe_row(db.table("services").select("*").eq("id", md.get("service_id")))
    if not capability("reviews", service):
        raise api_error(NOT_FOUND, "Reviews are not enabled here.")

    rating = max(1, min(5, round(payload.rating)))
    # One review per booking: clear any prior (service key — no user delete
    # policy) then insert through the user client (RLS reviews_insert_own).
    db.table("reviews").delete().eq("booking_id", booking_id).execute()
    uc.table("reviews").insert(
        {
            "booking_id": booking_id,
            "provider_id": md.get("provider_id"),
            "rating": rating,
            "text": (payload.text or "").strip(),
        }
    ).execute()
    review = maybe_row(db.table("reviews").select("*").eq("booking_id", booking_id))
    return serialize_booking(
        booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review,
        **_names_for(db, md),
    )


# --- owner request decisions (approve / reject) ----------------------------


@router.post("/{booking_id}/return")
def return_booking(booking_id: str, owner: AuthUser = Depends(require_owner)):
    """Mark a loaned item as handed back.

    Owner-only on purpose: the business is the party that can actually see the
    item come back, and a customer able to self-certify a return would be able
    to clear their own overdue fee.

    `inventory.returnRequired` deployments (ski hire, tool library, plant
    rental) do not finish at slot end. Until this existed the return leg was
    declared in config and enforced nowhere: the booking read as completed the
    moment the slot ended, and a declared overdue fee could never be charged.

    The overdue fee is COMPUTED from `returned_at_utc`, never stored — see
    `serialize.loan_state`. This route only records when the item came back.
    """
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)
    _assert_owns_booking(db, booking, owner)

    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))
    inventory = effective_service_config(service)["inventory"]
    if not inventory.get("returnRequired"):
        raise api_error(INVALID_RANGE, "This service does not loan anything to return.")
    if booking["status"] == "cancelled":
        raise api_error(INVALID_RANGE, "A cancelled booking has nothing to return.")
    if md.get("returned_at_utc"):
        raise api_error(INVALID_RANGE, "This is already marked returned.")

    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    md["returned_at_utc"] = iso_utc(now_utc())
    updated = uc.table("bookings").update({
        "metadata": md,
        # Append-only, like every other status change on this table.
        "history": list(booking.get("history") or []) + [
            {"status": "returned", "at": md["returned_at_utc"], "actor": "owner"}
        ],
    }).eq("id", booking_id).execute().data
    updated = enforce_rls_write(updated, entity="booking")
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
        review=_reviews_map(db, [booking_id]).get(booking_id),
        include_client=True, service=service, **_names_for(db, md),
    )


@router.post("/{booking_id}/pay")
def record_payment(booking_id: str, amount: int | None = None,
                   owner: AuthUser = Depends(require_owner)):
    """Record money received against a booking.

    Owner-only, and deliberately a RECORD rather than a charge: `payments.adapter`
    is `manual` in every shipped config, so the engine's job is to know what is
    owed and what has been settled, not to move money. Wiring a real PSP means
    implementing the adapter behind this route, not changing its meaning.

    `amount` defaults to whatever is still outstanding, so the common case —
    "they paid the bill" — needs no body. Partial payments accumulate, which is
    what `deposit_balance` pricing needs: a deposit now, the balance later.
    """
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)
    _assert_owns_booking(db, booking, owner)

    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))
    state = payment_state(md, service, booking["status"])
    if state["flow"] == "none":
        raise api_error(INVALID_RANGE, "This service does not take payment.")
    if state["state"] in ("paid", "not_required"):
        raise api_error(INVALID_RANGE, "There is nothing outstanding on this booking.")

    due = state["outstandingMinorUnits"]
    taken = due if amount is None else int(amount)
    if taken <= 0:
        raise api_error(INVALID_RANGE, "A payment must be a positive amount.")
    # Never record more than is owed: an overpayment is a refund problem the
    # engine has no way to resolve, so it is refused rather than absorbed.
    if taken > due:
        raise api_error(INVALID_RANGE, f"That is more than the {due} outstanding.")

    md["amount_paid_minor_units"] = int(md.get("amount_paid_minor_units") or 0) + taken
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    updated = uc.table("bookings").update({
        "metadata": md,
        "history": list(booking.get("history") or []) + [
            {"status": "payment_recorded", "amount": taken,
             "at": iso_utc(now_utc()), "actor": "owner"}
        ],
    }).eq("id", booking_id).execute().data
    updated = enforce_rls_write(updated, entity="booking")
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
        review=_reviews_map(db, [booking_id]).get(booking_id),
        include_client=True, service=service, **_names_for(db, md),
    )


@router.post("/{booking_id}/prerequisites/{key}")
def satisfy_prerequisite(booking_id: str, key: str, owner: AuthUser = Depends(require_owner)):
    """Record that one blocking prerequisite has been met.

    Owner-only: a prerequisite is the business checking something (a licence, a
    committee sign-off, an age check). A customer able to tick their own boxes
    is not a gate.

    Idempotent — re-recording a met prerequisite is a no-op, so a double-tap in
    the console cannot fail.
    """
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)
    _assert_owns_booking(db, booking, owner)

    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))
    known = {p["key"] for p in blocking_prerequisites(service) if p.get("key")}
    if key not in known:
        raise api_error(NOT_FOUND, f"No blocking prerequisite named {key!r}.")

    met = list(md.get("prerequisites_met") or [])
    if key not in met:
        met.append(key)
    md["prerequisites_met"] = met
    md["prerequisites_pending"] = [k for k in known if k not in met]

    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    updated = uc.table("bookings").update({
        "metadata": md,
        "history": list(booking.get("history") or []) + [
            {"status": "prerequisite_met", "key": key,
             "at": iso_utc(now_utc()), "actor": "owner"}
        ],
    }).eq("id", booking_id).execute().data
    updated = enforce_rls_write(updated, entity="booking")
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
        review=_reviews_map(db, [booking_id]).get(booking_id),
        include_client=True, service=service, **_names_for(db, md),
    )


@router.post("/{booking_id}/approve")
def approve_booking(booking_id: str, owner: AuthUser = Depends(require_owner)):
    """Owner approves a pending request → confirmed. Capacity is re-checked now
    (pending holds none), so a slot that filled while the request waited fails
    with the same SLOT_UNAVAILABLE the client would see."""
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)  # owner sees all bookings via RLS
    _assert_owns_booking(db, booking, owner)
    if booking["status"] != "pending":
        raise api_error(INVALID_RANGE, "Only pending requests can be approved.")

    md = dict(booking.get("metadata") or {})
    service = _load_service(db, md.get("service_id"))
    rules = effective_service_rules(service)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    party = int(md.get("party_size", 1))

    occ = _occ_by_id(db, cur_ids)
    _resolve_selection(rules, occ, cur_ids, md.get("resource_id"), party, credit=set())

    # The gate itself. Approving past an unmet prerequisite would make the whole
    # block advisory, so the owner has to record it as met first.
    if capability("prerequisites", service):
        outstanding = unmet_prerequisites(md, service)
        if outstanding:
            labels = ", ".join(
                p.get("label") or p["key"]
                for p in blocking_prerequisites(service)
                if p.get("key") in outstanding
            )
            raise api_error(INVALID_RANGE, f"Still outstanding: {labels}.")

    history = booking["history"] + [{"status": "confirmed", "at": iso_utc(now_utc()), "actor": "owner"}]
    updated = (
        uc.table("bookings")
        .update({"status": "confirmed", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    review = _reviews_map(db, [booking_id]).get(booking_id)
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review,
        **_names_for(db, md),
    )


@router.post("/{booking_id}/client-review")
def review_client(booking_id: str, payload: ClientReviewReq, owner: AuthUser = Depends(require_owner)):
    """Owner rates the customer after a completed booking → the customer's
    reputation. One review per booking (a re-review replaces the prior one)."""
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)
    _assert_owns_booking(db, booking, owner)

    cur_ids, _cur_start, cur_end = _span_of(db, booking, uc)
    if effective_booking_status(booking["status"], cur_end) != "completed":
        raise api_error(NOT_FOUND, "You can only rate a customer after the booking is completed.")

    md = booking.get("metadata") or {}
    # Same gate as the customer-facing review above. Without it `capabilities.
    # reviews: false` refused one direction and accepted the other, and these
    # rows feed the customer's public reputation (`GET /me/reputation`).
    service = maybe_row(db.table("services").select("*").eq("id", md.get("service_id")))
    if not capability("reviews", service):
        raise api_error(NOT_FOUND, "Reviews are not enabled here.")

    rating = max(1, min(5, round(payload.rating)))
    # One review per booking: clear any prior (service key) then insert through
    # the owner's client so RLS's client_reviews_insert_owner enforces.
    db.table("client_reviews").delete().eq("booking_id", booking_id).execute()
    uc.table("client_reviews").insert(
        {
            "booking_id": booking_id,
            "client_id": booking.get("client_id") or md.get("user_id"),
            "provider_id": md.get("provider_id"),
            "rating": rating,
            "text": (payload.text or "").strip(),
        }
    ).execute()
    row = maybe_row(db.table("client_reviews").select("*").eq("booking_id", booking_id))
    return {
        "rating": int(row["rating"]) if row else rating,
        "text": (row.get("text") if row else payload.text) or "",
        "createdAtUtc": iso_utc(row.get("created_at")) if row else None,
    }


@router.post("/{booking_id}/reject")
def reject_booking(booking_id: str, owner: AuthUser = Depends(require_owner)):
    """Owner declines a pending request → rejected (idempotent)."""
    db = get_supabase()
    uc = get_user_client(owner.token)
    booking = _load_own(uc, booking_id)
    _assert_owns_booking(db, booking, owner)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    if booking["status"] == "rejected":  # idempotent
        return serialize_booking(
            booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
            **_names_for(db, booking.get("metadata") or {}),
        )
    if booking["status"] != "pending":
        raise api_error(INVALID_RANGE, "Only pending requests can be rejected.")

    history = booking["history"] + [{"status": "rejected", "at": iso_utc(now_utc()), "actor": "owner"}]
    updated = (
        uc.table("bookings")
        .update({"status": "rejected", "history": history})
        .eq("id", booking_id)
        .execute()
        .data
    )
    updated = enforce_rls_write(updated, entity="booking")
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
        **_names_for(db, booking.get("metadata") or {}),
    )
