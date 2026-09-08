# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Row → wire-shape serializers.

The frontend contract (`frontend/src/types/domain.ts`) is **camelCase** and models
`Provider / Service / Resource / Slot / Booking / User / DayAvailability /
MonthDensityCell`. The database is snake_case and stores the extra domain fields
in each base table's `metadata jsonb` (schema is frozen). These pure functions
are the single place that maps between the two — every router returns shapes
produced here, so the JSON the frontend receives matches its types exactly.

Metadata key conventions (snake_case; this module is the authority, and
`seed.py` writes the same keys):
  resources.metadata: service_id, capacity, active, attributes[{label,value}],
                      image_url, owner_id
  slots.metadata:     service_id
  bookings.metadata:  party_size, reference, price_minor_units, currency,
                      provider_id, service_id, resource_id, user_id,
                      change_history[{at_utc,from_start_utc,to_start_utc}],
                      slot_ids[]
Time: every timestamp on the wire is UTC ISO-8601 with a trailing 'Z'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from app.clock import now_utc
from app.config import get_config
from app.rules import (
    capability,
    payment_state,
    entitlement_plan,
    effective_auto_approve,
    effective_service_config,
    effective_service_pricing,
    effective_service_rules,
)

# --- time helpers ----------------------------------------------------------


def _attribute_rows(value: object) -> list[dict]:
    """Normalise `resources.metadata.attributes` to the [{label, value}] the
    clients expect. Anything else degrades to an empty list rather than being
    passed through to break the caller; a dict is rendered as its own pairs,
    which is the one wrong shape with an obvious right reading."""
    if isinstance(value, list):
        return [r for r in value if isinstance(r, dict) and "label" in r and "value" in r]
    if isinstance(value, dict):
        return [{"label": str(k), "value": str(v)} for k, v in value.items()]
    return []


def _parse(value: Any) -> Optional[datetime]:
    """Coerce a DB timestamp (str or datetime) to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(value: Any) -> Optional[str]:
    """Format a DB timestamp as UTC ISO-8601 with a trailing 'Z' (millis, no µs)."""
    dt = _parse(value)
    if dt is None:
        return None
    # Millisecond precision, always 'Z' — matches the frontend's IsoUtc contract.
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _now(now: Optional[datetime] = None) -> datetime:
    return now or now_utc()


# --- derived enums ---------------------------------------------------------

SLOT_AVAILABLE = "available"
SLOT_PARTIAL = "partially_booked"
SLOT_FULL = "full"
SLOT_BLOCKED = "blocked"
SLOT_PAST = "past"


def derive_slot_status(
    end_utc: Any, capacity: int, booked_count: int, now: Optional[datetime] = None
) -> str:
    """The single source of slot status, mirroring the frontend's deriveSlotStatus:
    past → blocked (cap<=0) → full → partially_booked → available."""
    end = _parse(end_utc)
    if end is not None and end <= _now(now):
        return SLOT_PAST
    if capacity <= 0:
        return SLOT_BLOCKED
    if booked_count >= capacity:
        return SLOT_FULL
    if booked_count > 0:
        return SLOT_PARTIAL
    return SLOT_AVAILABLE


def effective_booking_status(
    status: str, end_utc: Any, now: Optional[datetime] = None
) -> str:
    """Wire BookingStatus is confirmed|cancelled|completed|pending|rejected.
    A stored 'confirmed' booking whose end is in the past reads as 'completed'.
    'pending' (awaiting owner approval on a manual-approve service) and
    'rejected' (owner declined) pass through unchanged — a pending request is
    never auto-completed just because its slot elapsed; the owner still acts on
    it (or it's surfaced as stale)."""
    if status == "confirmed":
        end = _parse(end_utc)
        if end is not None and end <= _now(now):
            return "completed"
        return "confirmed"
    if status in ("cancelled", "pending", "rejected"):
        return status
    # 'rescheduled' is only ever a transient/history value; treat as confirmed.
    return "confirmed"


# --- entity serializers ----------------------------------------------------


def serialize_provider(
    row: dict,
    *,
    service_ids: Iterable[str] = (),
    review_sum: float = 0.0,
    review_count: int = 0,
    price_from: Optional[int] = None,
    currency: str = "",
) -> dict:
    md = row.get("metadata") or {}
    loc = md.get("location") or {}
    # rating/reviewCount blend the seeded catalog baseline (metadata) with real
    # reviews as they accrue: count = seed + real, rating = pooled average. This
    # keeps a seeded "318 reviews @4.7" realistic while still reflecting new ones.
    seed_rating = float(md.get("rating", 0) or 0)
    seed_count = int(md.get("review_count", 0) or 0)
    total_count = seed_count + int(review_count)
    if total_count > 0:
        eff_rating = (seed_rating * seed_count + float(review_sum)) / total_count
    else:
        eff_rating = 0.0
    eff_count = total_count
    return {
        "id": row["id"],
        "name": row["name"],
        "avatarUrl": md.get("avatar_url", ""),
        "coverUrl": md.get("cover_url"),
        "tagline": md.get("tagline", ""),
        "bio": md.get("bio", ""),
        "categoryId": row.get("category_id") or md.get("category_id") or "",
        "location": {
            "city": loc.get("city", ""),
            "country": loc.get("country", ""),
            "lat": loc.get("lat", 0),
            "lng": loc.get("lng", 0),
        },
        "rating": round(eff_rating, 1),
        "reviewCount": eff_count,
        # Cheapest of the provider's services, so results can be ordered by price
        # without fetching each service. null when the provider has no priced
        # service (nothing to sort on); `currency` is that service's currency.
        "priceFromMinorUnits": price_from,
        "currency": currency or "",
        "links": md.get("links") or [],
        "publicCode": row.get("public_code") or "",
        "serviceIds": list(service_ids),
    }


def serialize_service(row: dict, *, resource_ids: Iterable[str] = ()) -> dict:
    md = row.get("metadata") or {}
    pricing = effective_service_pricing(row)
    # Resolved, not the raw columns. `effective_service_rules` puts an explicit
    # `metadata.timing` / `metadata.booking` override ABOVE the column, so every
    # one of these advertised the column while the booking path enforced the
    # override: the UI offered one slot where the API demanded four, and showed a
    # 24h cancellation window it closed at 2h. Same fix as `priceMinorUnits`
    # below, which is the only one of the seven that had it.
    rules = effective_service_rules(row)
    # Resolved ONCE and shared: both `autoApprove` and `capabilities` read from
    # this, instead of each triggering its own full block merge + revalidation.
    svc_config = effective_service_config(row)
    return {
        "id": row["id"],
        "providerId": row["provider_id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "imageUrl": md.get("image_url"),
        "bookingModel": rules["bookingModel"],
        "slotDurationMinutes": rules["slotDurationMinutes"],
        "minSlotsPerBooking": rules["minSlotsPerBooking"],
        "maxSlotsPerBooking": rules["maxSlotsPerBooking"],
        # Resolved, not the raw column: a service with a `metadata.pricing`
        # override is charged through `effective_service_pricing`, so reporting
        # the column here advertised one price and billed another.
        "priceMinorUnits": pricing["rate"]["amountMinorUnits"],
        "currency": pricing["currency"],
        "cancellationCutoffHours": rules["cancellationCutoffHours"],
        # Owner-controlled: when False, new bookings for this service land as
        # 'pending' and wait in the Requests tab; when True (default) they
        # confirm immediately. Rides in metadata (services columns are fixed).
        #
        # Resolved through the SAME helper the booking path uses. Reading
        # `metadata.auto_approve` directly meant a service whose confirmation came
        # from a `timing.confirmation` override reported `autoApprove: true` on the
        # wire while actually creating pending bookings.
        "autoApprove": effective_auto_approve(row, config=svc_config),
        # Resolved per service, because `capabilities` is in OVERRIDABLE_BLOCKS
        # and the routers gate on `capability(name, service)`. Serving only the
        # global block over /config left the client unable to see a per-service
        # override, so it rendered a review control the API then refused.
        "capabilities": svc_config["capabilities"],
        # The shape of the offer, so the UI can describe it before a selection
        # exists. `priceMinorUnits` above is only the base rate; under any model
        # other than the default it is not the price, and rendering it alone as
        # "€65" was wrong for every tiered/per-person/subscription service.
        "pricingModel": pricing.get("model") or "fixed",
        "rateUnit": (pricing.get("rate") or {}).get("per") or "slot",
        # `pricing.chargePerPerson` — whether the rate is multiplied by heads.
        # Served so the client can PREVIEW a total with the same formula the
        # engine bills with; without it a shared court read as per-head.
        "chargePerPerson": bool(pricing.get("chargePerPerson", True)),
        # How money is collected. `none` means the product carries no payment at
        # all; `invoice_after` means nothing is due at booking time — a confirm
        # screen showing "Total" with a pay affordance is wrong in both cases.
        "paymentFlow": svc_config["payments"].get("flow") or "none",
        "billingCycle": svc_config["payments"].get("billingCycle") or "none",
        # What must be satisfied before this can be confirmed. Declared in the
        # config since v2 and served nowhere, so a customer met the block only
        # as a rejection after committing.
        # Gated on the capability like waitlist/recurrence below: enforcement
        # (bookings.create/approve) ANDs the capability, so serving the list on
        # a capability-off deployment advertised a step the API never enforced.
        "prerequisites": [
            {
                "key": p.get("key"),
                "kind": p.get("kind"),
                "label": p.get("label") or p.get("key"),
                "appliesTo": p.get("appliesTo"),
                "required": bool(p.get("required")),
                "blocksConfirmation": bool(p.get("blocksConfirmation")),
            }
            # Global, not per-service: `prerequisites` is a LIST, so it is
            # deliberately absent from OVERRIDABLE_BLOCKS (block overrides
            # deep-merge dicts) and `effective_service_config` never carries it.
            for p in (get_config().get("prerequisites") or [])
        ] if capability("prerequisites", row) else [],
        # What repeat patterns this service offers (`recurrence`). Gated on the
        # capability too, so a config that declares patterns but turns the
        # capability off never renders a control the API would refuse.
        # Whether this service runs a queue for full slots (`timing.waitlist`),
        # already gated on the capability so the UI needs only this one flag.
        "waitlist": {
            "enabled": bool((svc_config["timing"].get("waitlist") or {}).get("enabled"))
            and capability("waitlist", row),
        },
        "recurrence": {
            "enabled": bool(svc_config["recurrence"].get("enabled"))
            and capability("recurrence", row),
            "patterns": list(svc_config["recurrence"].get("patterns") or []),
            "maxOccurrences": int(svc_config["recurrence"].get("maxOccurrences") or 1),
        },
        # The SHAPE of the offer. Every one of these blocks shipped in v2, was
        # validated at load, and then reached no client — so a config could
        # declare child pricing, paid add-ons, a per-participant intake, a course
        # of four sessions or a two-part payment schedule and the app had no way
        # to render, let alone collect, any of it.
        #
        # Resolved per service (all of `booking`/`payments`/`location` are in
        # OVERRIDABLE_BLOCKS), so a marketplace where one tenant sells add-ons
        # and another does not serves each the truth about itself.
        "unitKind": svc_config["booking"].get("unitKind") or "time_slot",
        # The size of the unit the customer picks. `none` means there is no
        # calendar at all — the customer sends a REQUEST and the business comes
        # back with a time — so the client needs this to decide whether to render
        # a date picker or a "we will contact you" form. Resolved per service, so
        # one tenant's date-less enquiry sits beside another's time grid.
        "granularity": svc_config["booking"].get("granularity") or "minute",
        # How long the business says it takes to answer a request
        # (`timing.approvalWindowHours`). Display only: nothing expires a pending
        # request server-side yet, so this is the promise being made, not a
        # deadline the engine keeps.
        "approvalWindowHours": svc_config["timing"].get("approvalWindowHours"),
        "party": {
            "mode": (svc_config["booking"].get("party") or {}).get("mode") or "individual",
            "min": int((svc_config["booking"].get("party") or {}).get("min") or 1),
            "max": (svc_config["booking"].get("party") or {}).get("max"),
            # [{key, label, priceFactor}] — the bands a party splits into. Empty
            # list (not null) so the client can render `.length` without a guard.
            "composition": list((svc_config["booking"].get("party") or {}).get("composition") or []),
            "matchResourceCapacity": bool(
                (svc_config["booking"].get("party") or {}).get("matchResourceCapacity")
            ),
        },
        "subject": {
            "enabled": bool((svc_config["booking"].get("subject") or {}).get("enabled")),
            "noun": (svc_config["booking"].get("subject") or {}).get("noun") or "Subject",
            "fields": list((svc_config["booking"].get("subject") or {}).get("fields") or []),
        },
        # Paid extras. Priced server-side by `rules.resolve_options`, so these
        # descriptors are for rendering the controls only — a client that invents
        # an option key or a price is rejected, not believed.
        "options": list(svc_config["booking"].get("options") or []),
        "sequence": {
            "enabled": bool((svc_config["booking"].get("sequence") or {}).get("enabled")),
            "steps": int((svc_config["booking"].get("sequence") or {}).get("steps") or 1),
            "minGapHours": int((svc_config["booking"].get("sequence") or {}).get("minGapHours") or 0),
            "maxGapHours": (svc_config["booking"].get("sequence") or {}).get("maxGapHours"),
        },
        # When each part of the money is due (`payments.schedule`). Display-only:
        # no payments table exists, so this describes the terms the customer is
        # agreeing to, which is exactly what a confirm screen owes them.
        "paymentSchedule": list(svc_config["payments"].get("schedule") or []),
        # Where the service happens. A deployment offering pickup/delivery/remote
        # has to say so before the booking, not after.
        "locationModes": list(svc_config["location"].get("modes") or ["on_site"]),
        "locationDefault": svc_config["location"].get("default") or "on_site",
        "resourceIds": list(resource_ids),
    }


def loan_state(md: dict, end_utc, service: dict | None = None, now=None) -> dict | None:
    """The return leg of a rentable booking, or None when nothing is loaned.

    `inventory.returnRequired` deployments (ski hire, a tool library, plant
    rental) do not finish when the slot ends — the item has to come back, and
    late costs money. The whole block was declared and enforced by nothing: a
    tool library could state a 168-hour loan and a 100/day overdue fee and the
    engine would treat the booking as complete the moment the slot ended.

    The booking IS the loan record, so this rides in `bookings.metadata` rather
    than a new table — base tables stay frozen and new fields go in metadata.

    `dueBackUtc` is slot end + `loanPeriodHours`; a null loan period means the
    item is due when the booking ends. The fee is computed, never stored: it
    changes with the clock, so persisting it would be stale the next day.
    """
    inventory = (effective_service_config(service) if service is not None
                 else {"inventory": get_config()["inventory"]})["inventory"]
    if not inventory.get("returnRequired"):
        return None
    end = _parse(end_utc)
    if end is None:
        return None
    hours = inventory.get("loanPeriodHours")
    due = end + timedelta(hours=int(hours)) if hours else end
    returned_at = md.get("returned_at_utc")
    # Single clock source (app.clock via `_now`), so a frozen test clock and the
    # booking-status derivation in the same serialize call agree — not a second,
    # unfreezable `datetime.now()` that drifts from the rest of this module.
    now = _now(now)
    reference = _parse(returned_at) if returned_at else now
    # Whole days late, floored: a business that charges "per day overdue" does
    # not bill a day that has not elapsed.
    days_late = max(0, (reference - due).days) if reference > due else 0
    per_day = int(inventory.get("overdueFeePerDayMinorUnits") or 0)
    return {
        "dueBackUtc": iso_utc(due),
        "returnedAtUtc": iso_utc(returned_at) if returned_at else None,
        "daysOverdue": days_late,
        "overdueFeeMinorUnits": days_late * per_day,
        "overdueFeePerDayMinorUnits": per_day,
    }


def serialize_entitlement(row: dict) -> dict:
    """One `entitlements` row on the wire. `plan` is resolved from the config so
    the client never has to hold the catalogue to render what it owns."""
    plan = entitlement_plan(row.get("plan_key")) or {}
    total = row.get("credits_total")
    return {
        "id": row["id"],
        "planKey": row.get("plan_key"),
        # Falls back to the raw key: a retired plan still has to render as
        # SOMETHING in the customer's history rather than an empty label.
        "label": plan.get("label") or row.get("plan_key"),
        "status": row.get("status"),
        "discountBps": int(plan.get("discountBps") or 0),
        "creditsTotal": total,
        "creditsUsed": int(row.get("credits_used") or 0),
        "creditsRemaining": None if total is None
        else max(0, int(total) - int(row.get("credits_used") or 0)),
        "startsAt": iso_utc(row.get("starts_at")) if row.get("starts_at") else None,
        "endsAt": iso_utc(row.get("ends_at")) if row.get("ends_at") else None,
    }


def serialize_quote(priced: dict, service: dict | None = None, *,
                    entitlement: dict | None = None) -> dict:
    """A `pricing.quote()` result on the wire.

    `breakdown` is the engine's own line list — base rate, tier, each fee, the
    cap adjustment — so the UI can show WHY a total is what it is instead of
    reproducing the arithmetic and drifting from it.
    """
    config = effective_service_config(service) if service is not None else None
    payments = (config or {}).get("payments") or {}
    return {
        "amountMinorUnits": priced.get("amountMinorUnits", 0),
        "currency": priced.get("currency") or "EUR",
        "depositMinorUnits": priced.get("depositMinorUnits", 0) or 0,
        "breakdown": [
            {
                "label": line.get("label"),
                "amountMinorUnits": line.get("amountMinorUnits", 0),
            }
            for line in (priced.get("breakdown") or [])
        ],
        # Repeated here so a quote is self-contained: the confirm screen decides
        # what to say about money from this one response.
        "paymentFlow": payments.get("flow") or "none",
        # The entitlement that was applied, so the customer can see WHY they were
        # charged less — a silent discount is as confusing as a silent surcharge.
        "entitlement": None if not entitlement else {
            "key": entitlement.get("key"),
            "label": entitlement.get("label"),
            "discountBps": entitlement.get("discountBps", 0),
            "creditsRemaining": entitlement.get("creditsRemaining"),
        },
    }


def serialize_resource(row: dict) -> dict:
    md = row.get("metadata") or {}
    return {
        "id": row["id"],
        "serviceId": md.get("service_id", ""),
        "name": row["name"],
        "description": row.get("description"),
        "imageUrl": md.get("image_url"),
        "capacity": int(md.get("capacity", 1)),
        # `metadata` is the no-migration extension point, so its contents are
        # not schema-checked: a row can carry anything. The API contract here is
        # a LIST of {label,value} (see types/domain.ts) and the provider page
        # maps over it, so a dict or string sent straight through crashed the
        # page with "attributes.slice is not a function". Coerce instead.
        "attributes": _attribute_rows(md.get("attributes")),
        "active": bool(md.get("active", True)),
    }


def serialize_slot(
    row: dict,
    *,
    booked_count: int = 0,
    service_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    md = row.get("metadata") or {}
    capacity = int(row.get("capacity", 1))
    sid = service_id or md.get("service_id", "")
    return {
        "id": row["id"],
        "serviceId": sid,
        "resourceId": row["resource_id"],
        "startUtc": iso_utc(row["starts_at"]),
        "endUtc": iso_utc(row["ends_at"]),
        "capacity": capacity,
        "bookedCount": int(booked_count),
        "status": derive_slot_status(row["ends_at"], capacity, booked_count, now),
    }


def _change_history(md: dict) -> list:
    out = []
    for e in md.get("change_history") or []:
        out.append(
            {
                "atUtc": iso_utc(e.get("at_utc") or e.get("atUtc")),
                "fromStartUtc": iso_utc(e.get("from_start_utc") or e.get("fromStartUtc")),
                "toStartUtc": iso_utc(e.get("to_start_utc") or e.get("toStartUtc")),
            }
        )
    return out



def _declared_booking_meta(md: dict) -> dict:
    """Only the keys `metaFields.bookings` declares, so a config's custom fields
    round-trip to the client without leaking engine-owned metadata alongside."""
    try:
        fields = get_config().get("metaFields", {}).get("bookings") or []
    except Exception:
        return {}
    out = {}
    for f in fields:
        key = f.get("key")
        if key and key in md:
            out[key] = md[key]
    return out

def serialize_booking(
    row: dict,
    *,
    slot_ids: Iterable[str],
    start_utc: Any,
    end_utc: Any,
    review: Optional[dict] = None,
    now: Optional[datetime] = None,
    include_client: bool = False,
    provider_name: str = "",
    provider_avatar_url: str = "",
    service_name: str = "",
    # Optional: `inventory` is in OVERRIDABLE_BLOCKS, so a caller that already
    # has the service row gets its override honoured. Callers that don't fall
    # back to the global block, which is right for every single-tenant
    # deployment and for any service that declares no override.
    service: Optional[dict] = None,
) -> dict:
    md = row.get("metadata") or {}
    review_out = None
    if review:
        review_out = {
            "rating": int(review["rating"]),
            "text": review.get("text") or "",
            "createdAtUtc": iso_utc(review.get("created_at") or review.get("createdAtUtc")),
        }
    out = {
        "id": row["id"],
        "reference": md.get("reference", ""),
        "userId": row.get("client_id") or md.get("user_id") or "",
        "providerId": md.get("provider_id", ""),
        "serviceId": md.get("service_id", ""),
        # Names are embedded so a bookings list needn't fetch each provider/
        # service separately (was an N+1 of heavy per-id calls from the client).
        # Additive + defaulted: endpoints that don't resolve them send "".
        "providerName": provider_name,
        # The counterparty's photo, embedded for the same reason the name is:
        # a bookings list must not fetch each provider by id to show a face.
        "providerAvatarUrl": provider_avatar_url,
        "serviceName": service_name,
        "resourceId": md.get("resource_id", ""),
        "slotIds": list(slot_ids),
        "startUtc": iso_utc(start_utc),
        "endUtc": iso_utc(end_utc),
        "status": effective_booking_status(row["status"], end_utc, now),
        "partySize": int(md.get("party_size", 1)),
        "priceMinorUnits": int(md.get("price_minor_units", 0)),
        # Same fallback chain as payment_state's currency, so one payload never
        # labels the total EUR beside a USD outstanding amount.
        "currency": md.get("currency")
        or effective_service_pricing(service).get("currency")
        or "EUR",
        "createdAtUtc": iso_utc(row.get("created_at")),
        "cancelledAtUtc": iso_utc(md.get("cancelled_at_utc")) if md.get("cancelled_at_utc") else None,
        "changeHistory": _change_history(md),
        "review": review_out,
        # None unless `inventory.returnRequired` — the overwhelming majority of
        # deployments loan nothing and must not grow a return surface.
        "loan": loan_state(md, end_utc, service, now),
        # What still blocks confirmation. Empty on every deployment that
        # declares no blocking prerequisite, which is almost all of them.
        "prerequisitesPending": list(md.get("prerequisites_pending") or []),
        "prerequisitesMet": list(md.get("prerequisites_met") or []),
        # What is owed and whether it is settled — derived from `payments.flow`,
        # never stored, so it cannot drift from the config after a pivot.
        "payment": payment_state(md, service, row.get("status")),
        # What the customer actually chose, where the config offers a choice.
        # All three are absent on a deployment that declares no composition, no
        # options and no subject, which is most of them.
        "partyBands": md.get("party_bands") or None,
        "options": list(md.get("options") or []),
        "subject": md.get("subject") or None,
        # The deployment's own `metaFields.bookings` values, echoed back so a
        # pivot's custom fields are readable and not just writable. Filtered to
        # the *declared* descriptors rather than dumping `metadata`: the same
        # jsonb column carries engine-owned keys (price, ids, prerequisite
        # state), and those already have their own serialized shapes above.
        # Empty dict on the majority of deployments, which declare none.
        "metadata": _declared_booking_meta(md),
    }
    if include_client:
        # Owner-only view: who booked. An additive field (never sent to clients).
        out["clientEmail"] = row.get("client_email") or ""
    return out


def serialize_conversation(
    row: dict,
    *,
    other_party: dict,
    unread_count: int = 0,
) -> dict:
    """A thread as the inbox lists it. `other_party` is the resolved
    {id, name, avatarUrl} of whoever the current user is talking to (the provider
    for a client; the customer for an owner) — resolved by the router, since it
    spans a cross-user lookup RLS can't do."""
    return {
        "id": row["id"],
        "providerId": row["provider_id"],
        "otherParty": {
            "id": other_party.get("id") or "",
            "name": other_party.get("name") or "",
            "avatarUrl": other_party.get("avatar_url"),
        },
        "lastMessagePreview": row.get("last_message_preview"),
        "lastMessageAtUtc": iso_utc(row.get("last_message_at")),
        "unreadCount": int(unread_count),
    }


def serialize_message(row: dict, *, me_id: str) -> dict:
    """A single message. `mine` is derived from the viewer so the UI can align
    bubbles left/right without knowing ids. A soft-deleted message keeps its
    envelope (timestamps/receipts) but its body is blanked — the client renders
    the "Message deleted" placeholder from `deletedAtUtc`."""
    deleted = row.get("deleted_at") is not None
    return {
        "id": row["id"],
        "conversationId": row["conversation_id"],
        "senderId": row["sender_id"],
        "body": "" if deleted else (row.get("body") or ""),
        "replyToId": row.get("reply_to_id"),
        "createdAtUtc": iso_utc(row.get("created_at")),
        "deliveredAtUtc": iso_utc(row.get("delivered_at")),
        "readAtUtc": iso_utc(row.get("read_at")),
        "deletedAtUtc": iso_utc(row.get("deleted_at")),
        "mine": row["sender_id"] == me_id,
    }


def serialize_user(
    *,
    id: str,
    email: Optional[str],
    metadata: Optional[dict] = None,
    followed_provider_ids: Iterable[str] = (),
) -> dict:
    """Assemble the frontend User from token/user_metadata + the follows table.
    Profile fields (displayName/avatar/timezone/verified) live in Supabase
    user_metadata; role is not part of the User shape (owner-gating is separate)."""
    md = metadata or {}
    return {
        "id": id,
        "displayName": md.get("display_name") or md.get("displayName") or (email or "").split("@")[0],
        "email": email or "",
        "avatarUrl": md.get("avatar_url") or md.get("avatarUrl") or "",
        "timezone": md.get("timezone") or "UTC",
        "verified": bool(md.get("verified", False)),
        "followedProviderIds": list(followed_provider_ids),
    }
