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
    client_email: str
    client_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class RescheduleRequest(BaseModel):
    new_slot_id: str


class ActorBody(BaseModel):
    """Optional owner/client flag on cancel/confirm — never credentials.

    Absent (or ``actor="client"``) ⇒ client behaviour, so the existing
    frontend calls keep working. ``actor="owner"`` overrides the
    cancellation window and is recorded in ``history``.
    """

    actor: str | None = None
