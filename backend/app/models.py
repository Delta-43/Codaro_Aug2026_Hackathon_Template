"""Pydantic request envelopes for the neutral booking engine.

These type ONLY the domain-agnostic fields the engine understands (`name`,
`starts_at`, `client_email`, `capacity`, ...) plus a free-form
`metadata: dict`. Domain-specific data rides in `metadata` and is validated
separately by `app.meta` from `domain.config.json` at request time — so a
pivot never needs a model change here.

Routers build insert rows explicitly from these fields; a raw ``**payload``
spread is deliberately avoided (arbitrary-key injection / KeyError 500s).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Request models the *new frontend* sends in camelCase. `populate_by_name`
    keeps snake_case acceptable too, so tests and curl can use either."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class BookingCreateReq(CamelModel):
    """POST /bookings — the multi-slot, party-size booking envelope. Ownership
    (userId/email) is derived from the token, never the body."""

    service_id: str
    resource_id: str
    slot_ids: list[str]
    party_size: int = 1


class RescheduleReq(CamelModel):
    """POST /bookings/{id}/reschedule — the new (possibly multi-) slot set."""

    new_slot_ids: list[str]


class ReviewReq(CamelModel):
    rating: int
    text: str = ""


class ClientReviewReq(CamelModel):
    """POST /bookings/{id}/client-review — an owner rating the customer after a
    completed booking (feeds the customer's reputation)."""

    rating: int
    text: str = ""


class MessageCreateReq(CamelModel):
    """POST /conversations/{id}/messages — a single message. `sender_id` and the
    timestamps are stamped server-side from the token, never the body."""

    body: str
    reply_to_id: str | None = None


class ConversationCreateReq(CamelModel):
    """POST /conversations — find-or-create a thread. The client path passes only
    `provider_id` (the caller is the customer). The owner path additionally
    passes `client_id` (the customer to reach out to); the router verifies the
    caller owns the provider before creating an owner-side thread."""

    provider_id: str
    client_id: str | None = None


class UserPatch(CamelModel):
    """PATCH /me — a partial User. Only these keys are honored; role/verified
    are not self-editable."""

    display_name: str | None = None
    email: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None


class ProviderCreate(CamelModel):
    """POST /providers (owner) — the presentational fields ride in metadata; the
    router stamps owner_id from the token."""

    name: str
    public_code: str | None = None
    category_id: str | None = None
    tagline: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    location: dict | None = None  # {city, country, lat, lng}
    links: list | None = None


class ProviderUpdate(CamelModel):
    name: str | None = None
    public_code: str | None = None
    category_id: str | None = None
    tagline: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    location: dict | None = None
    links: list | None = None


class ServiceCreate(CamelModel):
    """POST /services (owner) — the per-service rules are real columns."""

    provider_id: str
    name: str
    description: str | None = None
    booking_model: str = "one_to_one"
    slot_duration_minutes: int = 30
    min_slots_per_booking: int = 1
    max_slots_per_booking: int = 1
    price_minor_units: int = 0
    currency: str = "EUR"
    cancellation_cutoff_hours: int = 24
    image_url: str | None = None
    # Non-column fields (ride in services.metadata): auto_approve gates whether
    # new bookings confirm immediately or land as pending requests.
    auto_approve: bool = True


class ServiceUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    booking_model: str | None = None
    slot_duration_minutes: int | None = None
    min_slots_per_booking: int | None = None
    max_slots_per_booking: int | None = None
    price_minor_units: int | None = None
    currency: str | None = None
    cancellation_cutoff_hours: int | None = None
    image_url: str | None = None
    auto_approve: bool | None = None


class ResourceCreate(BaseModel):
    name: str
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class ResourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    metadata: dict | None = None


class SlotCreate(BaseModel):
    resource_id: str
    starts_at: str
    # Derived from rules.slotDurationMinutes when omitted (see routers/slots.py).
    ends_at: str | None = None
    # Defaults to rules.maxBookingsPerSlot when omitted.
    capacity: int | None = None
    metadata: dict = Field(default_factory=dict)


class SlotUpdate(BaseModel):
    starts_at: str | None = None
    ends_at: str | None = None
    capacity: int | None = None
    metadata: dict | None = None
