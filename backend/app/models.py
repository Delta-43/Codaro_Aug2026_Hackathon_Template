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

from pydantic import BaseModel, Field


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
