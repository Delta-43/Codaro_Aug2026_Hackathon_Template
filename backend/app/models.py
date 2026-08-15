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


class UserPatch(CamelModel):
    """PATCH /me — a partial User. Only these keys are honored; role/verified
    are not self-editable."""

    display_name: str | None = None
    email: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None


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


class BookingCreate(BaseModel):
    slot_id: str
    # Booking ownership is derived from the verified auth token, not trusted
    # from the body (see backend/CLAUDE.md "Auth"). These fields are accepted
    # for backward-compatibility but ignored — the router overwrites them with
    # the token's email / user id.
    client_email: str | None = None
    client_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class RescheduleRequest(BaseModel):
    new_slot_id: str
