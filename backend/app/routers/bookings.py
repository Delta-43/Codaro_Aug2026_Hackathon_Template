# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bookings, the reworked booking loop.

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
from app.db import chunked as _chunked
from app.db import fetch_all, get_supabase, get_user_client, maybe_row
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
    entitlement_plan,
    payment_state,
    resolve_entitlement,
    resolve_options,
    resolve_party_bands,
    resolve_subject,
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
    "party_bands", "options", "subject",
)

# --- lookups ---------------------------------------------------------------


def _load_service(db, service_id: str) -> dict:
    row = maybe_row(db.table("services").select("*").eq("id", service_id))
    if row is None:
        raise api_error(NOT_FOUND, "That service no longer exists.")
    return row


def _is_capacity_violation(exc: Exception) -> bool:
    """True when a write was rejected by the slot-capacity trigger (schema.sql).
    The trigger raises SQLSTATE 23514 with a `slot_capacity_exceeded` marker; the
    marker is matched as well so a client version that surfaces the message but
    not the code is still recognised."""
    return getattr(exc, "code", None) == "23514" or "slot_capacity_exceeded" in str(exc)


def _occ_by_id(db, slot_ids: list[str]) -> dict[str, dict]:
    if not slot_ids:
        return {}
    rows = db.table("slot_occupancy").select("*").in_("slot_id", slot_ids).execute().data or []
    return {r["slot_id"]: r for r in rows}


def _slot_ids_map(uc, booking_ids: list[str]) -> dict[str, list[str]]:
    if not booking_ids:
        return {}
    out: dict[str, list[str]] = {}
    # Chunked `in_` + paged fetch: past ~1000 join rows the raw select silently
    # truncated, so later bookings fell back to single-slot spans.
    for chunk in _chunked(booking_ids):
        rows = fetch_all(
            uc.table("booking_slots").select("booking_id,slot_id").in_("booking_id", chunk),
            order=("booking_id", "slot_id"),
        )
        for r in rows:
            out.setdefault(r["booking_id"], []).append(r["slot_id"])
    return out


def _slot_time_map(db, slot_ids: list[str]) -> dict[str, tuple]:
    if not slot_ids:
        return {}
    out: dict[str, tuple] = {}
    for chunk in _chunked(slot_ids):
        rows = fetch_all(db.table("slots").select("id,starts_at,ends_at").in_("id", chunk))
        out.update({r["id"]: (r["starts_at"], r["ends_at"]) for r in rows})
    return out


def _reviews_map(db, booking_ids: list[str]) -> dict[str, dict]:
    if not booking_ids:
        return {}
    out: dict[str, dict] = {}
    for chunk in _chunked(booking_ids):
        for r in fetch_all(db.table("reviews").select("*").in_("booking_id", chunk)):
            out[r["booking_id"]] = r  # one review per booking; keep the last seen
    return out


def _name_map(db, table: str, ids: set[str]) -> dict[str, str]:
    """Batch id→name lookup for a table (providers/services). One query for the
    whole booking list, so the client doesn't fetch each provider/service by id."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    out: dict[str, str] = {}
    for chunk in _chunked(list(ids)):
        for r in fetch_all(db.table(table).select("id,name").in_("id", chunk)):
            out[r["id"]] = r.get("name") or ""
    return out


def _provider_avatar_map(db, ids: set[str]) -> dict[str, str]:
    """Batch id->avatar_url for providers, so a bookings list can show WHO the
    booking is with rather than a column of initials. Same batching as
    `_name_map`: one query for the whole list, never one per row."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    out: dict[str, str] = {}
    for chunk in _chunked(list(ids)):
        for r in fetch_all(db.table("providers").select("id,metadata").in_("id", chunk)):
            # The logo lives in `metadata`, not a column, schema.sql is frozen.
            out[r["id"]] = (r.get("metadata") or {}).get("avatar_url") or ""
    return out


def _names_for(db, md: dict) -> dict:
    """provider_name/service_name kwargs for a single booking's metadata, so a
    mutation response embeds the same names the list/get (`_enrich`) paths do."""
    pid, sid = md.get("provider_id"), md.get("service_id")
    return {
        "provider_name": _name_map(db, "providers", {pid}).get(pid, ""),
        "service_name": _name_map(db, "services", {sid}).get(sid, ""),
        "provider_avatar_url": _provider_avatar_map(db, {pid}).get(pid, ""),
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
    prov_avatars = _provider_avatar_map(db, {m.get("provider_id") for m in metas})
    # Full service rows, not just names: serialize_booking derives `loan` and
    # `payment` from the GLOBAL config when `service` is omitted, so a service
    # whose metadata overrides `payments`/`inventory` would serialize a state
    # the /pay and /return endpoints don't enforce.
    svc_map = _service_map(db, {m.get("service_id") for m in metas})
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
                service=svc_map.get(md.get("service_id")),
                provider_name=prov_names.get(md.get("provider_id"), ""),
                provider_avatar_url=prov_avatars.get(md.get("provider_id"), ""),
                service_name=(svc_map.get(md.get("service_id")) or {}).get("name", ""),
            )
        )
    return out


def _service_map(db, ids: set) -> dict[str, dict]:
    """Batch id→row lookup for services (full rows, serializers need the
    metadata override blocks, not just the name)."""
    wanted = [i for i in ids if i]
    out: dict[str, dict] = {}
    for chunk in _chunked(wanted):
        for r in fetch_all(db.table("services").select("*").in_("id", chunk)):
            out[r["id"]] = r
    return out


def _load_own(uc, booking_id: str) -> dict:
    """Load a booking through the user client (RLS scopes to own/owner). 404 if
    missing or not visible to this user."""
    row = maybe_row(uc.table("bookings").select("*").eq("id", booking_id))
    if row is None:
        raise api_error(NOT_FOUND, "That booking could not be found.")
    return row


def _owns_booking_provider(db, booking: dict, owner: AuthUser) -> bool:
    """True when the caller owns the provider this booking belongs to."""
    provider_id = (booking.get("metadata") or {}).get("provider_id")
    provider = maybe_row(db.table("providers").select("owner_id").eq("id", provider_id))
    return bool(provider) and provider.get("owner_id") == owner.id


def _assert_owns_booking(db, booking: dict, owner: AuthUser) -> None:
    """Defense-in-depth: verify the owner owns the provider this booking belongs
    to before they act on it. RLS's is_owner() lets any owner update any booking,
    so this narrows owner actions to their own providers (403 otherwise)."""
    if not _owns_booking_provider(db, booking, owner):
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
    # This is the customer tab's "my bookings": scope to the caller as CLIENT
    # server-side. An owner's RLS view is every booking on the platform, so an
    # unfiltered fetch_all paged the whole marketplace per request. Legacy rows
    # keyed only by metadata (null client_id) stay listable via the same
    # fallback identity the mutation handlers honour.
    rows = fetch_all(uc.table("bookings").select("*").eq("client_id", user.id))
    legacy = fetch_all(
        uc.table("bookings").select("*")
        .is_("client_id", "null")
        .eq("metadata->>user_id", user.id)
    )
    seen_ids = {r["id"] for r in rows}
    rows += [r for r in legacy if r["id"] not in seen_ids]
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
        # owner refunds, far better than a 500 on the commit path.
        logger.exception("Could not load entitlements for %s", user_id)
        return None
    return resolve_entitlement(rows, service)


_PATTERN_DELTAS = {"weekly": 7, "biweekly": 14}


# The pseudo-pattern that means `booking.sequence` rather than
# `recurrence.patterns`. Never a config value, the client names it to say "book
# the whole course", and `_resolve_repeat` validates it against the block.
SEQUENCE_PATTERN = "sequence"


def _occurrence_starts(first_start, pattern: str, count: int, gap_hours: int = 0) -> list:
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
        if pattern == SEQUENCE_PATTERN:
            # `sequence.minGapHours` is the SMALLEST legal gap; using it as the
            # step books the course as tightly as the config allows, which is
            # what "session 2 is a week after session 1" means in practice.
            out.append(first_start + timedelta(hours=max(1, gap_hours) * i))
        elif pattern in _PATTERN_DELTAS:
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

    A recurring booking can only land on a slot the business actually opened,
    the engine never invents availability. An occurrence with no slot is
    reported back as skipped rather than quietly dropped.
    """
    if not starts:
        return {}
    lo, hi = min(starts), max(starts)
    # Paged: a year-long series on a 30-minute resource spans thousands of
    # slots, and PostgREST's silent 1000-row cap would drop every occurrence
    # past the first page, reported to the customer as NO_SLOT for slots that
    # exist and are bookable.
    rows = fetch_all(
        db.table("slots").select("*").eq("resource_id", resource_id)
        .gte("starts_at", iso_utc(lo)).lte("starts_at", iso_utc(hi))
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
    counter must not undo it or 500 the request. The alternative, decrement
    first, then insert, spends a credit for a booking that may never exist,
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


def _refund_credit(db, md: dict) -> bool:
    """Give back the credit a booking consumed, when it is cancelled/rejected.

    Consumption happens at create/promotion even for `pending` requests, so a
    rejection (or a cancel) without this quietly burned a pass credit for a
    booking that never happened. Idempotent via the `credit_refunded` stamp the
    caller persists into metadata when this returns True; best-effort like
    `_consume_credit` (a counter must not 500 the cancel). Known limit: there
    is no per-booking consume receipt, so a booking whose best-effort consume
    failed can still refund (the entitlement drifts one credit rich), a real
    ledger row per spend, keyed by booking_id, is the fix.
    """
    ent_id = (md or {}).get("entitlement_id")
    if not ent_id or md.get("credit_refunded"):
        return False
    try:
        row = maybe_row(db.table("entitlements").select("*").eq("id", ent_id))
        if not row or row.get("credits_total") is None:
            return False
        used = int(row.get("credits_used") or 0)
        if used <= 0:
            return False
        db.table("entitlements").update({"credits_used": used - 1}).eq("id", ent_id).execute()
        return True
    except Exception:
        logger.exception("Could not refund a credit on entitlement %s", ent_id)
        return False


def _price(service: dict | None, rows: list, party: int,
           entitlement: dict | None = None, *, person_units: float | None = None,
           addons: list | None = None, subject: dict | None = None) -> dict:
    """Quote a selection through the config-driven pricing engine.

    v1 computed `priceMinorUnits * len(rows) * party` inline here. The default
    `pricing` block reproduces that exactly, so an un-pivoted service prices
    identically, but a service that declares `metadata.pricing` can now bill per
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
            # The three inputs `pricing.quote()` has always documented and never
            # been given: a weighted head count from `party.composition`, the
            # chosen `booking.options` as priced lines, and the `booking.subject`
            # a `subjectField` tier matches on.
            "person_units": person_units,
            "addons": addons or [],
            "subject": subject,
        },
    )


def _business_tz(service: dict | None):
    """The business's own timezone, time-of-day pricing tiers (peak/off-peak)
    are meaningless in UTC."""
    name = effective_service_config(service)["location"].get("timezone") or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _booking_shape(payload, service: dict, party: int) -> tuple[float | None, dict | None, list, dict | None]:
    """Resolve the request's party bands, options and subject against the config.

    Quote and create both call this, for the same reason `_price` is shared: the
    number on the confirm screen has to be the number charged, and an add-on the
    quote priced must be an add-on the booking records. A violation is raised
    before anything is written.
    """
    try:
        person_units, bands = resolve_party_bands(
            getattr(payload, "party_bands", None), party, service
        )
        addons = resolve_options(getattr(payload, "options", None), service)
        subject = resolve_subject(getattr(payload, "subject", None), service)
    except RuleViolation as e:
        raise api_error(INVALID_RANGE, str(e))
    return person_units, bands, addons, subject


@router.post("/quote")
def quote_selection(payload: QuoteReq, user: AuthUser = Depends(require_user)):
    """Price a selection without committing it.

    Runs `_resolve_selection` + `_price`, byte for byte the path
    `create_booking` takes, so the number shown on the confirm screen is the
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
    person_units, _bands, addons, subject = _booking_shape(payload, service, party)
    priced = _price(
        service, rows, party, ent,
        person_units=person_units, addons=addons, subject=subject,
    )
    return serialize_quote(priced, service, entitlement=ent)


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
    # so this is a no-op until a pivot turns one on, that is the whole point of
    # the registry: a new constraint is a config key plus a validator, never a
    # change here.
    try:
        apply_rules(
            "booking.create",
            # The zone matters: `blackouts`/`seasons` are written as local dates,
            # so a UTC comparison closes the wrong day either side of midnight.
            {"slot_starts_at": rows[0]["starts_at"], "timezone": str(_business_tz(service))},
            # THIS service's resolved timing, not the global block. `timing` is in
            # OVERRIDABLE_BLOCKS and the write gate accepts a per-service
            # `leadTimeMinutes`, reading the global block here made this the one
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
    # A quote-priced service cannot confirm on the spot either: the price does
    # not exist yet. `pricing.model: "quote"` + `capabilities.quotes` shipped in
    # v2 and gated nothing, so a quote request auto-confirmed at a total of
    # zero: the customer held a booking the business had never priced.
    by_quote = (
        effective_service_pricing(service).get("model") == "quote"
        and capability("quotes", service)
    )
    status = "confirmed" if auto_approve and not pending_prereqs and not by_quote else "pending"
    # Validated here, before anything is written: a repeat this service cannot
    # honour must not leave a committed first booking behind.
    repeat = _resolve_repeat(payload, service)
    entitlement = _entitlement(db, user.id, service)
    person_units, bands, addons, subject = _booking_shape(payload, service, party)
    priced = _price(
        service, rows, party, entitlement,
        person_units=person_units, addons=addons, subject=subject,
    )

    metadata = {
        # `metaFields.bookings` domain data (the shipped medical example declares
        # a `reason` field) merged UNDER every engine-owned key below, which
        # always win, a domain field must never be able to rewrite a price.
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
        # What was chosen, kept beside what it cost. The breakdown above already
        # carries the add-on lines; these are the SELECTIONS, so the booking can
        # be re-rendered (and an owner can see which meal to cook) without
        # reverse-engineering it from money.
        "party_bands": bands,
        "options": addons,
        "subject": subject,
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
    booking = inserted[0]
    # The booking row exists but holds no capacity until its booking_slots links
    # do (occupancy joins through them). The DB capacity trigger (schema.sql)
    # fires on this insert and rejects a link that would overbook, closing the
    # TOCTOU where two last-seat bookings both pass `_resolve_selection`'s
    # pre-insert check. On rejection, roll back the now-orphan booking and raise
    # the same code the check would. Credit is consumed only AFTER the links
    # commit, so a rolled-back booking never spends one.
    try:
        uc.table("booking_slots").insert(
            [{"booking_id": booking["id"], "slot_id": sid} for sid in ordered]
        ).execute()
    except Exception as exc:  # noqa: BLE001 - re-raised unless it's the capacity trigger
        if _is_capacity_violation(exc):
            uc.table("bookings").delete().eq("id", booking["id"]).execute()
            raise api_error(
                SLOT_UNAVAILABLE, "That time was just taken. We've refreshed availability."
            )
        raise
    _consume_credit(db, entitlement, booking["id"])
    out = serialize_booking(
        booking, slot_ids=ordered, start_utc=start, end_utc=end, review=None,
        service=service, **_names_for(db, metadata)
    )
    out["series"] = (
        None if repeat is None else _book_repeats(
            db, uc, user, payload, service, rows, party, booking["id"], metadata,
            repeat, status, (person_units, bands, addons, subject),
        )
    )
    return out


def _resolve_repeat(payload, service) -> tuple[str, int] | None:
    """Validate the repeat request and resolve its pattern + count.

    Runs BEFORE the first booking is written. These checks used to live inside
    `_book_repeats`, which is called after the first occurrence is already
    inserted, so an unsupported pattern returned 400 with a real booking
    committed and holding capacity, and a client that retried on the error
    produced a second one.

    Returns None when no repeat was asked for. Raises ApiError on a repeat this
    service cannot honour, which is now a clean rejection with nothing written.
    """
    repeat = payload.repeat
    if repeat is None or int(repeat.count or 1) <= 1:
        return None
    # `booking.sequence`, a course, a treatment plan, a multi-dose vaccination:
    # N sessions spaced by a fixed gap, bought as one enrolment. It is a series
    # with a different clock, so it rides the recurrence machinery rather than
    # growing a parallel one; the only differences are where the ceiling comes
    # from (`steps`) and how far apart the occurrences sit (`minGapHours`).
    if repeat.pattern == SEQUENCE_PATTERN:
        seq = (effective_service_config(service)["booking"] or {}).get("sequence") or {}
        if not seq.get("enabled"):
            raise api_error(INVALID_RANGE, "This service is not booked as a sequence.")
        steps = max(1, int(seq.get("steps") or 1))
        return SEQUENCE_PATTERN, max(1, min(int(repeat.count), steps))
    cfg = effective_service_config(service)["recurrence"]
    if not cfg.get("enabled") or not capability("recurrence", service):
        raise api_error(INVALID_RANGE, "This service cannot be booked as a repeating series.")
    if repeat.pattern not in (cfg.get("patterns") or []):
        allowed = ", ".join(cfg.get("patterns") or []) or "none"
        raise api_error(INVALID_RANGE, f"Unsupported repeat pattern. Allowed: {allowed}.")
    # The config's ceiling wins over whatever the client asked for.
    limit = int(cfg.get("maxOccurrences") or 1)
    return repeat.pattern, max(1, min(int(repeat.count), limit))


def _book_repeats(db, uc, user, payload, service, rows, party, first_id, first_md,
                  resolved: tuple[str, int], status: str,
                  shape: tuple = (None, None, None, None)) -> dict | None:
    """Book the remaining occurrences of a repeating series.

    Returns `{id, pattern, bookedIds, skipped}` or None when the request asked
    for no repeat. The FIRST occurrence is already committed by the caller, it
    is the booking the customer selected, and it must succeed or fail on its
    own merits. Every later occurrence is best-effort: it lands only if the
    business actually opened a slot at that instant with room for the party.

    Occurrences that cannot be booked are REPORTED, not silently dropped. A
    series that quietly books 3 of 12 while the customer believes they have 12
    is the worst outcome here, so the caller gets both lists back.
    """
    pattern, count = resolved
    first_start = _parse(rows[0]["starts_at"])
    if first_start is None:
        return None

    series_id = first_id  # the first booking's id names the series
    # The whole SPAN repeats, not just its first slot: a two-hour clean booked
    # weekly needs both slots each week. Shifting only the first would fail
    # `minSlotsPerBooking` on every occurrence of any multi-slot service.
    span = [_parse(r["starts_at"]) for r in rows]
    offsets = [(t - first_start) for t in span if t is not None]
    seq_gap = int(
        ((effective_service_config(service)["booking"] or {}).get("sequence") or {}).get(
            "minGapHours"
        ) or 0
    )
    occurrence_starts = _occurrence_starts(first_start, pattern, count, seq_gap)[1:]
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
        # The same gates the first occurrence passed. Skipping them let a series
        # book past `advanceBookingWindowDays` / `leadTimeMinutes` that a direct
        # POST for the identical date would be refused, so one rule gave two
        # answers depending on which path reached it.
        try:
            apply_rules("booking.create",
                        {"slot_starts_at": occ_rows[0]["starts_at"],
                         "timezone": str(_business_tz(service))},
                        effective_service_config(service)["timing"])
        except RuleViolation as exc:
            skipped.append({"startUtc": iso_utc(start_at), "reason": "INVALID_RANGE",
                            "detail": str(exc)})
            continue
        ent = _entitlement(db, user.id, service)
        # The SAME shape as the first occurrence. Pricing each later one as a
        # bare selection charged a course's second session without the add-ons
        # and without the child weighting the first one was quoted with.
        occ_priced = _price(
            service, occ_rows, party, ent,
            person_units=shape[0], addons=shape[2], subject=shape[3],
        )
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
        "pattern": pattern,
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

    # Owner powers apply on the owner's OWN provider, including a booking the
    # owner recorded under their own account (walk-in/phone entry). An owner
    # touching a booking they made as a customer of ANOTHER business acts as a
    # client (cutoff applies); anyone who is neither the client nor the owning
    # provider is refused, since RLS's is_owner() alone shows them the row.
    is_client = (booking.get("client_id") or md.get("user_id")) == user.id
    acting_as_owner = user.is_owner and _owns_booking_provider(db, booking, user)
    if not is_client and not acting_as_owner:
        raise HTTPException(403, "You can only manage bookings for your own business.")

    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    if effective_booking_status(booking["status"], cur_end) != "confirmed":
        raise api_error(CUTOFF_PASSED, "Only upcoming bookings can be moved.")
    cutoff = rules["cancellationCutoffHours"]
    if not acting_as_owner and cur_start and within_cutoff(cur_start, cutoff):
        raise api_error(CUTOFF_PASSED, f"Changes closed, within {cutoff}h of the start.")

    party = int(md.get("party_size", 1))
    resource_id = md.get("resource_id")
    occ = _occ_by_id(db, payload.new_slot_ids)
    rows = _resolve_selection(
        rules, occ, payload.new_slot_ids, resource_id, party, credit=set(cur_ids)
    )
    ordered = [r["slot_id"] for r in rows]
    new_start, new_end = rows[0]["starts_at"], rows[-1]["ends_at"]

    # The calendar gates create dispatches (advance window, blackouts, seasons)
    # apply to the NEW date too, otherwise book-then-reschedule was a two-step
    # bypass into any closed day. `leadTimeMinutes` is deliberately zeroed:
    # changing an existing booking is governed by the cancellation window, and
    # moving onto a soon slot is pinned as allowed (see
    # test_lead_time_does_not_gate_a_reschedule_onto_a_soon_slot). Owners are
    # exempt, mirroring the cutoff waiver above, accommodating a regular
    # beyond the window or onto a closed day is the owner's call to make.
    if not acting_as_owner:
        try:
            apply_rules(
                "booking.create",
                {"slot_starts_at": rows[0]["starts_at"], "timezone": str(_business_tz(service))},
                {**effective_service_config(service)["timing"], "leadTimeMinutes": 0},
            )
        except RuleViolation as e:
            raise api_error(INVALID_RANGE, str(e))

    # Atomic slot swap: replace the join rows, then update the booking.
    uc.table("booking_slots").delete().eq("booking_id", booking_id).execute()
    uc.table("booking_slots").insert(
        [{"booking_id": booking_id, "slot_id": sid} for sid in ordered]
    ).execute()

    md["slot_ids"] = ordered
    # Reprice with the SAME shape that priced the original: the stored
    # `options` are already resolved priced lines, `subject` is the validated
    # dict, and person-units re-derive from the stored band counts. Without
    # these a pure time move silently dropped add-ons and child weighting.
    try:
        person_units, _ = resolve_party_bands(md.get("party_bands"), party, service)
    except RuleViolation:
        person_units = None  # config changed under an old booking; raw party pricing
    # The entitlement that priced this booking keeps pricing it, and the
    # consume receipt (entitlement_id) is IMMUTABLE, the refund path depends
    # on it. Re-resolving here nulled the receipt whenever the pass was
    # exhausted (by this very booking's spend) and repriced a covered booking
    # at list price; only a booking that never held one resolves fresh, for
    # the CLIENT (an owner moving it must keep the customer's pricing).
    stored_ent_id = md.get("entitlement_id")
    if stored_ent_id:
        ent = None
        held = maybe_row(db.table("entitlements").select("*").eq("id", stored_ent_id))
        plan = entitlement_plan((held or {}).get("plan_key"), service)
        if held is not None and plan is not None:
            total = held.get("credits_total")
            ent = {
                "key": plan.get("key"),
                "label": plan.get("label") or plan.get("key"),
                "discountBps": int(plan.get("discountBps") or 0),
                "creditsRemaining": None if total is None
                else int(total) - int(held.get("credits_used") or 0),
                "row": held,
                "plan": plan,
            }
    else:
        subject_id = booking.get("client_id") or md.get("user_id") or user.id
        ent = _entitlement(db, subject_id, service)
        md["entitlement_key"] = (ent or {}).get("key")
        md["entitlement_id"] = ((ent or {}).get("row") or {}).get("id")
    repriced = _price(
        service, rows, party, ent,
        person_units=person_units, addons=md.get("options") or [], subject=md.get("subject"),
    )
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
    # CAS on confirmed: a cancel committing during this handler's long window
    # must not be silently resurrected (it already refunded the credit and
    # promoted the waitlist). The swapped join rows stay on the lost row,
    # they hold no capacity, since occupancy counts confirmed only.
    updated = (
        uc.table("bookings")
        .update({"slot_id": ordered[0], "status": "confirmed", "history": history, "metadata": md})
        .eq("id", booking_id)
        .eq("status", "confirmed")
        .execute()
        .data
    )
    if not updated:
        current = _load_own(uc, booking_id)
        if current["status"] != "confirmed":
            raise api_error(CUTOFF_PASSED, "Only upcoming bookings can be moved.")
        updated = enforce_rls_write(updated, entity="booking")
    review = _reviews_map(db, [booking_id]).get(booking_id)
    return serialize_booking(
        updated[0], slot_ids=ordered, start_utc=new_start, end_utc=new_end, review=review,
        service=service, **_names_for(db, md),
    )


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, user: AuthUser = Depends(require_user)):
    db = get_supabase()
    uc = get_user_client(user.token)
    booking = _load_own(uc, booking_id)
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)

    # Same ownership narrowing as reschedule: owner powers on the owner's OWN
    # provider (their own walk-in bookings included); the booking's client acts
    # as a client; anyone else is refused despite RLS's is_owner() visibility.
    _cancel_md = booking.get("metadata") or {}
    is_client = (booking.get("client_id") or _cancel_md.get("user_id")) == user.id
    acting_as_owner = user.is_owner and _owns_booking_provider(db, booking, user)
    if not is_client and not acting_as_owner:
        raise HTTPException(403, "You can only manage bookings for your own business.")

    # ONE tolerant fetch for the whole handler: a cancel must succeed even when
    # the service was deleted out from under the booking (`_load_service` would
    # 404 an operation that must commit; the rules resolver treats None as the
    # config defaults). The cutoff, idempotent and response paths all reuse it.
    service = maybe_row(db.table("services").select("*").eq("id", _cancel_md.get("service_id")))

    if booking["status"] == "cancelled":  # idempotent
        review = _reviews_map(db, [booking_id]).get(booking_id)
        return serialize_booking(
            booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review,
            service=service, **_names_for(db, _cancel_md),
        )

    if booking["status"] == "rejected":
        # The owner already declined it (and any credit was refunded then);
        # flipping it to cancelled would overwrite that decision.
        raise api_error(INVALID_RANGE, "This request was declined, there is nothing to cancel.")
    if effective_booking_status(booking["status"], cur_end) == "completed":
        raise api_error(CUTOFF_PASSED, "Completed bookings can't be cancelled.")
    if not acting_as_owner:
        cutoff = effective_service_rules(service)["cancellationCutoffHours"]
        if cur_start and within_cutoff(cur_start, cutoff):
            raise api_error(CUTOFF_PASSED, f"Changes closed, within {cutoff}h of the start.")

    md = dict(booking.get("metadata") or {})
    md["cancelled_at_utc"] = iso_utc(now_utc())
    history = booking["history"] + [
        {"status": "cancelled", "at": iso_utc(now_utc()), **({"actor": "owner"} if acting_as_owner else {})}
    ]
    # Compare-and-set on the live statuses: two racing transitions (double
    # cancel, or a cancel racing the owner's reject) must not both commit,
    # whichever loses gets an empty write instead of a second refund.
    updated = (
        uc.table("bookings")
        .update({"status": "cancelled", "history": history, "metadata": md})
        .eq("id", booking_id)
        .in_("status", ["confirmed", "pending"])
        .execute()
        .data
    )
    if not updated:
        # An empty CAS write usually means a concurrent transition won, not an
        # RLS denial, answer for the CURRENT state instead of a security 403.
        current = _load_own(uc, booking_id)
        if current["status"] == "cancelled":
            # Lost a cancel/cancel race: the outcome the caller wanted.
            return serialize_booking(
                current, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
                review=_reviews_map(db, [booking_id]).get(booking_id),
                service=service, **_names_for(db, _cancel_md),
            )
        if current["status"] == "rejected":
            raise api_error(INVALID_RANGE, "This request was declined, there is nothing to cancel.")
        updated = enforce_rls_write(updated, entity="booking")
    # Refund only AFTER the transition committed: decrementing first meant a
    # failed write refunded with no stamp, so a retried cancel refunded twice.
    # The stamp is written on top of the row as just persisted. A crash between
    # the decrement and the stamp remains a narrow window, closing it fully
    # needs an entitlement ledger row.
    if _refund_credit(db, md):
        md = dict(updated[0].get("metadata") or md)
        md["credit_refunded"] = True
        uc.table("bookings").update({"metadata": md}).eq("id", booking_id).execute()
    # A cancellation is the moment a seat frees. Hand it to the head of the
    # queue if the config asks for that (`timing.waitlist.autoPromote`).
    promote_from_waitlist(db, cur_ids, service)
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=None,
        service=service, **_names_for(db, md),
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
    # open, the block's own contract is that a false capability hides the
    # surface AND refuses the write. Resolved per service, so one business on a
    # marketplace can run without reviews.
    service = maybe_row(db.table("services").select("*").eq("id", md.get("service_id")))
    if not capability("reviews", service):
        raise api_error(NOT_FOUND, "Reviews are not enabled here.")

    rating = max(1, min(5, round(payload.rating)))
    # One review per booking: clear any prior (service key, no user delete
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
        service=service, **_names_for(db, md),
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

    The overdue fee is COMPUTED from `returned_at_utc`, never stored, see
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
    # Precondition: only the none→returned transition commits, so a double-tap
    # can't re-stamp the timestamp (and inflate the overdue fee) or clobber
    # metadata written since our read.
    updated = uc.table("bookings").update({
        "metadata": md,
        # Append-only, like every other status change on this table.
        "history": list(booking.get("history") or []) + [
            {"status": "returned", "at": md["returned_at_utc"], "actor": "owner"}
        ],
    }).eq("id", booking_id).is_("metadata->>returned_at_utc", "null").execute().data
    if not updated:
        raise api_error(INVALID_RANGE, "This is already marked returned.")
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

    `amount` defaults to whatever is still outstanding, so the common case,
    "they paid the bill", needs no body. Partial payments accumulate, which is
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

    prior = md.get("amount_paid_minor_units")
    md["amount_paid_minor_units"] = int(prior or 0) + taken
    cur_ids, cur_start, cur_end = _span_of(db, booking, uc)
    # Precondition on the PRIOR paid amount: two concurrent payments must not
    # both read the same base and silently lose one. `->>` yields text and the
    # native value stringifies identically, so equality holds on both sides.
    q = uc.table("bookings").update({
        "metadata": md,
        "history": list(booking.get("history") or []) + [
            {"status": "payment_recorded", "amount": taken,
             "at": iso_utc(now_utc()), "actor": "owner"}
        ],
    }).eq("id", booking_id)
    if prior is None:
        q = q.is_("metadata->>amount_paid_minor_units", "null")
    else:
        q = q.eq("metadata->>amount_paid_minor_units", int(prior))
    updated = q.execute().data
    if not updated:
        raise api_error(
            INVALID_RANGE, "The payment state just changed, refresh and retry.", status=409
        )
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

    Idempotent, re-recording a met prerequisite is a no-op, so a double-tap in
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
    # CAS on pending: approving a request the client cancelled mid-flight must
    # not resurrect it as confirmed (the cancel already refunded any credit and
    # promoted the waitlist). The pre-check above re-read occupancy, but the DB
    # capacity trigger is the backstop for the race between that read and this
    # write, a confirm that would overbook is rejected here too.
    try:
        updated = (
            uc.table("bookings")
            .update({"status": "confirmed", "history": history})
            .eq("id", booking_id)
            .eq("status", "pending")
            .execute()
            .data
        )
    except Exception as exc:  # noqa: BLE001 - re-raised unless it's the capacity trigger
        if _is_capacity_violation(exc):
            raise api_error(SLOT_UNAVAILABLE, "That time filled up before this could be approved.")
        raise
    if not updated:
        current = _load_own(uc, booking_id)
        if current["status"] != "pending":
            raise api_error(INVALID_RANGE, "Only pending requests can be approved.")
        updated = enforce_rls_write(updated, entity="booking")
    review = _reviews_map(db, [booking_id]).get(booking_id)
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end, review=review,
        service=service, **_names_for(db, md),
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
    md = booking.get("metadata") or {}
    service = maybe_row(db.table("services").select("*").eq("id", md.get("service_id")))

    if booking["status"] == "rejected":  # idempotent
        return serialize_booking(
            booking, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
            service=service, **_names_for(db, md),
        )
    if booking["status"] != "pending":
        raise api_error(INVALID_RANGE, "Only pending requests can be rejected.")

    history = booking["history"] + [{"status": "rejected", "at": iso_utc(now_utc()), "actor": "owner"}]
    # Compare-and-set on pending: a reject racing a cancel (or a double reject)
    # must not both commit and both refund. Status/history only, writing back
    # the metadata copy read at the top would clobber concurrent stamps.
    updated = (
        uc.table("bookings")
        .update({"status": "rejected", "history": history})
        .eq("id", booking_id)
        .eq("status", "pending")
        .execute()
        .data
    )
    if not updated:
        # Empty CAS usually means a concurrent transition won, answer for the
        # current state rather than raising a security-framed 403.
        current = _load_own(uc, booking_id)
        if current["status"] == "rejected":
            return serialize_booking(
                current, slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
                service=service, **_names_for(db, md),
            )
        if current["status"] != "pending":
            raise api_error(INVALID_RANGE, "Only pending requests can be rejected.")
        updated = enforce_rls_write(updated, entity="booking")
    # Refund only AFTER the transition committed (same ordering as cancel).
    if _refund_credit(db, md):
        stamped = dict(updated[0].get("metadata") or md)
        stamped["credit_refunded"] = True
        uc.table("bookings").update({"metadata": stamped}).eq("id", booking_id).execute()
    return serialize_booking(
        updated[0], slot_ids=cur_ids, start_utc=cur_start, end_utc=cur_end,
        service=service, **_names_for(db, md),
    )
