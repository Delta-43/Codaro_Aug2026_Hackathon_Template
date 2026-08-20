"""Per-service config overrides — `services.metadata.<block>`.

The hole this file covers: `validate()` only ever ran on the global
`domain.config.json` at load. Per-service override blocks (consumed by
`rules.effective_service_config`, and through it by the pricing and scheduling
paths) reached the engine **completely unvalidated** — a service could carry a
`pricing` block that quoted real money with no schema check — and the feature was
unreachable anyway, because the API only ever wrote `image_url`/`auto_approve`
into service metadata.

Three layers, in order:

* `config_schema.validate_overrides(overrides, base=None)` — validate a PARTIAL
  config: merge the declared blocks onto the deployment's resolved config
  (`base`, defaulting to DEFAULTS when none is loaded), validate, and keep
  exactly the errors the override INTRODUCES — i.e. those not already produced by
  the base on its own. Attribution used to be a filter on the error's leading
  path segment, which silently dropped cross-block violations.
* `rules.service_overrides` / `service_override_problems` /
  `effective_service_config` — the READ path: an invalid block is dropped (per
  block, not per service) and falls back to the global one, with a warning.
* `POST`/`PATCH /services` + `POST /bookings` — the WRITE path and the
  marketplace claim it buys: a business's own `pricing` block prices a real
  booking, and a bad block is a 422 that writes nothing.
"""

from __future__ import annotations

import copy
import logging

import pytest

from app import rules as app_rules
from app.config import get_config
from app.config_schema import DEFAULTS, normalize, validate, validate_overrides
from app.rules import (
    OVERRIDABLE_BLOCKS,
    effective_service_config,
    effective_service_pricing,
    service_override_problems,
    service_overrides,
    surviving_overrides,
)
from helpers import DEFAULT_OWNER_ID, make_provider, make_resource, make_service, make_slot

OTHER_OWNER_ID = "99999999-9999-9999-9999-999999999999"

# Key set of the wire `Service` shape — overrides live in metadata and must not
# leak a new key onto it (the frontend contract is frozen).
SERVICE_KEYS = {
    "id", "providerId", "name", "description", "imageUrl", "bookingModel",
    "slotDurationMinutes", "minSlotsPerBooking", "maxSlotsPerBooking",
    "priceMinorUnits", "currency", "cancellationCutoffHours", "autoApprove",
    "capabilities", "pricingModel", "rateUnit", "chargePerPerson", "paymentFlow",
    "billingCycle", "prerequisites", "recurrence", "waitlist", "resourceIds",
    # The v2 offer-shape blocks. Every one was declared in the config, resolved
    # per service, and served to nobody — so the client could not render (let
    # alone collect) a party band, an add-on, a subject, a course or a payment
    # schedule.
    "unitKind",
    # `booking.granularity` (`none` = the customer picks no date at all) and
    # `timing.approvalWindowHours` (display-only reply promise). Both are
    # per-service overridable, hence resolved through effective_service_config.
    "granularity",
    "approvalWindowHours",
    "party",
    "subject",
    "options",
    "sequence",
    "paymentSchedule",
    "locationModes",
    "locationDefault",
}


# ======================================================================
# 1. config_schema.validate_overrides — validating a PARTIAL config
# ======================================================================


def test_the_defaults_base_is_itself_clean():
    """`validate_overrides` merges onto DEFAULTS, so the whole filtering trick
    only works because a bare DEFAULTS tree validates clean. If this ever fails,
    every override call starts inheriting unrelated problems."""
    assert validate(normalize({})) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}}},
        {"pricing": {"currency": "PLN", "chargePerPerson": False}},
        {"pricing": {"fees": [{"key": "clean", "kind": "flat", "amountMinorUnits": 500}]}},
        {"pricing": {"deposit": {"enabled": True, "kind": "percent", "value": 20}}},
        {"timing": {"leadTimeMinutes": 90, "cancellationWindowHours": 4}},
        {"timing": {"confirmation": "request_approve"}},
        {"booking": {"party": {"mode": "group", "min": 2, "max": 8}}},
        {"booking": {"options": [{"key": "seat", "type": "select", "choices": ["a", "b"]}]}},
        {"inventory": {"mode": "rentable", "reservationWindowMinutes": 30}},
        {"location": {"modes": ["remote"], "default": "remote", "timezone": "Europe/Warsaw"}},
        {"payments": {"flow": "pay_on_site", "payer": "customer"}},
        {"recurrence": {"enabled": True, "patterns": ["weekly"]}},
        {"entitlements": {"enabled": True, "kind": "credits", "plans": [{"key": "ten"}]}},
        {"capabilities": {"waitlist": True}},
        # every overridable block at once
        {"pricing": {"currency": "GBP"}, "timing": {"bufferMinutes": 15}},
    ],
)
def test_a_valid_override_block_reports_no_problems(overrides):
    assert validate_overrides(overrides) == []


@pytest.mark.parametrize("empty", [None, {}, {"pricing": {}}])
def test_empty_overrides_are_clean(empty):
    assert validate_overrides(empty) == []


def test_unknown_top_level_keys_are_ignored():
    """A service's metadata is a grab bag (`image_url`, `auto_approve`, whatever
    a niche adds). Only keys that name a real config block are validated."""
    assert validate_overrides({"image_url": "x", "auto_approve": False, "nope": {"a": 1}}) == []


def test_unknown_keys_alongside_a_declared_block_do_not_suppress_its_errors():
    problems = validate_overrides(
        {"image_url": "x", "pricing": {"rate": {"per": "fortnight"}}}
    )
    assert len(problems) == 1
    assert problems[0].startswith("pricing.rate.per must be one of")


def test_a_bad_enum_names_its_path():
    problems = validate_overrides({"pricing": {"rate": {"per": "fortnight"}}})
    assert problems == [
        "pricing.rate.per must be one of "
        "['booking', 'day', 'hour', 'month', 'night', 'person', 'slot', 'unit', 'week'], "
        "got 'fortnight'"
    ]


@pytest.mark.parametrize(
    "block, overrides, path",
    [
        ("pricing", {"pricing": {"model": "haggle"}}, "pricing.model"),
        ("booking", {"booking": {"unitKind": "vibes"}}, "booking.unitKind"),
        ("booking", {"booking": {"granularity": "fortnight"}}, "booking.granularity"),
        ("timing", {"timing": {"confirmation": "maybe"}}, "timing.confirmation"),
        ("payments", {"payments": {"flow": "cheque"}}, "payments.flow"),
        ("inventory", {"inventory": {"mode": "loads"}}, "inventory.mode"),
        ("entitlements", {"entitlements": {"kind": "vouchers"}}, "entitlements.kind"),
        ("pricing", {"pricing": {"deposit": {"kind": "share"}}}, "pricing.deposit.kind"),
    ],
)
def test_every_enum_position_in_an_overridable_block_is_checked(block, overrides, path):
    problems = validate_overrides(overrides)
    assert any(p.startswith(path + " must be one of") for p in problems), problems
    # ...and the error is attributed to the block that was declared.
    assert all(p.split(".", 1)[0] == block for p in problems), problems


def test_a_typoed_fee_kind_is_rejected():
    """The motivating case: `pricing._fee_amount` contributes 0 for an
    unrecognised kind with no breakdown line, so a `"percentage"` typo is a
    permanently under-charged booking. This validator is the only thing between
    the typo and the money."""
    problems = validate_overrides(
        {"pricing": {"fees": [{"key": "svc", "kind": "percentage", "rateBps": 500}]}}
    )
    assert problems == [
        "pricing.fees[0].kind must be one of ['distanceBand', 'flat', 'percent'], "
        "got 'percentage'"
    ]


def test_an_indexed_error_keeps_its_index_and_its_block():
    """A `pricing.fees[0]...` error keeps the `[i]` suffix, which is what
    `rules.surviving_overrides` strips to decide WHICH block to drop."""
    problems = validate_overrides({"pricing": {"fees": [{"key": "x", "kind": "nope"}]}})
    assert problems and all("[0]" in p for p in problems)


@pytest.mark.parametrize(
    "fee, fragment",
    [
        ({"key": "svc", "kind": "percent"}, "pricing.fees[0].rateBps must be a number"),
        ({"key": "svc", "kind": "percent", "rateBps": -1}, "pricing.fees[0].rateBps must be >= 0"),
        ({"key": "svc", "kind": "flat"}, "pricing.fees[0].amountMinorUnits must be a number"),
        ({"key": "svc"}, "pricing.fees[0].amountMinorUnits must be a number"),  # kind defaults to flat
        ({"key": "svc", "kind": "distanceBand"}, "pricing.fees[0].bands must be a non-empty list"),
        (
            {"key": "svc", "kind": "distanceBand", "bands": "10km"},
            "pricing.fees[0].bands must be a non-empty list",
        ),
        ("not-an-object", "pricing.fees[0] must be an object"),
    ],
)
def test_malformed_fee_descriptors_are_rejected(fee, fragment):
    problems = validate_overrides({"pricing": {"fees": [fee]}})
    assert any(p.startswith(fragment) for p in problems), problems


def test_a_bad_party_range_is_rejected():
    assert validate_overrides({"booking": {"party": {"min": 5, "max": 2}}}) == [
        "booking.party.min must not exceed booking.party.max"
    ]


def test_a_party_minimum_below_one_is_rejected():
    problems = validate_overrides({"booking": {"party": {"min": 0}}})
    assert problems == ["booking.party.min must be >= 1, got 0"]


def test_a_select_option_without_choices_is_rejected():
    problems = validate_overrides({"booking": {"options": [{"key": "seat", "type": "select"}]}})
    assert problems == ["booking.options[0].choices is required for a select option"]


def test_every_problem_in_one_block_is_reported_at_once():
    problems = validate_overrides(
        {
            "pricing": {
                "model": "haggle",
                "currency": "EUROS",
                "rate": {"per": "fortnight", "amountMinorUnits": -5},
                "fees": [{"key": "svc", "kind": "percentage"}],
                "deposit": {"kind": "share"},
            }
        }
    )
    joined = " | ".join(problems)
    for fragment in (
        "pricing.model",
        "pricing.currency",
        "pricing.rate.per",
        "pricing.rate.amountMinorUnits",
        "pricing.fees[0].kind",
        "pricing.deposit.kind",
    ):
        assert fragment in joined, (fragment, problems)


def test_problems_from_several_declared_blocks_are_all_reported():
    problems = validate_overrides(
        {
            "pricing": {"rate": {"per": "fortnight"}},
            "booking": {"party": {"min": 5, "max": 2}},
            "timing": {"confirmation": "maybe"},
        }
    )
    assert {p.split(".", 1)[0].split(" ", 1)[0] for p in problems} == {
        "pricing",
        "booking",
        "timing",
    }


def test_a_partial_block_merges_over_the_defaults_rather_than_replacing_them():
    """Declaring `rate.per` alone must not fail for the `amountMinorUnits` it
    didn't restate — otherwise every override would have to be a whole block."""
    assert validate_overrides({"pricing": {"rate": {"per": "night"}}}) == []
    assert validate_overrides({"pricing": {"rate": {"per": "night"}}}) == validate_overrides(
        {"pricing": {"rate": {"per": "night", "amountMinorUnits": 0}}}
    )


def test_errors_already_present_in_the_base_are_not_attributed_to_the_caller(monkeypatch):
    """Attribution is a DIFF against the base's own errors, not a filter on the
    error's leading path segment.

    What survived the change: a service overriding `pricing` must never be blamed
    for the deployment's own broken `tenancy` — a pre-existing defect in the base
    is not the override's fault, so it is reported to NOBODY (not even to a caller
    that happens to declare the same block). What the old leading-segment filter
    got wrong is the other half, covered by the next test: an error the override
    *introduces* is reported even when it names a block the caller never declared.

    DEFAULTS is clean, so the only way to prove this (rather than the absence of a
    problem) is to break the base the overrides merge onto.
    """
    monkeypatch.setitem(DEFAULTS["tenancy"], "mode", "single")  # providerCode is None
    # the base really is broken now...
    base_problems = validate(normalize({}))
    assert any(p.startswith("tenancy.providerCode") for p in base_problems)
    # ...and a service declaring an unrelated block hears nothing about it.
    assert validate_overrides({"timing": {"leadTimeMinutes": 90}}) == []
    assert validate_overrides({"pricing": {"currency": "PLN"}}) == []
    # nor does one that declares `tenancy` itself: it did not introduce the error.
    assert validate_overrides({"tenancy": {"mode": "single"}}) == []
    assert validate_overrides({"tenancy": {"commission": {"enabled": True}}}) == []
    # its own NEW problems still surface, in the same call.
    assert validate_overrides({"timing": {"confirmation": "maybe"}}) == [
        "timing.confirmation must be one of ['instant', 'request_approve'], got 'maybe'"
    ]
    assert validate_overrides({"tenancy": {"commission": {"rateBps": -1}}}) == [
        "tenancy.commission.rateBps must be >= 0, got -1"
    ]


def test_an_override_that_introduces_an_error_is_reported_even_when_it_names_another_block():
    """The bug the diff-based attribution fixed. On a deployment with
    `capabilities.payments: false` (so `payments.flow` must be `"none"`), a
    service overriding ONLY `payments.flow` produces an error phrased from the
    `capabilities` side. The old filter — keep errors whose leading path segment
    is a declared block — dropped it as 'undeclared', so the write gate accepted
    exactly the contradiction `validate()` exists to prevent.
    """
    base = normalize({"capabilities": {"payments": False}, "payments": {"flow": "none"}})
    assert validate(base) == []  # the deployment itself is consistent
    problems = validate_overrides({"payments": {"flow": "prepay"}}, base)
    assert len(problems) == 1
    assert problems[0].startswith("capabilities.payments is false")
    assert "payments.flow" in problems[0]
    # the caller declared `payments` only — the error names `capabilities`.
    assert problems[0].split(".", 1)[0] == "capabilities"
    # an override that keeps the deployment consistent is still clean.
    assert validate_overrides({"payments": {"payer": "customer"}}, base) == []
    assert validate_overrides({"payments": {"flow": "none"}}, base) == []
    # and declaring both halves in one override resolves it.
    assert validate_overrides(
        {"capabilities": {"payments": True}, "payments": {"flow": "prepay"}}, base
    ) == []


def test_the_cross_block_contradiction_is_caught_by_the_write_gate(client, db, auth, domain_config):
    """The same case through the real `POST /services`: on a payments-disabled
    deployment a business cannot write a `payments.flow: "prepay"` block. This is
    what the dropped cross-block error used to let through."""
    domain_config(capabilities={"payments": False}, payments={"flow": "none"})
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(client, p["id"], config={"payments": {"flow": "prepay"}})
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert any("capabilities.payments is false" in problem
               for problem in detail["details"]["problems"])
    assert db.count("services") == 0
    # the same block is accepted on a deployment that allows payments.
    domain_config(capabilities={"payments": True}, payments={"flow": "none"})
    assert _post_service(client, p["id"], config={"payments": {"flow": "prepay"}}).status_code == 200


def test_an_explicit_base_beats_the_defaults_fallback_where_the_deployment_differs():
    """`base` defaults to DEFAULTS only so the function stays usable without a
    loaded config; every real caller passes `get_config()`, because cross-block
    invariants are meaningless against the wrong baseline. `location.modes:
    ["remote"]` is the clean demonstration: against DEFAULTS it contradicts the
    default `location.default` ("on_site"), and on a deployment that is already
    remote-first it is a no-op."""
    against_defaults = validate_overrides({"location": {"modes": ["remote"]}})
    assert against_defaults == [
        "location.default ('on_site') must be one of location.modes ['remote']"
    ]
    remote_first = normalize({"location": {"modes": ["remote"], "default": "remote"}})
    assert validate(remote_first) == []
    assert validate_overrides({"location": {"modes": ["remote"]}}, remote_first) == []
    # passing the DEFAULTS tree explicitly reproduces the fallback exactly.
    assert validate_overrides({"location": {"modes": ["remote"]}}, DEFAULTS) == against_defaults
    assert validate_overrides({"location": {"modes": ["remote"]}}, None) == against_defaults


def test_a_cross_block_error_is_reported_from_whichever_side_introduces_it():
    """`capabilities.payments: false` with a non-`none` `payments.flow` is one
    error phrased from the capabilities side; declaring `capabilities` alone
    introduces it (the flow it conflicts with comes from the base). The mirror
    image — declaring only `payments` on a payments-disabled deployment — is the
    case the old leading-segment filter dropped, covered above."""
    problems = validate_overrides({"capabilities": {"payments": False}})
    assert len(problems) == 1
    assert problems[0].startswith("capabilities.payments is false")
    # declaring the other half of the pair resolves it.
    assert validate_overrides(
        {"capabilities": {"payments": False}, "payments": {"flow": "none"}}
    ) == []


def test_validate_overrides_knows_nothing_about_which_blocks_are_overridable():
    """`validate_overrides` validates any block name that exists in DEFAULTS;
    restricting the set (no `tenancy`, no `terms`) is the ROUTER's job. Pinned so
    the two responsibilities don't get merged by accident."""
    assert validate_overrides({"terms": {"slot": ""}}) == ["terms.slot must be a non-empty string"]
    assert validate_overrides({"tenancy": {"commission": {"rateBps": -1}}}) == [
        "tenancy.commission.rateBps must be >= 0, got -1"
    ]


def test_validate_overrides_mutates_neither_the_defaults_nor_its_argument():
    before = copy.deepcopy(DEFAULTS)
    overrides = {"pricing": {"currency": "PLN"}, "timing": {"leadTimeMinutes": 5}}
    snapshot = copy.deepcopy(overrides)
    validate_overrides(overrides)
    assert DEFAULTS == before
    assert overrides == snapshot


def test_a_malformed_season_window_is_reported_with_its_dotted_path():
    """FIXED (was a known gap). `validate()` used to phrase this one problem
    without a dotted path ("timing seasons/blackouts entry 0 needs startDate and
    endDate"), covering both lists in a single concatenated sentence, so the
    block-attribution filter in `validate_overrides` could not recognise it as a
    `timing` error and dropped it — a malformed window sailed through the
    per-service write gate while the global load path rejected it. `validate()`
    now walks `seasons` and `blackouts` separately and emits
    `timing.<list>[i] needs startDate and endDate`, so BOTH paths catch it.
    """
    bad = {"timing": {"seasons": [{"startDate": "2026-01-01"}]}}
    assert validate(normalize(bad))  # the global load path catches it...
    assert validate_overrides(bad) == [
        "timing.seasons[0] needs startDate and endDate"
    ]  # ...and so does the per-service path now


@pytest.mark.parametrize("key", ["seasons", "blackouts"])
@pytest.mark.parametrize(
    "window",
    [
        {},
        {"startDate": "2026-01-01"},                 # no end
        {"endDate": "2026-03-01"},                   # no start
        {"startDate": "", "endDate": "2026-03-01"},  # empty start
        {"startDate": "2026-01-01", "endDate": ""},  # empty end
        "2026-01-01/2026-03-01",                     # not an object at all
        None,
    ],
)
def test_both_window_lists_reject_a_malformed_entry(key, window):
    """`seasons` and `blackouts` are validated as separate lists, each naming
    itself — not as one merged sentence."""
    assert validate_overrides({"timing": {key: [window]}}) == [
        f"timing.{key}[0] needs startDate and endDate"
    ]


@pytest.mark.parametrize("key", ["seasons", "blackouts"])
def test_a_well_formed_window_in_either_list_is_clean(key):
    assert validate_overrides(
        {"timing": {key: [{"startDate": "2026-01-01", "endDate": "2026-03-01"}]}}
    ) == []


@pytest.mark.parametrize("key", ["seasons", "blackouts"])
def test_each_malformed_window_is_reported_with_its_own_index(key):
    """The index must be the entry's position in ITS list, so an owner-facing
    surface can point at the row that is actually broken."""
    good = {"startDate": "2026-01-01", "endDate": "2026-03-01"}
    problems = validate_overrides(
        {"timing": {key: [good, {"startDate": "2026-04-01"}, good, {}]}}
    )
    assert problems == [
        f"timing.{key}[1] needs startDate and endDate",
        f"timing.{key}[3] needs startDate and endDate",
    ]


def test_the_two_window_lists_are_indexed_independently():
    """The old single-pass message shared one counter across both lists; each
    list is now enumerated from 0 on its own."""
    good = {"startDate": "2026-01-01", "endDate": "2026-03-01"}
    problems = validate_overrides(
        {"timing": {"seasons": [good, {"startDate": "x"}], "blackouts": [{}, good]}}
    )
    assert set(problems) == {
        "timing.seasons[1] needs startDate and endDate",
        "timing.blackouts[0] needs startDate and endDate",
    }


def test_a_malformed_window_does_not_suppress_the_blocks_other_problems():
    problems = validate_overrides(
        {"timing": {"confirmation": "maybe", "blackouts": [{"startDate": "2026-01-01"}]}}
    )
    assert set(problems) == {
        "timing.confirmation must be one of ['instant', 'request_approve'], got 'maybe'",
        "timing.blackouts[0] needs startDate and endDate",
    }


def test_a_malformed_window_in_the_defaults_is_blamed_on_nobody(monkeypatch):
    """The path was added so the error is *attributable*; the diff decides WHO it
    is attributable to. A window that is already broken in the base is a
    pre-existing defect of the deployment, not something any override introduced,
    so no caller is blamed for it — including one that declares `timing`."""
    monkeypatch.setitem(DEFAULTS["timing"], "blackouts", [{"startDate": "2026-01-01"}])
    assert "timing.blackouts[0] needs startDate and endDate" in validate(normalize({}))
    assert validate_overrides({"pricing": {"currency": "PLN"}}) == []
    assert validate_overrides({"timing": {"bufferMinutes": 5}}) == []
    # the deployment's own load path is what must catch it, and still does.
    assert validate(normalize({"timing": {"blackouts": [{"startDate": "2026-01-01"}]}})) == [
        "timing.blackouts[0] needs startDate and endDate"
    ]


def test_a_malformed_window_the_override_itself_introduces_is_still_reported(monkeypatch):
    """The half that must keep working with a broken base: an override that adds
    its OWN bad window is reported, because that error is not in the baseline."""
    monkeypatch.setitem(DEFAULTS["timing"], "blackouts", [{"startDate": "2026-01-01"}])
    # a different list -> a different path -> a new error.
    assert validate_overrides({"timing": {"seasons": [{"startDate": "2026-04-01"}]}}) == [
        "timing.seasons[0] needs startDate and endDate"
    ]
    # and in the same list: entry 0 is repaired, the new entry 1 is the caller's.
    assert validate_overrides(
        {
            "timing": {
                "blackouts": [
                    {"startDate": "2026-01-01", "endDate": "2026-02-01"},
                    {"startDate": "2026-04-01"},
                ]
            }
        }
    ) == ["timing.blackouts[1] needs startDate and endDate"]


# ======================================================================
# 2. rules.service_overrides / service_override_problems
# ======================================================================


def test_service_overrides_returns_only_the_declared_config_blocks():
    service = {
        "id": "svc-1",
        "metadata": {
            "image_url": "http://img/x.png",
            "auto_approve": False,
            "pricing": {"currency": "PLN"},
            "timing": {"leadTimeMinutes": 90},
        },
    }
    assert service_overrides(service) == {
        "pricing": {"currency": "PLN"},
        "timing": {"leadTimeMinutes": 90},
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"image_url": "x", "auto_approve": True},
        {"tenancy": {"commission": {"rateBps": 9999}}},  # not overridable — inert in metadata
        {"terms": {"slot": "Bay"}},                       # presentation stays global
        {"pricing": "cheap"},                             # non-dict value is ignored
        {"pricing": None},
        {"pricing": [{"currency": "PLN"}]},
    ],
)
def test_service_overrides_ignores_everything_that_is_not_an_overridable_block(metadata):
    assert service_overrides({"id": "s", "metadata": metadata}) == {}


@pytest.mark.parametrize("service", [None, {}, {"metadata": None}, {"metadata": {}}])
def test_service_overrides_of_a_service_without_metadata_is_empty(service):
    assert service_overrides(service) == {}
    assert service_override_problems(service) == []


def test_service_overrides_covers_exactly_the_overridable_block_list():
    metadata = {block: {} for block in OVERRIDABLE_BLOCKS}
    assert set(service_overrides({"metadata": metadata})) == set(OVERRIDABLE_BLOCKS)
    assert "tenancy" not in OVERRIDABLE_BLOCKS  # commission is a platform term


def test_service_override_problems_is_empty_for_a_clean_service(domain_config):
    domain_config()
    service = {"id": "s", "metadata": {"pricing": {"currency": "PLN"}, "timing": {"bufferMinutes": 5}}}
    assert service_override_problems(service) == []


def test_service_override_problems_reports_the_services_own_errors(domain_config):
    domain_config()
    service = {"id": "s", "metadata": {"pricing": {"rate": {"per": "fortnight"}}}}
    assert service_override_problems(service) == [
        "pricing.rate.per must be one of "
        "['booking', 'day', 'hour', 'month', 'night', 'person', 'slot', 'unit', 'week'], "
        "got 'fortnight'"
    ]


def test_a_non_overridable_block_in_metadata_is_never_validated_nor_applied(domain_config):
    """A `tenancy` block written straight into the DB is invisible: not a
    problem, and not merged into anything."""
    domain_config()
    service = {"id": "s", "metadata": {"tenancy": {"mode": "single", "commission": {"rateBps": 5000}}}}
    assert service_override_problems(service) == []
    assert "tenancy" not in effective_service_config(service)


# ======================================================================
# 2b. rules.surviving_overrides — the single source of truth for
#     "which of a service's overrides actually apply"
# ======================================================================


def test_surviving_overrides_returns_every_declared_block_when_they_are_clean(domain_config):
    domain_config()
    metadata = {
        "image_url": "http://img/x.png",
        "auto_approve": False,
        "pricing": {"currency": "PLN"},
        "timing": {"leadTimeMinutes": 90},
    }
    assert surviving_overrides({"id": "s", "metadata": metadata}) == {
        "pricing": {"currency": "PLN"},
        "timing": {"leadTimeMinutes": 90},
    }
    # nothing is dropped, so it agrees with `service_overrides` exactly.
    assert surviving_overrides({"id": "s", "metadata": metadata}) == service_overrides(
        {"id": "s", "metadata": metadata}
    )


def test_surviving_overrides_removes_only_the_offending_block(domain_config):
    domain_config()
    service = {
        "id": "svc-1",
        "metadata": {
            "pricing": {"rate": {"per": "fortnight", "amountMinorUnits": 9900}},
            "booking": {"party": {"min": 5, "max": 2}},
            "timing": {"leadTimeMinutes": 90},
        },
    }
    assert surviving_overrides(service) == {"timing": {"leadTimeMinutes": 90}}


def test_surviving_overrides_drops_a_block_by_its_indexed_error_too(domain_config):
    """`pricing.fees[0].kind` must still be recognised as a `pricing` problem —
    the `[i]` suffix is stripped before the block name is taken."""
    domain_config()
    service = {
        "id": "s",
        "metadata": {
            "pricing": {"fees": [{"key": "svc", "kind": "percentage", "rateBps": 500}]},
            "timing": {"bufferMinutes": 5},
        },
    }
    assert surviving_overrides(service) == {"timing": {"bufferMinutes": 5}}


@pytest.mark.parametrize(
    "service",
    [None, {}, {"metadata": None}, {"metadata": {}},
     {"metadata": {"image_url": "x", "auto_approve": True}}],
)
def test_surviving_overrides_of_a_service_declaring_nothing_is_empty(service):
    assert surviving_overrides(service) == {}


def test_surviving_overrides_skips_validation_for_a_service_declaring_nothing(
    domain_config, monkeypatch
):
    """It runs on the hot booking path (twice per booking: config + pricing), so
    the overwhelming majority of services must not pay for a validation pass."""
    calls = []
    monkeypatch.setattr(
        app_rules, "validate_overrides", lambda o, base=None: calls.append(o) or []
    )
    domain_config()
    for service in (None, {}, {"metadata": {}}, {"metadata": {"auto_approve": False}}):
        assert surviving_overrides(service) == {}
    assert calls == []


def test_surviving_overrides_is_what_both_resolvers_read(domain_config, monkeypatch):
    """The regression guard for the bug: `effective_service_config` and
    `effective_service_pricing` used to decide independently which blocks applied
    and disagreed. Stubbing the one function must move BOTH."""
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 0}})
    service = {"id": "s", "price_minor_units": 4500, "metadata": {"pricing": {"currency": "PLN"}}}
    monkeypatch.setattr(app_rules, "surviving_overrides", lambda s: {})
    assert effective_service_config(service)["pricing"]["currency"] == "EUR"
    assert effective_service_pricing(service)["currency"] == "EUR"


def test_surviving_overrides_logs_the_drop_once_naming_the_service(domain_config, caplog):
    domain_config()
    service = {"id": "svc-42", "metadata": {"pricing": {"rate": {"per": "fortnight"}}}}
    with caplog.at_level(logging.WARNING, logger="app.rules"):
        surviving_overrides(service)
    records = [r for r in caplog.records if r.name == "app.rules"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "svc-42" in message and "pricing" in message and "fortnight" in message


# ======================================================================
# 3. rules.effective_service_config — invalid blocks are DROPPED
# ======================================================================


def test_an_invalid_block_is_dropped_while_a_valid_one_in_the_same_service_applies(domain_config):
    """Per-block isolation is the point: a business's bad `pricing` must not
    silently disable its perfectly good `timing`."""
    domain_config(timing={"leadTimeMinutes": 0, "cancellationWindowHours": 24})
    service = {
        "id": "svc-1",
        "metadata": {
            "pricing": {"rate": {"per": "fortnight", "amountMinorUnits": 9900}},
            "timing": {"leadTimeMinutes": 90},
        },
    }
    resolved = effective_service_config(service)
    assert resolved["timing"]["leadTimeMinutes"] == 90            # valid block survives
    assert resolved["pricing"]["rate"]["per"] == "slot"           # invalid block dropped
    assert resolved["pricing"]["rate"]["amountMinorUnits"] == 0


def test_the_dropped_block_falls_back_to_the_global_block_exactly(domain_config):
    domain_config(
        pricing={
            "currency": "GBP",
            "chargePerPerson": False,
            "rate": {"per": "hour", "amountMinorUnits": 250},
            "fees": [{"key": "clean", "kind": "flat", "amountMinorUnits": 500}],
        }
    )
    service = {"id": "svc-1", "metadata": {"pricing": {"model": "haggle", "currency": "PLN"}}}
    assert effective_service_config(service)["pricing"] == get_config()["pricing"]
    # equal to, but not the cached object itself.
    assert effective_service_config(service)["pricing"] is not get_config()["pricing"]


def test_dropping_a_block_does_not_touch_the_others(domain_config):
    domain_config()
    service = {"id": "svc-1", "metadata": {"pricing": {"model": "haggle"}}}
    resolved = effective_service_config(service)
    clean = effective_service_config(None)
    assert resolved == clean


def test_a_clean_override_still_merges(domain_config):
    """The drop must not become 'ignore every override'."""
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 100}})
    service = {"id": "svc-1", "metadata": {"pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}}}}
    pricing = effective_service_config(service)["pricing"]
    assert pricing["rate"] == {"per": "night", "amountMinorUnits": 9900}
    assert pricing["currency"] == "EUR"  # undeclared key still from the global block


def test_service_override_problems_matches_exactly_the_blocks_that_were_dropped(domain_config):
    domain_config()
    service = {
        "id": "svc-1",
        "metadata": {
            "pricing": {"model": "haggle"},
            "booking": {"party": {"min": 5, "max": 2}},
            "timing": {"leadTimeMinutes": 90},
        },
    }
    problems = service_override_problems(service)
    dropped = {p.split(".", 1)[0].split(" ", 1)[0] for p in problems}
    assert dropped == {"pricing", "booking"}
    resolved = effective_service_config(service)
    clean = effective_service_config(None)
    for block in dropped:
        assert resolved[block] == clean[block]
    assert resolved["timing"]["leadTimeMinutes"] == 90


def test_dropping_a_block_logs_a_warning_naming_the_service_and_the_problem(domain_config, caplog):
    domain_config()
    service = {"id": "svc-42", "metadata": {"pricing": {"rate": {"per": "fortnight"}}}}
    with caplog.at_level(logging.WARNING, logger="app.rules"):
        effective_service_config(service)
    records = [r for r in caplog.records if r.name == "app.rules"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    message = records[0].getMessage()
    assert "svc-42" in message
    assert "pricing" in message
    assert "fortnight" in message


def test_a_service_with_no_id_still_logs_rather_than_crashing(domain_config, caplog):
    domain_config()
    with caplog.at_level(logging.WARNING, logger="app.rules"):
        effective_service_config({"metadata": {"pricing": {"model": "haggle"}}})
    assert "?" in [r.getMessage() for r in caplog.records if r.name == "app.rules"][0]


def test_a_clean_service_logs_nothing(domain_config, caplog):
    domain_config()
    with caplog.at_level(logging.WARNING, logger="app.rules"):
        effective_service_config({"id": "s", "metadata": {"timing": {"leadTimeMinutes": 5}}})
        effective_service_config(None)
    assert [r for r in caplog.records if r.name == "app.rules"] == []


def test_a_service_declaring_no_blocks_pays_no_validation_cost(domain_config, monkeypatch):
    """`effective_service_config` runs on the hot booking path for every service,
    the overwhelming majority of which declare nothing. Validation must be
    skipped entirely for them, not merely return empty."""
    calls = []
    monkeypatch.setattr(
        app_rules, "validate_overrides", lambda o, base=None: calls.append(o) or []
    )
    domain_config()
    for service in (None, {}, {"metadata": {}}, {"metadata": {"image_url": "x", "auto_approve": False}}):
        effective_service_config(service)
    assert calls == []


def test_a_service_declaring_blocks_is_validated_against_the_deployment_config(
    domain_config, monkeypatch
):
    """The cost invariant worth pinning is the zero-call one above (a service
    declaring nothing must not pay for a validation pass at all); the exact call
    count for a DECLARING service is an implementation detail — `validate()` now
    runs twice per `validate_overrides` call (baseline + merged) precisely so the
    errors can be diffed. What this pins instead is the argument: the resolver
    hands the validator the service's declared blocks AND the deployment's own
    resolved config as the base, not DEFAULTS."""
    calls = []
    monkeypatch.setattr(
        app_rules, "validate_overrides", lambda o, base=None: calls.append((o, base)) or []
    )
    domain_config()
    effective_service_config({"metadata": {"pricing": {"currency": "PLN"}}})
    assert [overrides for overrides, _ in calls] == [{"pricing": {"currency": "PLN"}}]
    (_, base), = calls
    assert base == get_config()          # the deployment, not the schema defaults
    assert base is not DEFAULTS


def test_effective_service_pricing_falls_back_to_the_global_block_but_keeps_the_columns(
    domain_config,
):
    """FIXED (was a known wart). The legacy-column fold-in used to consult the
    *rejected* metadata block: because the bad block declared a
    `rate.amountMinorUnits`, the service's own `price_minor_units` column was NOT
    folded in and the service silently priced at the global amount (0 by default)
    — a free booking caused by a typo in an unrelated key. Both resolvers read
    `rules.surviving_overrides` now, so the rejected block is invisible here and
    the column wins.
    """
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 0}})
    service = {
        "id": "svc-1",
        "price_minor_units": 4500,
        "currency": "PLN",
        "metadata": {"pricing": {"rate": {"per": "fortnight", "amountMinorUnits": 9900}}},
    }
    pricing = effective_service_pricing(service)
    assert pricing["rate"]["amountMinorUnits"] == 4500      # its own column
    assert pricing["rate"]["amountMinorUnits"] != 0         # not the global default (the bug)
    assert pricing["rate"]["amountMinorUnits"] != 9900      # not the rejected block's amount
    assert pricing["rate"]["per"] == "slot"                 # the rest is the global block
    assert pricing["currency"] == "PLN"                     # the currency column still applies
    # identical to a service carrying no override at all: the bad block is inert.
    clean = dict(service)
    clean["metadata"] = {}
    assert pricing == effective_service_pricing(clean)


def test_a_rejected_pricing_block_cannot_zero_a_service_with_no_column_either(domain_config):
    """With no `price_minor_units` column there is nothing to fold in, so the
    global amount is the right answer — the fix must not invent a price."""
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 700}})
    service = {"id": "s", "metadata": {"pricing": {"rate": {"per": "fortnight"}}}}
    assert effective_service_pricing(service)["rate"] == {"per": "slot", "amountMinorUnits": 700}


def test_a_valid_pricing_block_still_beats_the_columns(domain_config):
    """The fix is about the REJECTED case only: a declared, valid amount must
    still win over the legacy column."""
    domain_config(pricing={"currency": "EUR", "rate": {"per": "slot", "amountMinorUnits": 0}})
    service = {
        "id": "s",
        "price_minor_units": 4500,
        "currency": "PLN",
        "metadata": {"pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}, "currency": "GBP"}},
    }
    pricing = effective_service_pricing(service)
    assert pricing["rate"] == {"per": "night", "amountMinorUnits": 9900}
    assert pricing["currency"] == "GBP"


def test_effective_auto_approve_survives_an_invalid_timing_block(domain_config):
    """A bad `timing` override must not flip a service's confirmation mode: the
    block is dropped, so the global `timing.confirmation` decides."""
    domain_config(timing={"confirmation": "request_approve"})
    bad = {"id": "s", "metadata": {"timing": {"confirmation": "instant", "leadTimeMinutes": -5}}}
    assert app_rules.effective_auto_approve(bad) is False
    good = {"id": "s", "metadata": {"timing": {"confirmation": "instant"}}}
    assert app_rules.effective_auto_approve(good) is True


# ======================================================================
# 4. POST /services — the write path
# ======================================================================

VALID_CONFIG = {
    "pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}, "chargePerPerson": False},
    "timing": {"leadTimeMinutes": 0, "cancellationWindowHours": 4},
}


def _post_service(client, provider_id, **fields):
    return client.post("/services", json={"providerId": provider_id, "name": "S", **fields})


def test_create_service_persists_validated_config_blocks_into_metadata(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(client, p["id"], config=VALID_CONFIG, imageUrl="http://img/x.png")
    assert resp.status_code == 200
    body = resp.json()
    # the wire shape is unchanged — overrides are backend state, not a new field.
    assert set(body) == SERVICE_KEYS
    stored = db.get_row("services", body["id"])
    assert stored["metadata"]["pricing"] == VALID_CONFIG["pricing"]
    assert stored["metadata"]["timing"] == VALID_CONFIG["timing"]
    # ...alongside the non-column fields, not instead of them.
    assert stored["metadata"]["image_url"] == "http://img/x.png"
    # `autoApprove` was not sent, so no key is written at all (it used to be
    # stamped `true` unconditionally, which shadowed a `timing.confirmation`
    # override — see the confirmation-override tests below).
    assert "auto_approve" not in stored["metadata"]
    assert body["autoApprove"] is True  # from the config default, not a stamp
    # and never as columns.
    assert "pricing" not in {k for k in stored if k != "metadata"}


def test_create_service_without_config_writes_no_metadata_at_all(client, db, auth):
    """Every non-column field is optional now, so a bare create leaves metadata
    empty — nothing is stamped on the caller's behalf."""
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    body = _post_service(client, p["id"]).json()
    assert db.get_row("services", body["id"])["metadata"] == {}
    assert body["autoApprove"] is True  # the config default still applies


@pytest.mark.parametrize("value", [True, False])
def test_create_service_writes_auto_approve_only_when_it_is_sent(client, db, auth, value):
    """`ServiceCreate.auto_approve` is `bool | None = None`: an explicit value
    (either one) is persisted as the owner's toggle and wins over the config."""
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    body = _post_service(client, p["id"], autoApprove=value).json()
    assert db.get_row("services", body["id"])["metadata"] == {"auto_approve": value}
    assert body["autoApprove"] is value


@pytest.mark.parametrize("config", [None, {}])
def test_create_service_with_an_empty_config_is_a_no_op(client, db, auth, config):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    body = _post_service(client, p["id"], config=config).json()
    assert db.get_row("services", body["id"])["metadata"] == {}


@pytest.mark.parametrize("config", [None, {}])
def test_an_empty_config_does_not_swallow_the_other_metadata_fields(client, db, auth, config):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    body = _post_service(
        client, p["id"], config=config, imageUrl="http://img/x.png", autoApprove=False
    ).json()
    assert db.get_row("services", body["id"])["metadata"] == {
        "image_url": "http://img/x.png",
        "auto_approve": False,
    }


@pytest.mark.parametrize(
    "config, fragment",
    [
        ({"pricing": {"rate": {"per": "fortnight"}}}, "pricing.rate.per"),
        ({"pricing": {"fees": [{"key": "svc", "kind": "percentage", "rateBps": 500}]}},
         "pricing.fees[0].kind"),
        ({"pricing": {"currency": "EUROS"}}, "pricing.currency"),
        ({"booking": {"party": {"min": 5, "max": 2}}}, "booking.party.min"),
        ({"timing": {"confirmation": "maybe"}}, "timing.confirmation"),
        ({"timing": {"cancellationWindowHours": -1}}, "timing.cancellationWindowHours"),
        # the season/blackout windows reach the gate now that their message
        # carries a dotted path (they used to be filtered out as pathless).
        ({"timing": {"seasons": [{"startDate": "2026-01-01"}]}}, "timing.seasons[0]"),
        ({"timing": {"blackouts": [{"endDate": "2026-01-01"}]}}, "timing.blackouts[0]"),
    ],
)
def test_create_service_with_an_invalid_block_is_a_422_and_writes_nothing(
    client, db, auth, config, fragment
):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(client, p["id"], config=config)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert fragment in detail["message"]
    # the problems ride in the envelope's details so a UI can show them per key.
    assert any(fragment in p for p in detail["details"]["problems"])
    assert db.count("services") == 0


def test_the_422_envelope_lists_every_problem_at_once(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(
        client,
        p["id"],
        config={
            "pricing": {"model": "haggle", "rate": {"per": "fortnight"}},
            "booking": {"party": {"min": 5, "max": 2}},
        },
    )
    assert resp.status_code == 422
    problems = resp.json()["detail"]["details"]["problems"]
    assert len(problems) == 3
    assert {p.split(".", 1)[0].split(" ", 1)[0] for p in problems} == {"pricing", "booking"}


@pytest.mark.parametrize("block", ["terms", "copy", "theme", "metaFields", "discovery", "nonsense"])
def test_create_service_with_an_unknown_block_is_a_422(client, db, auth, block):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(client, p["id"], config={block: {"whatever": 1}})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert f"Unknown config block(s): {block}" in detail["message"]
    # the message tells the caller what IS allowed.
    for allowed in OVERRIDABLE_BLOCKS:
        assert allowed in detail["message"]
    assert db.count("services") == 0


def test_tenancy_is_deliberately_not_overridable(client, db, auth):
    """A tenant must not be able to set its own commission: `tenancy` is a
    platform term, so it is rejected as an unknown block rather than merged."""
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(
        client,
        p["id"],
        config={"tenancy": {"commission": {"enabled": False, "rateBps": 0}}},
    )
    assert resp.status_code == 422
    assert "Unknown config block(s): tenancy" in resp.json()["detail"]["message"]
    assert "tenancy" not in OVERRIDABLE_BLOCKS
    assert db.count("services") == 0


def test_an_unknown_block_is_rejected_even_next_to_a_valid_one(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = _post_service(
        client, p["id"], config={"pricing": {"currency": "PLN"}, "tenancy": {"mode": "multi"}}
    )
    assert resp.status_code == 422
    assert db.count("services") == 0


def test_create_service_with_config_requires_a_token(client, db):
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = client.post("/services", json={"providerId": p["id"], "name": "S", "config": VALID_CONFIG})
    assert resp.status_code == 401
    assert db.count("services") == 0


def test_a_client_cannot_set_a_service_config(client, db, auth):
    auth(role="client")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = client.post("/services", json={"providerId": p["id"], "name": "S", "config": VALID_CONFIG})
    assert resp.status_code == 403
    assert db.count("services") == 0


def test_owner_gating_runs_before_config_validation(client, db, auth):
    """A non-owner posting a BAD config still gets 403, not a 422 that would
    leak which blocks exist."""
    auth(role="client")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    resp = client.post(
        "/services",
        json={"providerId": p["id"], "name": "S", "config": {"pricing": {"model": "haggle"}}},
    )
    assert resp.status_code == 403


# ======================================================================
# 5. The marketplace claim: a real booking priced by the service's own config
# ======================================================================


def _bookable(db, service_id, *, owner_id=DEFAULT_OWNER_ID, duration=60):
    """A resource + one future slot under an existing service."""
    resource = make_resource(db, "Unit", service_id=service_id, capacity=1, owner_id=owner_id)
    slot = make_slot(
        db, resource["id"], service_id=service_id, hours_ahead=48, capacity=1,
        duration_minutes=duration,
    )
    return resource, slot


def test_a_service_created_with_a_pricing_config_prices_a_real_booking(client, db, auth):
    """End to end, through the real endpoints: an owner creates two services with
    IDENTICAL price columns, one of which declares its own `pricing` block, and a
    customer's booking is billed by the service's own config — not by the column
    and not by the platform default. This is the marketplace claim.
    """
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    common = {
        "slotDurationMinutes": 60,
        "priceMinorUnits": 1000,   # the v1 column both services share
        "currency": "EUR",
    }
    pivoted = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "Per-night suite",
            "config": {"pricing": {"rate": {"per": "night", "amountMinorUnits": 9900}}},
            **common,
        },
    ).json()
    plain = client.post(
        "/services", json={"providerId": p["id"], "name": "Per-slot desk", **common}
    ).json()

    pivoted_res, pivoted_slot = _bookable(db, pivoted["id"])
    plain_res, plain_slot = _bookable(db, plain["id"])

    auth(role="client", email="ada@example.com")

    def _book(service, resource, slot):
        resp = client.post(
            "/bookings",
            json={
                "serviceId": service["id"],
                "resourceId": resource["id"],
                "slotIds": [slot["id"]],
                "partySize": 1,
            },
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    priced = _book(pivoted, pivoted_res, pivoted_slot)
    default = _book(plain, plain_res, plain_slot)

    assert priced["priceMinorUnits"] == 9900      # the service's own pricing block
    assert default["priceMinorUnits"] == 1000     # the untouched column, same deployment
    stored = db.get_row("bookings", priced["id"])["metadata"]
    assert stored["price_minor_units"] == 9900
    assert stored["price_breakdown"][0]["amountMinorUnits"] == 9900


def test_a_service_created_with_a_fee_and_deposit_config_bills_them(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "With extras",
            "slotDurationMinutes": 60,
            "priceMinorUnits": 5000,
            "config": {
                "pricing": {
                    "fees": [{"key": "clean", "label": "Cleaning", "kind": "flat",
                              "amountMinorUnits": 1500}],
                    "deposit": {"enabled": True, "kind": "percent", "value": 20,
                                "refundable": False},
                }
            },
        },
    ).json()
    resource, slot = _bookable(db, svc["id"])

    auth(role="client")
    booking = client.post(
        "/bookings",
        json={
            "serviceId": svc["id"],
            "resourceId": resource["id"],
            "slotIds": [slot["id"]],
            "partySize": 1,
        },
    ).json()
    assert booking["priceMinorUnits"] == 6500          # 5000 column + 1500 configured fee
    md = db.get_row("bookings", booking["id"])["metadata"]
    assert [line["key"] for line in md["price_breakdown"]] == ["base", "clean"]
    assert md["deposit_minor_units"] == 1300           # 20% of the capped total


def test_a_service_patched_onto_a_new_pricing_block_reprices_the_next_booking(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = client.post(
        "/services",
        json={"providerId": p["id"], "name": "S", "slotDurationMinutes": 60,
              "priceMinorUnits": 1000},
    ).json()
    r1, s1 = _bookable(db, svc["id"])

    auth(role="client")
    first = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": r1["id"], "slotIds": [s1["id"]],
              "partySize": 1},
    ).json()
    assert first["priceMinorUnits"] == 1000

    auth(role="owner")
    patched = client.patch(
        f"/services/{svc['id']}",
        json={"config": {"pricing": {"rate": {"per": "night", "amountMinorUnits": 12000}}}},
    )
    assert patched.status_code == 200

    r2, s2 = _bookable(db, svc["id"])
    auth(role="client")
    second = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": r2["id"], "slotIds": [s2["id"]],
              "partySize": 1},
    ).json()
    assert second["priceMinorUnits"] == 12000
    # the earlier booking keeps the price it was quoted.
    assert db.get_row("bookings", first["id"])["metadata"]["price_minor_units"] == 1000


def test_a_config_timing_block_can_gate_a_services_confirmation_mode(client, db, auth):
    """`timing.confirmation` as a per-service override: a booking lands *pending*
    with nobody touching `auto_approve`. Seeded directly here; the next test
    drives the same thing through `POST /services` (which used to stamp an
    explicit `auto_approve` that shadowed the override)."""
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(
        db, p["id"], "By request",
        metadata={"timing": {"confirmation": "request_approve"}},
    )
    resource, slot = _bookable(db, svc["id"], duration=30)
    auth(role="client")
    booking = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    ).json()
    assert booking["status"] == "pending"


def test_a_created_services_config_confirmation_override_reaches_the_booking_path(
    client, db, auth
):
    """FIXED (was a known gap). `ServiceCreate.auto_approve` defaulted to `True`
    and `_service_metadata` only drops `None`, so **every** service created
    through `POST /services` carried an explicit `metadata.auto_approve: true`.
    `rules.effective_auto_approve` checks that key first, so a
    `timing.confirmation: "request_approve"` override could never take effect on
    an API-created service. The field is `bool | None = None` now: unset writes no
    key, and the override decides.
    """
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "By request",
            "config": {"timing": {"confirmation": "request_approve"}},
        },
    ).json()
    stored = db.get_row("services", svc["id"])
    assert stored["metadata"]["timing"] == {"confirmation": "request_approve"}
    assert "auto_approve" not in stored["metadata"]            # nothing stamped
    assert svc["autoApprove"] is False                         # the wire agrees...
    assert app_rules.effective_auto_approve(stored) is False   # ...with the engine

    resource, slot = _bookable(db, svc["id"], duration=30)
    auth(role="client")
    booking = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    ).json()
    assert booking["status"] == "pending"  # was "confirmed" while the stamp existed


def test_an_explicit_auto_approve_still_beats_a_config_confirmation_override(client, db, auth):
    """The owner's toggle is still the last word: sending `autoApprove: true`
    alongside a `request_approve` override writes the key and books instantly."""
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "Override the override",
            "autoApprove": True,
            "config": {"timing": {"confirmation": "request_approve"}},
        },
    ).json()
    stored = db.get_row("services", svc["id"])
    assert stored["metadata"]["auto_approve"] is True
    assert svc["autoApprove"] is True
    assert app_rules.effective_auto_approve(stored) is True

    resource, slot = _bookable(db, svc["id"], duration=30)
    auth(role="client")
    booking = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    ).json()
    assert booking["status"] == "confirmed"


def test_an_explicit_auto_approve_false_still_gates_a_service_with_no_override(client, db, auth):
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = client.post(
        "/services", json={"providerId": p["id"], "name": "By request 2", "autoApprove": False}
    ).json()
    assert svc["autoApprove"] is False
    resource, slot = _bookable(db, svc["id"], duration=30)
    auth(role="client")
    booking = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    ).json()
    assert booking["status"] == "pending"


def test_serialized_auto_approve_reflects_the_effective_confirmation_mode(db):
    """FIXED (was the other half of the same gap). `serialize_service` read
    `metadata.auto_approve` directly (`bool(md.get("auto_approve", True))`), so
    the wire field and the booking path disagreed for a service whose
    confirmation came from a `timing.confirmation` override. It calls
    `rules.effective_auto_approve(row)` now."""
    from app.serialize import serialize_service

    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    by_request = make_service(
        db, p["id"], "S", metadata={"timing": {"confirmation": "request_approve"}}
    )
    assert serialize_service(by_request)["autoApprove"] is False
    assert app_rules.effective_auto_approve(by_request) is False  # they agree now

    # an explicit key still wins over the override, on the wire as in the engine.
    forced = make_service(
        db, p["id"], "S2",
        metadata={"timing": {"confirmation": "request_approve"}, "auto_approve": True},
    )
    assert serialize_service(forced)["autoApprove"] is True
    assert app_rules.effective_auto_approve(forced) is True

    # and a plain service is unchanged.
    plain = make_service(db, p["id"], "S3")
    assert serialize_service(plain)["autoApprove"] is True
    assert app_rules.effective_auto_approve(plain) is True


def test_serialized_auto_approve_ignores_an_invalid_timing_override(db):
    """A dropped block must not flip the wire field either — `serialize_service`
    goes through the same resolver, so it sees the fallback."""
    from app.serialize import serialize_service

    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(
        db, p["id"], "S",
        metadata={"timing": {"confirmation": "request_approve", "leadTimeMinutes": -5}},
    )
    assert serialize_service(svc)["autoApprove"] is True
    assert app_rules.effective_auto_approve(svc) is True


def test_the_wire_and_the_booking_path_agree_on_a_by_request_service(client, db, auth):
    """The pairing that was broken, end to end: a service created with only a
    `timing.confirmation` override must report `autoApprove: false` on
    `GET /services/{id}` AND actually produce a pending booking. Before the fix
    the wire said `true` (it read the stamped metadata key) and the booking
    confirmed — the UI and the engine were wrong in the same direction, so
    neither half alone would have shown it.
    """
    auth(role="owner")
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    created = client.post(
        "/services",
        json={
            "providerId": p["id"],
            "name": "Request only",
            "slotDurationMinutes": 30,
            "config": {"timing": {"confirmation": "request_approve"}},
        },
    )
    assert created.status_code == 200, created.text
    svc = created.json()

    fetched = client.get(f"/services/{svc['id']}")
    assert fetched.status_code == 200
    assert set(fetched.json()) == SERVICE_KEYS
    assert fetched.json()["autoApprove"] is False      # what the UI renders

    resource, slot = _bookable(db, svc["id"], duration=30)
    auth(role="client", email="ada@example.com")
    resp = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending"          # what the engine does
    assert db.get_row("bookings", resp.json()["id"])["status"] == "pending"

    # a pending booking holds no capacity, so the slot is still fully available.
    occupancy = client.get("/slots/occupancy", params={"resourceId": resource["id"]})
    assert occupancy.status_code == 200
    row = next(r for r in occupancy.json() if r["slot_id"] == slot["id"])
    assert row["booked_count"] == 0
    assert row["available_count"] == row["capacity"]


# ======================================================================
# 6. PATCH /services/{id} — wholesale-per-block replacement
# ======================================================================


def _seeded(db, **metadata):
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(db, p["id"], "S", metadata=metadata)
    return p, svc


def test_patch_config_replaces_a_block_wholesale(client, db, auth):
    """A partial deep-merge would make it impossible to ever REMOVE a key, so a
    declared block replaces the stored one outright."""
    auth(role="owner")
    _, svc = _seeded(db, pricing={"currency": "PLN", "chargePerPerson": False})
    resp = client.patch(
        f"/services/{svc['id']}", json={"config": {"pricing": {"currency": "USD"}}}
    )
    assert resp.status_code == 200
    stored = db.get_row("services", svc["id"])["metadata"]
    assert stored["pricing"] == {"currency": "USD"}  # chargePerPerson is gone, not merged


def test_patch_config_leaves_untouched_blocks_and_the_other_metadata_intact(client, db, auth):
    auth(role="owner")
    _, svc = _seeded(
        db,
        pricing={"currency": "PLN"},
        timing={"leadTimeMinutes": 90},
        image_url="http://img/keep.png",
        auto_approve=False,
    )
    resp = client.patch(
        f"/services/{svc['id']}", json={"config": {"pricing": {"currency": "USD"}}}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imageUrl"] == "http://img/keep.png"
    assert body["autoApprove"] is False
    stored = db.get_row("services", svc["id"])["metadata"]
    assert stored["pricing"] == {"currency": "USD"}
    assert stored["timing"] == {"leadTimeMinutes": 90}     # untouched block preserved
    assert stored["image_url"] == "http://img/keep.png"
    assert stored["auto_approve"] is False


def test_patch_can_add_a_block_to_a_service_that_had_none(client, db, auth):
    auth(role="owner")
    _, svc = _seeded(db, image_url="http://img/keep.png")
    client.patch(f"/services/{svc['id']}", json={"config": {"timing": {"bufferMinutes": 15}}})
    stored = db.get_row("services", svc["id"])["metadata"]
    assert stored["timing"] == {"bufferMinutes": 15}
    assert stored["image_url"] == "http://img/keep.png"


def test_patch_config_alongside_columns_and_image_url_in_one_call(client, db, auth):
    auth(role="owner")
    _, svc = _seeded(db)
    resp = client.patch(
        f"/services/{svc['id']}",
        json={
            "name": "Renamed",
            "priceMinorUnits": 7700,
            "imageUrl": "http://img/new.png",
            "config": {"pricing": {"chargePerPerson": False}},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["priceMinorUnits"] == 7700
    assert body["imageUrl"] == "http://img/new.png"
    stored = db.get_row("services", svc["id"])
    assert stored["price_minor_units"] == 7700
    assert stored["metadata"]["pricing"] == {"chargePerPerson": False}
    assert stored["metadata"]["image_url"] == "http://img/new.png"
    # `config` is never written as a column.
    assert "config" not in stored


@pytest.mark.parametrize(
    "config, fragment",
    [
        ({"pricing": {"rate": {"per": "fortnight"}}}, "pricing.rate.per"),
        ({"pricing": {"fees": [{"key": "s", "kind": "percentage"}]}}, "pricing.fees[0].kind"),
        ({"booking": {"party": {"min": 5, "max": 2}}}, "booking.party.min"),
    ],
)
def test_patch_with_an_invalid_block_is_a_422_and_writes_nothing(
    client, db, auth, config, fragment
):
    auth(role="owner")
    _, svc = _seeded(db, pricing={"currency": "PLN"}, image_url="http://img/keep.png")
    before = copy.deepcopy(db.get_row("services", svc["id"]))
    resp = client.patch(f"/services/{svc['id']}", json={"name": "Renamed", "config": config})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert any(fragment in p for p in detail["details"]["problems"])
    # nothing at all is written — not even the valid `name` in the same request.
    assert db.get_row("services", svc["id"]) == before


@pytest.mark.parametrize("block", ["tenancy", "terms", "nonsense"])
def test_patch_with_an_unknown_block_is_a_422_and_writes_nothing(client, db, auth, block):
    auth(role="owner")
    _, svc = _seeded(db, pricing={"currency": "PLN"})
    before = copy.deepcopy(db.get_row("services", svc["id"]))
    resp = client.patch(f"/services/{svc['id']}", json={"config": {block: {"x": 1}}})
    assert resp.status_code == 422
    assert f"Unknown config block(s): {block}" in resp.json()["detail"]["message"]
    assert db.get_row("services", svc["id"]) == before


def test_patch_config_requires_a_token(client, db):
    _, svc = _seeded(db)
    resp = client.patch(f"/services/{svc['id']}", json={"config": VALID_CONFIG})
    assert resp.status_code == 401
    assert db.get_row("services", svc["id"])["metadata"] == {}


def test_a_client_cannot_patch_a_service_config(client, db, auth):
    auth(role="client")
    _, svc = _seeded(db)
    resp = client.patch(f"/services/{svc['id']}", json={"config": VALID_CONFIG})
    assert resp.status_code == 403
    assert db.get_row("services", svc["id"])["metadata"] == {}


def test_patch_config_on_an_unknown_service_is_404(client, db, auth):
    auth(role="owner")
    assert client.patch("/services/nope", json={"config": VALID_CONFIG}).status_code == 404


def test_patch_with_an_empty_config_changes_nothing(client, db, auth):
    auth(role="owner")
    _, svc = _seeded(db, pricing={"currency": "PLN"})
    resp = client.patch(f"/services/{svc['id']}", json={"config": {}})
    assert resp.status_code == 200
    assert db.get_row("services", svc["id"])["metadata"] == {"pricing": {"currency": "PLN"}}


def test_a_service_written_with_a_bad_block_before_the_gate_existed_still_serves(client, db, auth):
    """The read-path fallback is for rows the write gate never saw (seeds, direct
    DB edits). Such a service must still be bookable — at the global price, with
    a warning — rather than 500 on a customer's booking."""
    p = make_provider(db, "P", owner_id=DEFAULT_OWNER_ID)
    svc = make_service(
        db, p["id"], "Legacy", slot_duration_minutes=60, price_minor_units=1000,
        metadata={"pricing": {"rate": {"per": "fortnight", "amountMinorUnits": 9900}}},
    )
    resource, slot = _bookable(db, svc["id"])
    auth(role="client")
    resp = client.post(
        "/bookings",
        json={"serviceId": svc["id"], "resourceId": resource["id"], "slotIds": [slot["id"]],
              "partySize": 1},
    )
    assert resp.status_code == 200
    # ...and it is priced by the GLOBAL block folded onto its own column, never by
    # the rejected one. Before `surviving_overrides`, the rejected block's
    # `rate.amountMinorUnits` suppressed the column and this booking was free.
    assert resp.json()["priceMinorUnits"] != 9900   # not the rejected block
    assert resp.json()["priceMinorUnits"] == 1000   # its own price_minor_units column
    assert resp.json()["priceMinorUnits"] != 0      # the silent-zero bug
