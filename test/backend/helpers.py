"""Row builders shared by the backend integration tests.

They insert directly into the `FakeSupabase` store (bypassing the API), matching
the metadata-key conventions `app.serialize` / `seed.py` use, so a test can set
up a provider → service → resource → slot graph in a couple of lines and then hit
the real endpoints.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fakes import FakeSupabase

DEFAULT_USER_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_OWNER_ID = "22222222-2222-2222-2222-222222222222"


def iso_in(hours: float = 0, minutes: float = 0) -> str:
    """UTC timestamp `hours`/`minutes` from now, PostgREST-style (+00:00)."""
    moment = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)
    return moment.isoformat()


def make_provider(
    db: FakeSupabase,
    name: str = "Provider One",
    *,
    public_code: str | None = None,
    category_id: str | None = None,
    owner_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return db.insert_row(
        "providers",
        name=name,
        public_code=public_code,
        category_id=category_id,
        owner_id=owner_id,
        metadata=metadata or {},
    )


def make_service(
    db: FakeSupabase,
    provider_id: str,
    name: str = "Service One",
    *,
    booking_model: str = "one_to_one",
    slot_duration_minutes: int = 30,
    min_slots_per_booking: int = 1,
    max_slots_per_booking: int = 1,
    price_minor_units: int = 0,
    currency: str = "EUR",
    cancellation_cutoff_hours: int = 24,
    **extra,
) -> dict:
    return db.insert_row(
        "services",
        provider_id=provider_id,
        name=name,
        booking_model=booking_model,
        slot_duration_minutes=slot_duration_minutes,
        min_slots_per_booking=min_slots_per_booking,
        max_slots_per_booking=max_slots_per_booking,
        price_minor_units=price_minor_units,
        currency=currency,
        cancellation_cutoff_hours=cancellation_cutoff_hours,
        **extra,
    )


def make_resource(
    db: FakeSupabase,
    name: str = "Widget 1",
    *,
    service_id: str | None = None,
    capacity: int = 1,
    active: bool = True,
    owner_id: str | None = None,
    attributes: list | None = None,
    metadata: dict | None = None,
    **extra,
) -> dict:
    md = {
        "service_id": service_id,
        "capacity": capacity,
        "active": active,
        "attributes": attributes or [],
    }
    if owner_id is not None:
        md["owner_id"] = owner_id
    if metadata:
        md.update(metadata)
    return db.insert_row("resources", name=name, metadata=md, **extra)


def make_slot(
    db: FakeSupabase,
    resource_id: str | None = None,
    *,
    service_id: str | None = None,
    hours_ahead: float = 48,
    capacity: int = 1,
    duration_minutes: int = 30,
    starts_at: str | None = None,
    **extra,
) -> dict:
    if resource_id is None:
        resource_id = make_resource(db)["id"]
    start = starts_at if starts_at is not None else iso_in(hours=hours_ahead)
    ends_at = extra.pop(
        "ends_at",
        (datetime.fromisoformat(start) + timedelta(minutes=duration_minutes)).isoformat(),
    )
    metadata = extra.pop("metadata", {})
    if service_id is not None:
        metadata = {**metadata, "service_id": service_id}
    return db.insert_row(
        "slots",
        resource_id=resource_id,
        starts_at=start,
        ends_at=ends_at,
        capacity=capacity,
        metadata=metadata,
        **extra,
    )


def make_booking(
    db: FakeSupabase,
    *,
    slots: list[dict],
    service: dict | None = None,
    resource_id: str | None = None,
    user_id: str = DEFAULT_USER_ID,
    client_email: str = "guest@example.com",
    party_size: int = 1,
    status: str = "confirmed",
    reference: str = "BK-TEST01",
    history: list | None = None,
    metadata: dict | None = None,
) -> dict:
    """Insert a booking plus its `booking_slots` join rows (so occupancy counts
    it). `slots` is the ordered list of slot rows the booking spans."""
    slot_ids = [s["id"] for s in slots]
    resource_id = resource_id or slots[0]["resource_id"]
    md = {
        "party_size": party_size,
        "reference": reference,
        "price_minor_units": (service or {}).get("price_minor_units", 0) * len(slots) * party_size,
        "currency": (service or {}).get("currency", "EUR"),
        "provider_id": (service or {}).get("provider_id", ""),
        "service_id": (service or {}).get("id", ""),
        "resource_id": resource_id,
        "user_id": user_id,
        "slot_ids": slot_ids,
        "change_history": [],
    }
    if metadata:
        md.update(metadata)
    booking = db.insert_row(
        "bookings",
        slot_id=slot_ids[0],
        client_email=client_email,
        client_id=user_id,
        status=status,
        history=history if history is not None else [{"status": status, "at": iso_in()}],
        metadata=md,
    )
    for sid in slot_ids:
        db.insert_row("booking_slots", booking_id=booking["id"], slot_id=sid)
    return booking


def make_client_review(
    db: FakeSupabase,
    booking: dict,
    *,
    rating: int = 5,
    text: str = "",
    provider_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    """Insert a `client_reviews` row (a business rating a customer after a
    completed booking). Defaults resolve the client/provider from the booking's
    stored ids so a caller only needs the booking + a rating."""
    md = booking.get("metadata") or {}
    return db.insert_row(
        "client_reviews",
        booking_id=booking["id"],
        client_id=client_id or booking.get("client_id") or md.get("user_id"),
        provider_id=provider_id or md.get("provider_id"),
        rating=rating,
        text=text,
    )


def make_entitlement(
    db: FakeSupabase,
    *,
    user_id: str = DEFAULT_USER_ID,
    plan_key: str = "ten-pass",
    credits_total: int | None = None,
    credits_used: int = 0,
    status: str = "active",
    **extra,
) -> dict:
    """Insert an `entitlements` row (a plan a customer holds). The plan itself
    lives in config (`entitlements.plans[]`) — declare a matching `plan_key`
    there via `domain_config` or the row resolves to nothing."""
    return db.insert_row(
        "entitlements",
        user_id=user_id,
        plan_key=plan_key,
        credits_total=credits_total,
        credits_used=credits_used,
        status=status,
        **extra,
    )


def make_catalog(
    db: FakeSupabase,
    *,
    owner_id: str = DEFAULT_OWNER_ID,
    booking_model: str = "one_to_one",
    capacity: int = 1,
    slot_hours_ahead: float = 48,
    slot_capacity: int | None = None,
    **service_cols,
) -> dict:
    """One provider + service + resource + a single future slot, wired together.
    Returns {provider, service, resource, slot}."""
    provider = make_provider(db, owner_id=owner_id)
    service = make_service(db, provider["id"], booking_model=booking_model, **service_cols)
    resource = make_resource(
        db, service_id=service["id"], capacity=capacity, owner_id=owner_id
    )
    slot = make_slot(
        db,
        resource["id"],
        service_id=service["id"],
        hours_ahead=slot_hours_ahead,
        capacity=slot_capacity if slot_capacity is not None else capacity,
        duration_minutes=service["slot_duration_minutes"],
    )
    return {"provider": provider, "service": service, "resource": resource, "slot": slot}

