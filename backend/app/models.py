# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pydantic request envelopes for the neutral booking engine.

These type ONLY the domain-agnostic fields the engine understands (`name`,
`starts_at`, `client_email`, `capacity`, ...) plus a free-form
`metadata: dict`. Domain-specific data rides in `metadata` and is validated
separately by `app.meta` from `domain.config.json` at request time, so a
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


class RepeatReq(CamelModel):
    """The repeat leg of `POST /bookings`.

    `recurrence` was declared, validated and read by nothing: a config could
    state `patterns: ["weekly"], maxOccurrences: 12` and the engine had no way
    to make a second booking from it.

    `count` INCLUDES the first occurrence, so `count: 4` on a weekly pattern is
    the selected date plus three more. It is clamped to
    `recurrence.maxOccurrences` server-side, the client never decides the
    ceiling.
    """

    pattern: str
    count: int = 1


class QuoteReq(CamelModel):
    """POST /bookings/quote, price a selection WITHOUT committing it.

    The same envelope as `BookingCreateReq` minus the domain metadata, because
    the quote runs the identical resolve + price path the create does. The UI
    used to compute `priceMinorUnits * slots * party` itself, which is only the
    default `pricing` block's formula: a service billing per hour, per person,
    by tier, or with a fee/cap/deposit displayed one number and charged another.
    """

    service_id: str
    resource_id: str
    slot_ids: list[str]
    party_size: int = 1
    # The three v2 `booking` blocks that had no input path until now. All
    # optional: a deployment declaring none sends none and prices exactly as
    # before.
    #
    # party_bands  {bandKey: count} for `booking.party.composition`, priced as a
    #              weighted head count, and must add up to party_size.
    # options      {optionKey: true | "choiceKey"} for `booking.options`, paid
    #              add-ons, resolved to breakdown lines server-side so the client
    #              can never name its own price.
    # subject      the pet/vehicle/child the booking is about
    #              (`booking.subject.fields`), validated against the declared
    #              fields; a missing required one is a rejection.
    party_bands: dict[str, int] | None = None
    options: dict[str, object] | None = None
    subject: dict | None = None


class BookingCreateReq(CamelModel):
    """POST /bookings, the multi-slot, party-size booking envelope. Ownership
    (userId/email) is derived from the token, never the body."""

    service_id: str
    resource_id: str
    slot_ids: list[str]
    party_size: int = 1
    # The three v2 `booking` blocks that had no input path until now. All
    # optional: a deployment declaring none sends none and prices exactly as
    # before.
    #
    # party_bands  {bandKey: count} for `booking.party.composition`, priced as a
    #              weighted head count, and must add up to party_size.
    # options      {optionKey: true | "choiceKey"} for `booking.options`, paid
    #              add-ons, resolved to breakdown lines server-side so the client
    #              can never name its own price.
    # subject      the pet/vehicle/child the booking is about
    #              (`booking.subject.fields`), validated against the declared
    #              fields; a missing required one is a rejection.
    party_bands: dict[str, int] | None = None
    options: dict[str, object] | None = None
    subject: dict | None = None
    # Optional repeat. Absent (the default) books exactly the selection, which
    # is what every non-recurring deployment does.
    repeat: RepeatReq | None = None
    # Domain-specific fields, validated at request time from
    # `domain.config.json` metaFields.{entity}. Only `resources`/`slots` ever
    # accepted one, so a `metaFields.providers|services|bookings` descriptor (the
    # a config can declare one) had no input path and validated
    # nothing. Merged UNDER the engine's own keys, which always win.
    metadata: dict | None = None


class RescheduleReq(CamelModel):
    """POST /bookings/{id}/reschedule, the new (possibly multi-) slot set."""

    new_slot_ids: list[str]


class ReviewReq(CamelModel):
    rating: int
    text: str = ""


class ClientReviewReq(CamelModel):
    """POST /bookings/{id}/client-review, an owner rating the customer after a
    completed booking (feeds the customer's reputation)."""

    rating: int
    text: str = ""


class MessageCreateReq(CamelModel):
    """POST /conversations/{id}/messages, a single message. `sender_id` and the
    timestamps are stamped server-side from the token, never the body."""

    body: str
    reply_to_id: str | None = None


class ConversationCreateReq(CamelModel):
    """POST /conversations, find-or-create a thread. The client path passes only
    `provider_id` (the caller is the customer). The owner path additionally
    passes `client_id` (the customer to reach out to); the router verifies the
    caller owns the provider before creating an owner-side thread."""

    provider_id: str
    client_id: str | None = None


class UserPatch(CamelModel):
    """PATCH /me, a partial User. Only these keys are honored; role/verified
    are not self-editable."""

    display_name: str | None = None
    email: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None


class ProviderCreate(CamelModel):
    """POST /providers (owner), the presentational fields ride in metadata; the
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
    # Domain-specific fields, validated at request time from
    # `domain.config.json` metaFields.{entity}. Only `resources`/`slots` ever
    # accepted one, so a `metaFields.providers|services|bookings` descriptor (the
    # a config can declare one) had no input path and validated
    # nothing. Merged UNDER the engine's own keys, which always win.
    metadata: dict | None = None


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
    # Domain-specific fields, validated at request time from
    # `domain.config.json` metaFields.{entity}. Only `resources`/`slots` ever
    # accepted one, so a `metaFields.providers|services|bookings` descriptor (the
    # a config can declare one) had no input path and validated
    # nothing. Merged UNDER the engine's own keys, which always win.
    metadata: dict | None = None


class ServiceCreate(CamelModel):
    """POST /services (owner), the per-service rules are real columns."""

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
    #
    # None (not True) so an unset value stays UNSET. Defaulting to True stamped
    # every created service with an explicit metadata key, which `effective_auto_approve`
    # checks first, making both a `timing.confirmation` override and a
    # deployment-wide `request_approve` unreachable through the API.
    auto_approve: bool | None = None
    # Per-service config overrides, keyed by block name (`pricing`, `timing`,
    # `inventory`, ...). This is how one business on a marketplace prices or
    # gates differently from another without touching domain.config.json.
    # Validated against the same schema as the global file; a bad block is a 422.
    config: dict | None = None
    # Domain-specific fields, validated at request time from
    # `domain.config.json` metaFields.{entity}. Only `resources`/`slots` ever
    # accepted one, so a `metaFields.providers|services|bookings` descriptor (the
    # a config can declare one) had no input path and validated
    # nothing. Merged UNDER the engine's own keys, which always win.
    metadata: dict | None = None


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
    config: dict | None = None
    # Domain-specific fields, validated at request time from
    # `domain.config.json` metaFields.{entity}. Only `resources`/`slots` ever
    # accepted one, so a `metaFields.providers|services|bookings` descriptor (the
    # a config can declare one) had no input path and validated
    # nothing. Merged UNDER the engine's own keys, which always win.
    metadata: dict | None = None


# `CamelModel`, not `BaseModel`. These four were the only owner-side write
# models still snake_case-only, so the frontend seam, which sends camelCase
# everywhere, could create a provider and a service but not the resources and
# slots they need. `SlotCreate` 422'd on `resourceId`/`startsAt`, and
# `ResourceCreate` silently ignored the unknown keys, which is worse: a
# camelCase resource was created with the DEFAULT capacity rather than rejected.
# `populate_by_name` keeps existing snake_case callers (seed, tests, curl) working.
class ResourceCreate(CamelModel):
    name: str
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class ResourceUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    metadata: dict | None = None


class SlotCreate(CamelModel):
    resource_id: str
    starts_at: str
    # Derived from rules.slotDurationMinutes when omitted (see routers/slots.py).
    ends_at: str | None = None
    # Defaults to rules.maxBookingsPerSlot when omitted.
    capacity: int | None = None
    metadata: dict = Field(default_factory=dict)


class SlotUpdate(CamelModel):
    starts_at: str | None = None
    ends_at: str | None = None
    capacity: int | None = None
    metadata: dict | None = None
