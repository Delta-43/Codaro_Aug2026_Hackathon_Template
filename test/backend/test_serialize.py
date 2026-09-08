# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pure unit tests for `app.serialize` — the row → camelCase wire mappers.

These are offline and config-independent: none of the serializers touch
`get_config()` or the database, so they run without any fixture. They pin the
exact key set the frontend's `src/types/domain.ts` expects for each entity, plus
the three derived helpers (`derive_slot_status`, `effective_booking_status`,
`iso_utc`).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import serialize as S
from app.rules import capability, effective_auto_approve

# A fixed "now" so the time-dependent ladders are deterministic.
NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
PAST = "2026-01-01T00:00:00+00:00"
FUTURE = "2027-01-01T00:00:00+00:00"


# --- iso_utc ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-02T03:04:05+00:00", "2026-01-02T03:04:05.000Z"),
        ("2026-01-02T03:04:05Z", "2026-01-02T03:04:05.000Z"),
        ("2026-01-02T03:04:05.123456+00:00", "2026-01-02T03:04:05.123Z"),  # µs -> ms
        ("2026-01-02T03:04:05", "2026-01-02T03:04:05.000Z"),  # naive -> UTC
        ("2026-01-02T03:04:05+02:00", "2026-01-02T01:04:05.000Z"),  # offset normalised
    ],
)
def test_iso_utc_formats_with_trailing_z_and_millis(value, expected):
    assert S.iso_utc(value) == expected


def test_iso_utc_accepts_a_datetime():
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert S.iso_utc(dt) == "2026-01-02T03:04:05.000Z"


def test_iso_utc_none_is_none():
    assert S.iso_utc(None) is None


def test_iso_utc_always_ends_in_z():
    assert S.iso_utc("2026-01-02T03:04:05+05:30").endswith("Z")


# --- derive_slot_status ----------------------------------------------------


def test_slot_status_past_beats_everything():
    # Even a blocked/full slot in the past reads as "past".
    assert S.derive_slot_status(PAST, capacity=0, booked_count=0, now=NOW) == "past"


def test_slot_status_blocked_when_capacity_zero():
    assert S.derive_slot_status(FUTURE, capacity=0, booked_count=0, now=NOW) == "blocked"


def test_slot_status_full_when_booked_meets_capacity():
    assert S.derive_slot_status(FUTURE, capacity=2, booked_count=2, now=NOW) == "full"


def test_slot_status_partial_when_some_booked():
    assert S.derive_slot_status(FUTURE, capacity=3, booked_count=1, now=NOW) == "partially_booked"


def test_slot_status_available_when_empty():
    assert S.derive_slot_status(FUTURE, capacity=3, booked_count=0, now=NOW) == "available"


def test_slot_status_ladder_constants():
    assert (S.SLOT_PAST, S.SLOT_BLOCKED, S.SLOT_FULL, S.SLOT_PARTIAL, S.SLOT_AVAILABLE) == (
        "past",
        "blocked",
        "full",
        "partially_booked",
        "available",
    )


# --- effective_booking_status ----------------------------------------------


def test_confirmed_in_the_past_reads_as_completed():
    assert S.effective_booking_status("confirmed", PAST, now=NOW) == "completed"


def test_confirmed_in_the_future_stays_confirmed():
    assert S.effective_booking_status("confirmed", FUTURE, now=NOW) == "confirmed"


def test_confirmed_with_no_end_stays_confirmed():
    assert S.effective_booking_status("confirmed", None, now=NOW) == "confirmed"


def test_cancelled_stays_cancelled_even_in_the_past():
    assert S.effective_booking_status("cancelled", PAST, now=NOW) == "cancelled"


def test_rescheduled_is_treated_as_confirmed():
    assert S.effective_booking_status("rescheduled", FUTURE, now=NOW) == "confirmed"


def test_pending_passes_through_even_in_the_future():
    assert S.effective_booking_status("pending", FUTURE, now=NOW) == "pending"


def test_pending_past_is_not_auto_completed():
    # A pending request whose slot elapsed is still 'pending' (the owner acts on
    # it) — it is NOT silently completed by elapsed time.
    assert S.effective_booking_status("pending", PAST, now=NOW) == "pending"


def test_rejected_passes_through_in_past_and_future():
    assert S.effective_booking_status("rejected", FUTURE, now=NOW) == "rejected"
    assert S.effective_booking_status("rejected", PAST, now=NOW) == "rejected"


# --- serialize_provider ----------------------------------------------------

PROVIDER_KEYS = {
    "id",
    "name",
    "avatarUrl",
    "coverUrl",
    "tagline",
    "bio",
    "categoryId",
    "location",
    "rating",
    "reviewCount",
    "priceFromMinorUnits",
    "currency",
    "links",
    "publicCode",
    "serviceIds",
}


def _provider_row():
    return {
        "id": "prov-1",
        "name": "Vistula Auto",
        "category_id": "economy",
        "public_code": "VISTULA-4471",
        "metadata": {
            "avatar_url": "http://img/a.png",
            "cover_url": "http://img/c.png",
            "tagline": "City rentals",
            "bio": "Family-run desk.",
            "location": {"city": "Warsaw", "country": "Poland", "lat": 52.2, "lng": 21.0},
            "links": [{"label": "Website", "url": "http://x"}],
            "rating": 4.7,
            "review_count": 100,
        },
    }


def test_provider_key_set():
    out = S.serialize_provider(_provider_row(), service_ids=["s1", "s2"])
    assert set(out) == PROVIDER_KEYS
    assert set(out["location"]) == {"city", "country", "lat", "lng"}


def test_provider_serviceids_and_public_code():
    out = S.serialize_provider(_provider_row(), service_ids=["s1"])
    assert out["serviceIds"] == ["s1"]
    assert out["publicCode"] == "VISTULA-4471"
    assert out["categoryId"] == "economy"


def test_provider_rating_pools_seed_baseline_with_real_reviews():
    # seed: 4.7 over 100; add two real 5.0 reviews -> pooled over 102.
    out = S.serialize_provider(_provider_row(), review_sum=10.0, review_count=2)
    assert out["reviewCount"] == 102
    assert out["rating"] == round((4.7 * 100 + 10.0) / 102, 1)


def test_provider_rating_zero_when_no_reviews_at_all():
    row = _provider_row()
    row["metadata"]["rating"] = 0
    row["metadata"]["review_count"] = 0
    out = S.serialize_provider(row)
    assert out["rating"] == 0.0
    assert out["reviewCount"] == 0


def test_provider_defaults_when_metadata_sparse():
    out = S.serialize_provider({"id": "p", "name": "Bare"})
    assert out["avatarUrl"] == ""
    assert out["location"] == {"city": "", "country": "", "lat": 0, "lng": 0}
    assert out["links"] == []
    assert out["coverUrl"] is None


def test_provider_price_from_defaults_to_none_and_empty_currency():
    # No price aggregate passed (provider has no priced service) → null price,
    # empty currency.
    out = S.serialize_provider(_provider_row(), service_ids=["s1"])
    assert out["priceFromMinorUnits"] is None
    assert out["currency"] == ""


def test_provider_price_from_carries_min_price_and_currency():
    out = S.serialize_provider(
        _provider_row(), service_ids=["s1"], price_from=4500, currency="PLN"
    )
    assert out["priceFromMinorUnits"] == 4500
    assert out["currency"] == "PLN"


def test_provider_price_from_zero_currency_still_defaults_empty():
    # A falsy currency ("") stays "", never None — the wire contract is str.
    out = S.serialize_provider(_provider_row(), price_from=0, currency="")
    assert out["priceFromMinorUnits"] == 0
    assert out["currency"] == ""


# --- discovery: price_from_by_provider + build_provider --------------------


class _Table:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    # `db.fetch_all` orders + ranges before executing; the stub holds one small
    # fixed page, so both are no-ops (a single short page ends the paging loop).
    def order(self, *_a, **_k):
        return self

    def range(self, *_a, **_k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rows})()


class _DB:
    """A services table standing in for the whole-table scan the discovery
    helpers do. Hoisted to module level so the price tests below can share it."""

    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _Table(self._rows)


def test_discovery_price_from_picks_cheapest_service_currency():
    from app import discovery as D

    rows = [
        {"provider_id": "prov-1", "price_minor_units": 9000, "currency": "PLN"},
        {"provider_id": "prov-1", "price_minor_units": 4500, "currency": "USD"},
        {"provider_id": "prov-1", "price_minor_units": 7000, "currency": "PLN"},
        {"provider_id": "prov-2", "price_minor_units": 1200, "currency": "EUR"},
    ]
    by = D.price_from_by_provider(_DB(rows))
    # cheapest of prov-1 wins, carrying that service's currency.
    assert by["prov-1"] == (4500, "USD")
    assert by["prov-2"] == (1200, "EUR")

    # build_provider threads it onto the serialized Provider...
    p1 = D.build_provider(
        {"id": "prov-1", "name": "P1"},
        svc_by_prov={"prov-1": ["s1", "s2"]},
        sums={},
        counts={},
        price_by_prov=by,
    )
    assert p1["priceFromMinorUnits"] == 4500
    assert p1["currency"] == "USD"

    # ...and a provider absent from the map falls back to null / "".
    p3 = D.build_provider(
        {"id": "prov-3", "name": "P3"},
        svc_by_prov={},
        sums={},
        counts={},
        price_by_prov=by,
    )
    assert p3["priceFromMinorUnits"] is None
    assert p3["currency"] == ""


def test_discovery_price_from_resolves_a_metadata_pricing_override():
    """A service priced ONLY through `metadata.pricing` must drive the provider's
    `priceFromMinorUnits`. Reading `price_minor_units` reported 0 for it while
    `serialize_service` and `quote()` used the real amount — the provider card
    and the price facet were computed from a number nothing else in the engine
    used. This is also the only coverage of `_resolved_price`'s override branch;
    every other price test builds rows from plain columns."""
    from app import discovery as D

    rows = [
        {"provider_id": "prov-1", "price_minor_units": 9000, "currency": "PLN", "metadata": {}},
        # Column says 0; the override is what the engine actually charges.
        {
            "provider_id": "prov-1",
            "price_minor_units": 0,
            "currency": "EUR",
            "metadata": {"pricing": {"rate": {"per": "slot", "amountMinorUnits": 3300}}},
        },
    ]
    by = D.price_from_by_provider(_DB(rows))
    assert by["prov-1"] == (3300, "EUR")


def test_discovery_price_fast_path_agrees_with_the_full_resolver():
    """`_resolved_price` skips `effective_service_pricing` for any row with no
    `metadata.pricing` block. That shortcut is only equivalent because
    `price_minor_units`/`currency` are NOT NULL DEFAULT and the resolver folds
    them over the global block unconditionally — facts in schema.sql and
    rules.py that nothing else pins. Make the columns nullable, or reorder the
    fold-in, and discovery silently starts reporting a different price from
    `quote()`; this is what fails when that happens."""
    from app import discovery as D
    from app.rules import effective_service_pricing

    def resolved(row):
        pricing = effective_service_pricing(row)
        return (
            int((pricing.get("rate") or {}).get("amountMinorUnits") or 0),
            pricing.get("currency") or "",
        )

    fallback = D._global_price_fallback()
    rows = [
        {"price_minor_units": 1000, "currency": "EUR", "metadata": {}},
        {"price_minor_units": 0, "currency": "EUR", "metadata": {}},
        {"price_minor_units": 2500, "currency": "JPY", "metadata": {}},
        {"price_minor_units": 1000, "currency": "", "metadata": {}},
        {"price_minor_units": None, "currency": "EUR", "metadata": {}},
        {"price_minor_units": 1000, "currency": "EUR", "metadata": {"image_url": "x"}},
        # override branch, including shapes `surviving_overrides` rejects
        {
            "price_minor_units": 1000,
            "currency": "EUR",
            "metadata": {"pricing": {"rate": {"per": "slot", "amountMinorUnits": 7777}}},
        },
        {"price_minor_units": 1000, "currency": "EUR", "metadata": {"pricing": {"currency": "KWD"}}},
        {"price_minor_units": 1000, "currency": "EUR", "metadata": {"pricing": "not-a-dict"}},
        {"price_minor_units": 1000, "currency": "EUR", "metadata": {"pricing": {"rate": 5}}},
    ]
    for row in rows:
        assert D._resolved_price(row, fallback) == resolved(row), row


# --- serialize_service -----------------------------------------------------

SERVICE_KEYS = {
    "id",
    "providerId",
    "name",
    "description",
    "imageUrl",
    "bookingModel",
    "slotDurationMinutes",
    "minSlotsPerBooking",
    "maxSlotsPerBooking",
    "priceMinorUnits",
    "currency",
    "cancellationCutoffHours",
    "autoApprove",
    "capabilities",
    # The shape of the offer, so the UI can describe it before a selection
    # exists — `priceMinorUnits` alone is only the base rate.
    "pricingModel",
    "rateUnit",
    # `pricing.chargePerPerson` — whether the rate is multiplied by heads. The
    # client previews a total with the engine's own formula; without it a
    # shared court/table read as per-head.
    "chargePerPerson",
    "paymentFlow",
    "billingCycle",
    "prerequisites",
    "recurrence",
    "waitlist",
    "resourceIds",
    # The v2 offer-shape blocks. Every one was declared in the config, resolved
    # per service, and served to nobody — so the client could not render (let
    # alone collect) a party band, an add-on, a subject, a course or a payment
    # schedule.
    "unitKind",
    # `booking.granularity` — `none` means the customer picks NO date at all
    # (the business assigns one afterwards), so the client needs this to choose
    # between a date picker and a "we will contact you" form.
    "granularity",
    # `timing.approvalWindowHours` — DISPLAY ONLY: how fast the business says it
    # answers a request. Nothing expires a stale request server-side (pinned in
    # test_config_schema.py's surfaced-but-unenforced inventory).
    "approvalWindowHours",
    "party",
    "subject",
    "options",
    "sequence",
    "paymentSchedule",
    "locationModes",
    "locationDefault",
}


def _service_row():
    return {
        "id": "svc-1",
        "provider_id": "prov-1",
        "name": "Compact rental",
        "description": "A small car.",
        "booking_model": "unit_selection",
        "slot_duration_minutes": 1440,
        "min_slots_per_booking": 1,
        "max_slots_per_booking": 7,
        "price_minor_units": 4500,
        "currency": "PLN",
        "cancellation_cutoff_hours": 48,
        "metadata": {"image_url": "http://img/s.png"},
    }


def test_service_key_set_and_passthrough():
    out = S.serialize_service(_service_row(), resource_ids=["r1", "r2"])
    assert set(out) == SERVICE_KEYS
    assert out["providerId"] == "prov-1"
    assert out["bookingModel"] == "unit_selection"
    assert out["slotDurationMinutes"] == 1440
    assert out["maxSlotsPerBooking"] == 7
    assert out["cancellationCutoffHours"] == 48
    assert out["currency"] == "PLN"
    assert out["resourceIds"] == ["r1", "r2"]
    assert out["imageUrl"] == "http://img/s.png"


def test_service_missing_description_becomes_empty_string():
    row = _service_row()
    row["description"] = None
    assert S.serialize_service(row)["description"] == ""


def test_service_auto_approve_defaults_true_when_absent():
    row = _service_row()
    row["metadata"] = {}  # no auto_approve key
    assert S.serialize_service(row)["autoApprove"] is True


def test_service_auto_approve_reflects_metadata_false():
    row = _service_row()
    row["metadata"] = {"auto_approve": False}
    assert S.serialize_service(row)["autoApprove"] is False


def test_service_auto_approve_metadata_true():
    row = _service_row()
    row["metadata"] = {"auto_approve": True}
    assert S.serialize_service(row)["autoApprove"] is True


def test_service_auto_approve_follows_a_per_service_confirmation_override():
    """`serialize_service` delegates to `rules.effective_auto_approve` (it used to
    read `metadata.auto_approve` directly), so the wire field cannot disagree with
    the booking path for a service gated by `timing.confirmation` alone."""
    row = _service_row()
    row["metadata"] = {"timing": {"confirmation": "request_approve"}}
    assert S.serialize_service(row)["autoApprove"] is False
    assert effective_auto_approve(row) is False


def test_service_auto_approve_key_still_wins_over_a_confirmation_override():
    row = _service_row()
    row["metadata"] = {"timing": {"confirmation": "request_approve"}, "auto_approve": True}
    assert S.serialize_service(row)["autoApprove"] is True


def test_service_capabilities_are_resolved_per_service_not_global():
    """The routers gate `capability(name, service)`, which resolves a service's
    own `metadata.capabilities` over the global block. Serving only the global
    block left the client unable to see a per-service override, so it rendered a
    review control the API then refused with a 404."""
    row = _service_row()
    row["metadata"] = {"capabilities": {"reviews": False}}
    out = S.serialize_service(row)
    assert out["capabilities"]["reviews"] is False
    # and it agrees with the gate the router actually applies
    assert capability("reviews", row) is False


def test_service_capabilities_fall_back_to_the_global_block():
    row = _service_row()
    row["metadata"] = {}
    assert S.serialize_service(row)["capabilities"]["reviews"] is True
    assert capability("reviews", row) is True


def test_service_auto_approve_follows_the_global_confirmation_mode(domain_config):
    """No per-service block at all: the deployment-wide `timing.confirmation`
    decides what the wire reports."""
    domain_config(timing={"confirmation": "request_approve"})
    row = _service_row()
    row["metadata"] = {}
    assert S.serialize_service(row)["autoApprove"] is False
    domain_config(timing={"confirmation": "instant"})
    assert S.serialize_service(row)["autoApprove"] is True


# --- the additive v2 offer-shape keys --------------------------------------
#
# `granularity` / `approvalWindowHours` / `chargePerPerson` were declared,
# resolved per service and served to nobody. Each is a seam the client cannot
# render the offer without, so each is pinned at BOTH ends: the value the config
# resolves to, and the value that lands on the wire.


def test_service_granularity_defaults_to_minute():
    """The date-picker default. Absent config -> `minute`, never None: the
    client branches on this value and has no sensible fallback of its own."""
    row = _service_row()
    row["metadata"] = {}
    assert S.serialize_service(row)["granularity"] == "minute"


@pytest.mark.parametrize("granularity", ["minute", "hour", "day", "none"])
def test_service_granularity_round_trips_from_the_global_block(domain_config, granularity):
    domain_config(booking={"granularity": granularity})
    row = _service_row()
    row["metadata"] = {}
    assert S.serialize_service(row)["granularity"] == granularity


def test_service_granularity_none_is_the_no_date_request_flow(domain_config):
    """`booking.granularity: "none"` is the seam that tells the client the
    customer picks NO date — the business assigns one afterwards. It must
    survive as a per-service override beside a normal calendar service, which is
    the whole point of a marketplace deployment."""
    domain_config(booking={"granularity": "minute"})
    calendar = _service_row()
    calendar["metadata"] = {}
    enquiry = _service_row()
    enquiry["metadata"] = {"booking": {"granularity": "none"}}
    assert S.serialize_service(calendar)["granularity"] == "minute"
    assert S.serialize_service(enquiry)["granularity"] == "none"


def test_service_approval_window_hours_comes_from_timing(domain_config):
    domain_config(timing={"approvalWindowHours": 72})
    row = _service_row()
    row["metadata"] = {}
    assert S.serialize_service(row)["approvalWindowHours"] == 72
    # ...and a per-service override wins, so one business can promise a faster
    # reply than the deployment default.
    row["metadata"] = {"timing": {"approvalWindowHours": 4}}
    assert S.serialize_service(row)["approvalWindowHours"] == 4


def test_service_charge_per_person_mirrors_the_pricing_block():
    """The wire flag must equal the flag `pricing.quote` bills with — this is
    the number the client multiplies a preview by."""
    shared = _service_row()
    shared["metadata"] = {"pricing": {"chargePerPerson": False}}
    per_head = _service_row()
    per_head["metadata"] = {"pricing": {"chargePerPerson": True}}
    assert S.serialize_service(shared)["chargePerPerson"] is False
    assert S.serialize_service(per_head)["chargePerPerson"] is True
    # Default when nothing declares it: per head (the engine's own default).
    bare = _service_row()
    bare["metadata"] = {}
    assert S.serialize_service(bare)["chargePerPerson"] is True


# --- serialize_resource ----------------------------------------------------

RESOURCE_KEYS = {
    "id",
    "serviceId",
    "name",
    "description",
    "imageUrl",
    "capacity",
    "attributes",
    "active",
}


def test_resource_key_set_and_metadata_projection():
    row = {
        "id": "res-1",
        "name": "Unit 4471",
        "description": "Toyota Yaris",
        "metadata": {
            "service_id": "svc-1",
            "capacity": 4,
            "active": True,
            "attributes": [{"label": "Seats", "value": "5"}],
            "image_url": "http://img/r.png",
        },
    }
    out = S.serialize_resource(row)
    assert set(out) == RESOURCE_KEYS
    assert out["serviceId"] == "svc-1"
    assert out["capacity"] == 4
    assert out["active"] is True
    assert out["attributes"] == [{"label": "Seats", "value": "5"}]


def test_resource_defaults_capacity_and_active():
    out = S.serialize_resource({"id": "r", "name": "Bare", "metadata": {}})
    assert out["capacity"] == 1
    assert out["active"] is True
    assert out["attributes"] == []
    assert out["serviceId"] == ""


# --- serialize_slot --------------------------------------------------------

SLOT_KEYS = {
    "id",
    "serviceId",
    "resourceId",
    "startUtc",
    "endUtc",
    "capacity",
    "bookedCount",
    "status",
}


def test_slot_key_set_and_derived_status():
    row = {
        "id": "slot-1",
        "resource_id": "res-1",
        "starts_at": "2027-01-01T09:00:00+00:00",
        "ends_at": "2027-01-01T10:00:00+00:00",
        "capacity": 3,
        "metadata": {"service_id": "svc-1"},
    }
    out = S.serialize_slot(row, booked_count=1, now=NOW)
    assert set(out) == SLOT_KEYS
    assert out["serviceId"] == "svc-1"
    assert out["startUtc"] == "2027-01-01T09:00:00.000Z"
    assert out["endUtc"] == "2027-01-01T10:00:00.000Z"
    assert out["capacity"] == 3
    assert out["bookedCount"] == 1
    assert out["status"] == "partially_booked"


def test_slot_service_id_kwarg_overrides_metadata():
    row = {
        "id": "s",
        "resource_id": "r",
        "starts_at": FUTURE,
        "ends_at": FUTURE,
        "capacity": 1,
        "metadata": {"service_id": "from-md"},
    }
    out = S.serialize_slot(row, service_id="from-kwarg", now=NOW)
    assert out["serviceId"] == "from-kwarg"


# --- serialize_booking -----------------------------------------------------

BOOKING_KEYS = {
    "id",
    "reference",
    "userId",
    "providerId",
    "serviceId",
    "providerName",
    # The counterparty's logo, embedded beside the name for the same reason:
    # a bookings list must not fetch each provider by id to show a face.
    "providerAvatarUrl",
    "serviceName",
    "resourceId",
    "slotIds",
    "startUtc",
    "endUtc",
    "status",
    "partySize",
    "priceMinorUnits",
    "currency",
    "createdAtUtc",
    "cancelledAtUtc",
    "changeHistory",
    "review",
    # None unless `inventory.returnRequired`; present on every booking so the
    # shape does not change between deployments.
    "loan",
    "prerequisitesPending",
    "prerequisitesMet",
    "payment",
    # What the customer chose where the config offered a choice.
    "partyBands",
    "options",
    "subject",
    # The deployment's own `metaFields.bookings` values, echoed back. Present on
    # every booking (an empty dict where nothing is declared) so the wire shape
    # does not change between deployments.
    "metadata",
}


def _booking_row(status="confirmed"):
    return {
        "id": "bk-1",
        "status": status,
        "client_id": "user-1",
        "created_at": "2026-05-01T00:00:00+00:00",
        "metadata": {
            "reference": "BK-ABC123",
            "provider_id": "prov-1",
            "service_id": "svc-1",
            "resource_id": "res-1",
            "party_size": 2,
            "price_minor_units": 9000,
            "currency": "PLN",
            "change_history": [
                {
                    "at_utc": "2026-05-02T00:00:00+00:00",
                    "from_start_utc": "2027-01-01T09:00:00+00:00",
                    "to_start_utc": "2027-02-01T09:00:00+00:00",
                }
            ],
        },
    }


def test_booking_key_set_and_span():
    out = S.serialize_booking(
        _booking_row(),
        slot_ids=["s1", "s2"],
        start_utc="2027-02-01T09:00:00+00:00",
        end_utc="2027-02-01T11:00:00+00:00",
        now=NOW,
    )
    assert set(out) == BOOKING_KEYS
    assert out["slotIds"] == ["s1", "s2"]
    assert out["userId"] == "user-1"
    assert out["reference"] == "BK-ABC123"
    assert out["partySize"] == 2
    assert out["priceMinorUnits"] == 9000
    assert out["currency"] == "PLN"
    assert out["startUtc"] == "2027-02-01T09:00:00.000Z"
    assert out["status"] == "confirmed"
    assert out["cancelledAtUtc"] is None
    assert out["review"] is None
    # Names default to "" when the endpoint doesn't resolve them.
    assert out["providerName"] == ""
    assert out["serviceName"] == ""


def test_booking_provider_and_service_names_passed_through():
    out = S.serialize_booking(
        _booking_row(),
        slot_ids=["s1"],
        start_utc=FUTURE,
        end_utc=FUTURE,
        provider_name="Vistula Rentals",
        service_name="City Cruiser",
        now=NOW,
    )
    assert out["providerName"] == "Vistula Rentals"
    assert out["serviceName"] == "City Cruiser"


def test_booking_provider_and_service_names_default_to_empty():
    out = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert out["providerName"] == ""
    assert out["serviceName"] == ""


def test_booking_change_history_is_camelcased():
    out = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    entry = out["changeHistory"][0]
    assert set(entry) == {"atUtc", "fromStartUtc", "toStartUtc"}
    assert entry["atUtc"] == "2026-05-02T00:00:00.000Z"


def test_booking_confirmed_in_past_serializes_as_completed():
    out = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=PAST, end_utc=PAST, now=NOW
    )
    assert out["status"] == "completed"


def test_booking_review_is_serialized_when_present():
    review = {"rating": 5, "text": "Great", "created_at": "2026-05-10T00:00:00+00:00"}
    out = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, review=review, now=NOW
    )
    assert out["review"] == {
        "rating": 5,
        "text": "Great",
        "createdAtUtc": "2026-05-10T00:00:00.000Z",
    }


def test_booking_cancelled_at_is_serialized():
    row = _booking_row(status="cancelled")
    row["metadata"]["cancelled_at_utc"] = "2026-05-05T00:00:00+00:00"
    out = S.serialize_booking(row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW)
    assert out["status"] == "cancelled"
    assert out["cancelledAtUtc"] == "2026-05-05T00:00:00.000Z"


def test_booking_include_client_adds_client_email_only_when_true():
    row = _booking_row()
    row["client_email"] = "guest@example.com"

    # Default (client-facing): no clientEmail leaked.
    default = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert "clientEmail" not in default
    assert set(default) == BOOKING_KEYS

    # Owner view: additive clientEmail present alongside the full Booking shape.
    owner_view = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW, include_client=True
    )
    assert set(owner_view) == BOOKING_KEYS | {"clientEmail"}
    assert owner_view["clientEmail"] == "guest@example.com"


def test_booking_include_client_defaults_missing_email_to_empty_string():
    # Booking row without a client_email column -> "" (never KeyError/None).
    out = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW, include_client=True
    )
    assert out["clientEmail"] == ""


# --- providerAvatarUrl + the metaFields echo -------------------------------


def test_booking_provider_avatar_is_passed_through_and_defaults_to_empty():
    """Embedded beside `providerName` for the same reason: a bookings list must
    not fetch each provider by id just to show a face. Defaults to "" (not
    None), so the client renders it without a guard."""
    passed = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE,
        provider_avatar_url="http://img/p.png", now=NOW,
    )
    assert passed["providerAvatarUrl"] == "http://img/p.png"
    bare = S.serialize_booking(
        _booking_row(), slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert bare["providerAvatarUrl"] == ""


def test_booking_metadata_echoes_only_the_declared_meta_fields():
    """`bookings.metadata` is a shared jsonb column: it carries the deployment's
    own `metaFields.bookings` values NEXT TO engine-owned keys (price, ids,
    prerequisite state), each of which already has its own serialized shape.
    Echoing the column wholesale would duplicate — and leak — all of that, so
    the echo is filtered to the DECLARED descriptors.

    The fixture config declares exactly one booking field, `note`."""
    row = _booking_row()
    row["metadata"]["note"] = "Ring the bell"
    out = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert out["metadata"] == {"note": "Ring the bell"}
    # Engine-owned keys that ARE in the same column are deliberately absent.
    for engine_key in (
        "reference", "provider_id", "service_id", "resource_id",
        "party_size", "price_minor_units", "currency", "change_history",
    ):
        assert engine_key in row["metadata"]           # really is in the column
        assert engine_key not in out["metadata"], engine_key


def test_booking_metadata_follows_the_config_not_the_row(domain_config):
    """A pivot that declares a new booking field makes it readable with no code
    change; one that declares none serves `{}` rather than the raw column."""
    domain_config(metaFields={"bookings": [
        {"key": "casketType", "label": "Casket", "type": "text"},
        {"key": "serviceDateUtc", "label": "Service date", "type": "text"},
    ]})
    row = _booking_row()
    row["metadata"].update({
        "casketType": "oak", "serviceDateUtc": "2027-03-02", "note": "undeclared now",
    })
    out = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert out["metadata"] == {"casketType": "oak", "serviceDateUtc": "2027-03-02"}

    domain_config(metaFields={"bookings": []})
    empty = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert empty["metadata"] == {}


def test_booking_metadata_omits_a_declared_field_the_row_never_stored():
    """Declared-but-absent is omitted, not stamped as None — the client can tell
    "not provided" from "provided as empty"."""
    row = _booking_row()
    row["metadata"].pop("note", None)
    out = S.serialize_booking(
        row, slot_ids=["s1"], start_utc=FUTURE, end_utc=FUTURE, now=NOW
    )
    assert out["metadata"] == {}


# --- serialize_user --------------------------------------------------------

USER_KEYS = {
    "id",
    "displayName",
    "email",
    "avatarUrl",
    "timezone",
    "verified",
    "followedProviderIds",
}


def test_user_key_set_and_metadata():
    out = S.serialize_user(
        id="user-1",
        email="a@b.com",
        metadata={
            "display_name": "Ada",
            "avatar_url": "http://img/u.png",
            "timezone": "Europe/Warsaw",
            "verified": True,
        },
        followed_provider_ids=["prov-1"],
    )
    assert set(out) == USER_KEYS
    assert out["displayName"] == "Ada"
    assert out["timezone"] == "Europe/Warsaw"
    assert out["verified"] is True
    assert out["followedProviderIds"] == ["prov-1"]


def test_user_display_name_falls_back_to_email_local_part():
    out = S.serialize_user(id="u", email="jane.doe@example.com", metadata={})
    assert out["displayName"] == "jane.doe"
    assert out["timezone"] == "UTC"
    assert out["verified"] is False
    assert out["followedProviderIds"] == []


# --- import graph ----------------------------------------------------------


def test_serialize_can_be_imported_on_its_own_without_a_circular_import():
    """`serialize_service` reaches into `app.rules` for `effective_auto_approve`,
    and `app.rules` imports `app.config`/`app.config_schema` — a cycle here would
    only show up as an ImportError on the first module to be imported in a fresh
    process (never in this suite, where conftest has already imported both). Pin
    it in a subprocess so the claim is actually tested.
    """
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2] / "backend"
    for module in ("app.serialize", "app.rules"):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=str(backend), capture_output=True, text=True,
        )
        assert proc.returncode == 0, (module, proc.stderr)
