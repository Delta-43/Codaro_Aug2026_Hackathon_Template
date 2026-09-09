# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""The v2 `booking` blocks that had no input path until now.

`booking.party.composition`, `booking.options`, `booking.subject` and
`booking.sequence` were declared in the config, validated at load, and reached
neither the pricing engine nor the database: `pricing.quote()` documented a
`person_units` and a `subject` in its context that no caller ever built, and the
add-ons and the course had nowhere to be expressed at all.

These pin the round trip, request body -> resolver -> price -> stored booking,
plus the two closure windows (`timing.blackouts` / `timing.seasons`) that were
in the same state on the scheduling side.
"""

from __future__ import annotations

import pytest

from app.rules import (
    RuleViolation,
    closure_reason,
    resolve_options,
    resolve_party_bands,
    resolve_subject,
)
from app.pricing import quote

from helpers import make_catalog


# --------------------------------------------------------------------
# party.composition -> a weighted head count
# --------------------------------------------------------------------

COMPOSITION = [
    {"key": "adult", "label": "Adult", "priceFactor": 1},
    {"key": "child", "label": "Child", "priceFactor": 0.5},
]


def _service(**booking) -> dict:
    """A service row whose `metadata.booking` overrides the global block."""
    return {"metadata": {"booking": booking}}


def test_bands_weight_the_head_count(domain_config):
    svc = _service(party={"composition": COMPOSITION})
    units, bands = resolve_party_bands({"adult": 2, "child": 1}, 3, svc)
    assert units == 2.5
    assert bands == {"adult": 2, "child": 1}


def test_bands_must_add_up_to_the_party_size(domain_config):
    """Both numbers reach the engine, the party size holds capacity and the
    bands price it, so a disagreement means one of them is wrong."""
    svc = _service(party={"composition": COMPOSITION})
    with pytest.raises(RuleViolation):
        resolve_party_bands({"adult": 2}, 3, svc)


def test_an_undeclared_band_is_refused(domain_config):
    svc = _service(party={"composition": COMPOSITION})
    with pytest.raises(RuleViolation):
        resolve_party_bands({"toddler": 1}, 1, svc)


def test_no_composition_means_no_weighting(domain_config):
    """A deployment that declares no bands prices exactly as it did before."""
    assert resolve_party_bands({"adult": 2}, 2, _service()) == (None, None)


# --------------------------------------------------------------------
# booking.options -> priced add-on lines
# --------------------------------------------------------------------

OPTIONS = [
    {"key": "kit", "label": "Kit hire", "type": "boolean", "priceMinorUnits": 900},
    {
        "key": "meal",
        "label": "Meal",
        "type": "select",
        "choices": [
            {"key": "lunch", "label": "Lunch", "priceMinorUnits": 1400},
            {"key": "full", "label": "Full board", "priceMinorUnits": 2600},
        ],
    },
]


def test_options_resolve_to_priced_lines(domain_config):
    lines = resolve_options({"kit": True, "meal": "full"}, _service(options=OPTIONS))
    assert [(line["key"], line["amountMinorUnits"]) for line in lines] == [
        ("kit", 900),
        ("meal", 2600),
    ]


def test_an_unchosen_option_costs_nothing(domain_config):
    assert resolve_options({"kit": False, "meal": ""}, _service(options=OPTIONS)) == []


def test_an_undeclared_option_or_choice_is_refused(domain_config):
    """The client names the option; the SERVER names the price. A key the config
    never declared must be a rejection, or a client could invent a free banquet."""
    svc = _service(options=OPTIONS)
    with pytest.raises(RuleViolation):
        resolve_options({"helicopter": True}, svc)
    with pytest.raises(RuleViolation):
        resolve_options({"meal": "banquet"}, svc)


def test_addons_are_added_to_the_total_and_itemised():
    """Add-ons land between the entitlement discount and the fees: a member
    discount is on the service, a percentage fee is on everything sold."""
    block = {
        "model": "fixed",
        "currency": "EUR",
        "rate": {"per": "slot", "amountMinorUnits": 1000},
        "fees": [{"key": "svc", "label": "Service", "kind": "percent", "rateBps": 1000}],
        "deposit": {"enabled": False, "kind": "percent", "value": 0},
        "caps": {},
        "tiers": [],
        "chargePerPerson": True,
    }
    plain = quote(block, {"slot_count": 1, "party_size": 1})
    with_addon = quote(
        block,
        {
            "slot_count": 1,
            "party_size": 1,
            "addons": [{"key": "kit", "label": "Kit hire", "amountMinorUnits": 500}],
        },
    )
    assert plain["amountMinorUnits"] == 1100  # 1000 + 10%
    assert with_addon["amountMinorUnits"] == 1650  # (1000 + 500) + 10%
    assert any(line["key"] == "option:kit" for line in with_addon["breakdown"])


# --------------------------------------------------------------------
# booking.subject -> the thing the booking is about
# --------------------------------------------------------------------

SUBJECT = {
    "enabled": True,
    "noun": "Pet",
    "fields": [
        {"key": "name", "label": "Name", "type": "text", "required": True},
        {"key": "species", "label": "Species", "type": "select",
         "options": ["dog", "cat"], "required": False},
    ],
}


def test_a_missing_required_subject_field_is_refused(domain_config):
    with pytest.raises(RuleViolation):
        resolve_subject({}, _service(subject=SUBJECT))


def test_subject_keeps_declared_fields_and_drops_the_rest(domain_config):
    out = resolve_subject(
        {"name": "Rex", "species": "dog", "microchip": "sneaky"},
        _service(subject=SUBJECT),
    )
    assert out == {"name": "Rex", "species": "dog"}


def test_a_value_outside_a_select_is_refused(domain_config):
    with pytest.raises(RuleViolation):
        resolve_subject({"name": "Rex", "species": "iguana"}, _service(subject=SUBJECT))


def test_subject_is_none_when_the_block_is_off(domain_config):
    assert resolve_subject({"name": "Rex"}, _service()) is None


# --------------------------------------------------------------------
# the round trip: a booking records what was chosen
# --------------------------------------------------------------------


def test_create_prices_and_stores_the_chosen_shape(client, db, auth, domain_config):
    domain_config(
        booking={
            "party": {"mode": "group", "composition": COMPOSITION},
            "options": OPTIONS,
            "subject": SUBJECT,
        },
        pricing={"model": "fixed", "currency": "EUR",
                 "rate": {"per": "slot", "amountMinorUnits": 1000}},
    )
    auth(role="client")
    # The service's own price column wins over the config default (that is the
    # documented precedence), so it is the number the weighting applies to.
    cat = make_catalog(db, capacity=5, slot_capacity=5, price_minor_units=1000)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 3,
            "partyBands": {"adult": 2, "child": 1},
            "options": {"kit": True},
            "subject": {"name": "Rex", "species": "dog"},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["partyBands"] == {"adult": 2, "child": 1}
    assert [o["key"] for o in body["options"]] == ["kit"]
    assert body["subject"] == {"name": "Rex", "species": "dog"}
    # 2.5 weighted heads at 1000 + a 900 add-on, not 3 flat heads.
    assert body["priceMinorUnits"] == 2500 + 900


def test_the_quote_and_the_create_agree_on_the_same_shape(client, db, auth, domain_config):
    """The number on the confirm screen has to be the number charged, which is
    only true if the quote is given the same bands, options and subject."""
    domain_config(
        booking={"party": {"mode": "group", "composition": COMPOSITION}, "options": OPTIONS},
        pricing={"model": "fixed", "currency": "EUR",
                 "rate": {"per": "slot", "amountMinorUnits": 1000}},
    )
    auth(role="client")
    cat = make_catalog(db, capacity=5, slot_capacity=5, price_minor_units=1000)
    payload = {
        "serviceId": cat["service"]["id"],
        "resourceId": cat["resource"]["id"],
        "slotIds": [cat["slot"]["id"]],
        "partySize": 3,
        "partyBands": {"adult": 2, "child": 1},
        "options": {"meal": "lunch"},
    }
    quoted = client.post("/bookings/quote", json=payload).json()
    booked = client.post("/bookings", json=payload).json()
    assert quoted["amountMinorUnits"] == booked["priceMinorUnits"]


def test_an_undeclared_option_is_a_clean_rejection(client, db, auth, domain_config):
    domain_config(booking={"options": OPTIONS})
    auth(role="client")
    cat = make_catalog(db)
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
            "options": {"helicopter": True},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_RANGE"


# --------------------------------------------------------------------
# timing.blackouts / timing.seasons, the closure windows
# --------------------------------------------------------------------


def test_a_blackout_closes_the_day(domain_config):
    svc = {"metadata": {"timing": {
        "blackouts": [{"key": "xmas", "label": "Christmas",
                       "startDate": "2026-12-24", "endDate": "2026-12-26"}],
    }}}
    assert closure_reason("2026-12-25T10:00:00Z", svc) is not None
    assert closure_reason("2026-12-27T10:00:00Z", svc) is None


def test_declared_seasons_close_everything_outside_them(domain_config):
    """A season list is a statement that the business is open THEN, which only
    means anything if it is shut the rest of the year."""
    svc = {"metadata": {"timing": {
        "seasons": [{"key": "summer", "startDate": "2026-06-01", "endDate": "2026-09-15"}],
    }}}
    assert closure_reason("2026-07-04T10:00:00Z", svc) is None
    assert closure_reason("2026-10-04T10:00:00Z", svc) is not None


def test_no_windows_declared_closes_nothing(domain_config):
    assert closure_reason("2026-10-04T10:00:00Z", {"metadata": {}}) is None


def test_a_booking_inside_a_blackout_is_refused(client, db, auth, domain_config):
    auth(role="client")
    cat = make_catalog(db)
    slot_day = cat["slot"]["starts_at"][:10]
    domain_config(timing={"blackouts": [
        {"key": "closed", "label": "Stocktake", "startDate": slot_day, "endDate": slot_day},
    ]})
    resp = client.post(
        "/bookings",
        json={
            "serviceId": cat["service"]["id"],
            "resourceId": cat["resource"]["id"],
            "slotIds": [cat["slot"]["id"]],
            "partySize": 1,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_RANGE"
