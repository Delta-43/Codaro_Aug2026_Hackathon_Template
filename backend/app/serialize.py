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

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.rules import effective_auto_approve, effective_service_pricing

# --- time helpers ----------------------------------------------------------


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
    return now or datetime.now(timezone.utc)


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
    return {
        "id": row["id"],
        "providerId": row["provider_id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "imageUrl": md.get("image_url"),
        "bookingModel": row["booking_model"],
        "slotDurationMinutes": row["slot_duration_minutes"],
        "minSlotsPerBooking": row["min_slots_per_booking"],
        "maxSlotsPerBooking": row["max_slots_per_booking"],
        # Resolved, not the raw column: a service with a `metadata.pricing`
        # override is charged through `effective_service_pricing`, so reporting
        # the column here advertised one price and billed another.
        "priceMinorUnits": pricing["rate"]["amountMinorUnits"],
        "currency": pricing["currency"],
        "cancellationCutoffHours": row["cancellation_cutoff_hours"],
        # Owner-controlled: when False, new bookings for this service land as
        # 'pending' and wait in the Requests tab; when True (default) they
        # confirm immediately. Rides in metadata (services columns are fixed).
        #
        # Resolved through the SAME helper the booking path uses. Reading
        # `metadata.auto_approve` directly meant a service whose confirmation came
        # from a `timing.confirmation` override reported `autoApprove: true` on the
        # wire while actually creating pending bookings.
        "autoApprove": effective_auto_approve(row),
        "resourceIds": list(resource_ids),
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
        "attributes": md.get("attributes") or [],
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
    service_name: str = "",
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
        "serviceName": service_name,
        "resourceId": md.get("resource_id", ""),
        "slotIds": list(slot_ids),
        "startUtc": iso_utc(start_utc),
        "endUtc": iso_utc(end_utc),
        "status": effective_booking_status(row["status"], end_utc, now),
        "partySize": int(md.get("party_size", 1)),
        "priceMinorUnits": int(md.get("price_minor_units", 0)),
        "currency": md.get("currency", "EUR"),
        "createdAtUtc": iso_utc(row.get("created_at")),
        "cancelledAtUtc": iso_utc(md.get("cancelled_at_utc")) if md.get("cancelled_at_utc") else None,
        "changeHistory": _change_history(md),
        "review": review_out,
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
