# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for `app.config_schema` — the v2 pivot-file resolver.

Pure dict work: no Supabase, no FastAPI, no `domain.config.json` dependency
beyond the two files this repo actually ships. Two jobs are pinned here.

**normalize()** is the back-compat contract. v1 files declared five sections
(`terms`/`rules`/`copy`/`theme`/`metaFields`, `theme` since dropped); v2 adds
fifteen more blocks. A v1
file must keep booting, and the two aliased pairs (`rules` <-> `timing`,
`search` <-> `discovery`) must never be able to disagree — a reader on either
path sees the same number.

**validate()** is the "fail at the edit, not at the next booking" contract. This
file gets hand-edited under time pressure; a typo has to be a load-time error
listing *every* problem, not a 500 on whichever request happens to read the bad
key first.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from app.config import load_config
from app.config_schema import (
    ConfigError,
    CONFIG_VERSION,
    DEFAULTS,
    DEPOSIT_KINDS,
    FEE_KINDS,
    META_FIELD_TYPE_ALIASES,
    META_FIELD_TYPES,
    OPTION_TYPES,
    PAYERS,
    PRICING_MODELS,
    RATE_PERIODS,
    RECURRENCE_PATTERNS,
    UNIT_KINDS,
    normalize,
    validate,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CONFIG = REPO_ROOT / "test" / "fixtures" / "domain.config.test.json"
REPO_CONFIG = REPO_ROOT / "domain.config.json"

_TIMING_ALIASES = (
    "slotDurationMinutes",
    "maxBookingsPerSlot",
    "cancellationWindowHours",
    "advanceBookingWindowDays",
    "bufferMinutes",
)


def good() -> dict:
    """A minimal valid raw file (everything else resolves from DEFAULTS)."""
    return {"domain": "test"}


# ======================================================================
# normalize — defaults
# ======================================================================


def test_normalize_of_nothing_is_the_defaults():
    """A half-written config still boots: every key resolves."""
    assert normalize({}) == normalize(None)
    resolved = normalize({})
    for block in DEFAULTS:
        assert block in resolved, block
    assert resolved["configVersion"] == CONFIG_VERSION
    assert validate(resolved) == []


def test_normalize_fills_every_v2_block_a_v1_file_never_heard_of():
    v1 = json.loads(FIXTURE_CONFIG.read_text())
    assert set(v1) == {"domain", "terms", "rules", "copy", "theme", "metaFields"}

    resolved = normalize(v1)

    assert set(resolved) == set(DEFAULTS)
    # ...except v1's `theme`, which the engine no longer has: the frontend owns
    # its palette, so the block is dropped rather than served to nothing.
    assert "theme" not in resolved
    assert resolved["pricing"]["rate"] == {"per": "slot", "amountMinorUnits": 0}
    assert resolved["location"]["timezone"] == "UTC"
    assert resolved["capabilities"]["payments"] is True
    assert resolved["booking"]["unitKind"] == "time_slot"
    # ...and a v1 file is still a *usable* config.
    assert validate(resolved) == []


def test_normalize_keeps_what_the_file_declared():
    v1 = json.loads(FIXTURE_CONFIG.read_text())
    resolved = normalize(v1)
    assert resolved["domain"] == "test-domain"
    assert resolved["terms"]["resource"] == "Widget"
    assert resolved["copy"]["landingTitle"] == "Book a Widget"


def test_normalize_merges_a_partial_block_key_by_key():
    resolved = normalize({"pricing": {"currency": "PLN"}})
    assert resolved["pricing"]["currency"] == "PLN"
    # untouched siblings still resolve
    assert resolved["pricing"]["model"] == "fixed"
    assert resolved["pricing"]["rate"]["per"] == "slot"


def test_normalize_partially_declared_terms_keep_the_default_vocabulary():
    """A pivot renames the two nouns it cares about; the rest must not vanish
    (the frontend reads every term unconditionally)."""
    resolved = normalize({"terms": {"resource": "Doctor"}})
    assert resolved["terms"]["resource"] == "Doctor"
    assert resolved["terms"]["booking"] == DEFAULTS["terms"]["booking"]
    assert set(resolved["terms"]) == set(DEFAULTS["terms"])


def test_normalize_lists_replace_rather_than_merge():
    """`pricing.tiers: [x]` means *those* tiers, not those plus the defaults —
    otherwise a pivot could never delete a default entry."""
    resolved = normalize(
        {
            "location": {"modes": ["remote"], "default": "remote"},
            "pricing": {"tiers": [{"key": "peak", "amountMinorUnits": 100}]},
            "prerequisites": [{"key": "waiver", "kind": "waiver"}],
        }
    )
    assert resolved["location"]["modes"] == ["remote"]
    assert resolved["pricing"]["tiers"] == [{"key": "peak", "amountMinorUnits": 100}]
    assert resolved["prerequisites"] == [{"key": "waiver", "kind": "waiver"}]


def test_normalize_does_not_mutate_the_defaults_or_the_input():
    before = copy.deepcopy(DEFAULTS)
    raw = {"terms": {"resource": "Doctor"}, "pricing": {"currency": "PLN"}}
    raw_before = copy.deepcopy(raw)

    resolved = normalize(raw)
    resolved["terms"]["resource"] = "Mutated"
    resolved["pricing"]["rate"]["amountMinorUnits"] = 99999

    assert DEFAULTS == before
    assert raw == raw_before


def test_normalize_is_idempotent():
    """Normalizing a normalized tree changes nothing — the endpoint, the CI
    validator and the reload path can each run it without drift."""
    for raw in ({}, json.loads(FIXTURE_CONFIG.read_text()), json.loads(REPO_CONFIG.read_text())):
        once = normalize(raw)
        assert normalize(once) == once


def test_both_shipped_config_files_are_normalize_fixpoints_and_valid():
    for path in (REPO_CONFIG, REPO_ROOT / "domain.config.medical.example.json"):
        raw = json.loads(path.read_text())
        assert normalize(raw) == raw, f"{path.name} is no longer an explicit v2 file"
        assert validate(raw) == [], path.name


# ======================================================================
# normalize — the rules <-> timing alias, in BOTH directions
# ======================================================================


@pytest.mark.parametrize("key", _TIMING_ALIASES)
def test_v1_rules_key_is_mirrored_into_timing(key):
    resolved = normalize({"rules": {key: 7}})
    assert resolved["timing"][key] == 7
    assert resolved["rules"][key] == 7


@pytest.mark.parametrize("key", _TIMING_ALIASES)
def test_v2_timing_key_is_mirrored_back_into_rules(key):
    resolved = normalize({"timing": {key: 11}})
    assert resolved["rules"][key] == 11
    assert resolved["timing"][key] == 11


@pytest.mark.parametrize("key", _TIMING_ALIASES)
def test_explicit_timing_wins_over_explicit_rules(key):
    """Precedence is explicit `timing` -> explicit `rules` -> default. The two
    paths can never be left disagreeing."""
    resolved = normalize({"timing": {key: 2}, "rules": {key: 99}})
    assert resolved["timing"][key] == 2
    assert resolved["rules"][key] == 2


@pytest.mark.parametrize("key", _TIMING_ALIASES)
def test_an_undeclared_alias_falls_to_the_default_on_both_paths(key):
    resolved = normalize({})
    assert resolved["timing"][key] == DEFAULTS["timing"][key]
    assert resolved["rules"][key] == DEFAULTS["timing"][key]


def test_timing_keeps_its_own_v2_only_keys_alongside_the_aliases():
    resolved = normalize({"rules": {"bufferMinutes": 15}})
    assert resolved["timing"]["bufferMinutes"] == 15
    assert resolved["timing"]["confirmation"] == "instant"
    assert resolved["timing"]["approvalWindowHours"] == 48
    # `rules` stays the five-key v1 shape so an old reader sees nothing new.
    assert set(resolved["rules"]) == set(_TIMING_ALIASES)


# ======================================================================
# normalize — the search <-> discovery facet alias
# ======================================================================


def test_discovery_facets_default_to_five_keys_and_search_to_three():
    resolved = normalize({})
    assert set(resolved["discovery"]["facets"]) == {
        "price",
        "distance",
        "rating",
        "availability",
        "unitKind",
    }
    assert set(resolved["search"]["facets"]) == {"price", "distance", "rating"}


def test_a_v1_search_facet_is_mirrored_into_discovery():
    resolved = normalize({"search": {"facets": {"distance": False}}})
    assert resolved["discovery"]["facets"]["distance"] is False
    assert resolved["search"]["facets"]["distance"] is False


def test_a_v2_discovery_facet_is_mirrored_back_into_search():
    resolved = normalize({"discovery": {"facets": {"price": False}}})
    assert resolved["search"]["facets"]["price"] is False
    assert resolved["discovery"]["facets"]["price"] is False


def test_discovery_facets_win_over_search_facets():
    resolved = normalize(
        {"search": {"facets": {"price": True}}, "discovery": {"facets": {"price": False}}}
    )
    assert resolved["discovery"]["facets"]["price"] is False
    assert resolved["search"]["facets"]["price"] is False


def test_a_v2_only_facet_never_leaks_into_the_v1_search_shape():
    """`search.facets` keeps only the three keys a v1 client can render."""
    resolved = normalize({"discovery": {"facets": {"availability": False, "unitKind": True}}})
    assert set(resolved["search"]["facets"]) == {"price", "distance", "rating"}
    assert resolved["discovery"]["facets"]["unitKind"] is True


def test_search_and_discovery_facets_always_agree_on_the_shared_keys():
    for raw in ({}, {"search": {"facets": {"rating": False}}},
                {"discovery": {"facets": {"distance": False}}},
                json.loads(REPO_CONFIG.read_text())):
        resolved = normalize(raw)
        for key in ("price", "distance", "rating"):
            assert resolved["search"]["facets"][key] == resolved["discovery"]["facets"][key]


# ======================================================================
# normalize — tenancy.selfOnboarding
# ======================================================================


def test_self_onboarding_defaults_to_true_for_a_marketplace():
    """A marketplace onboards businesses; a single-business site does not."""
    assert normalize({})["tenancy"]["selfOnboarding"] is True
    assert normalize({"tenancy": {"mode": "multi"}})["tenancy"]["selfOnboarding"] is True


def test_self_onboarding_defaults_to_false_for_a_single_business():
    resolved = normalize({"tenancy": {"mode": "single", "providerCode": "VISTULA-4471"}})
    assert resolved["tenancy"]["selfOnboarding"] is False


@pytest.mark.parametrize("declared", [True, False])
def test_an_explicit_self_onboarding_is_never_overwritten(declared):
    resolved = normalize({"tenancy": {"mode": "single", "providerCode": "X", "selfOnboarding": declared}})
    assert resolved["tenancy"]["selfOnboarding"] is declared


# ======================================================================
# validate — reports EVERY problem at once
# ======================================================================


def test_a_valid_config_reports_nothing():
    assert validate(normalize(good())) == []


def test_validate_reports_all_problems_at_once():
    """One round-trip through the validator must list every mistake — fixing a
    pivot file one 500 at a time is exactly the failure mode v2 removes."""
    cfg = normalize(
        {
            "booking": {"unitKind": "spaceship"},
            "pricing": {"currency": "EUROS", "model": "vibes"},
            "location": {"timezone": "Mars/Olympus"},
        }
    )
    problems = validate(cfg)
    joined = "\n".join(problems)
    assert len(problems) >= 4, problems
    for path in ("booking.unitKind", "pricing.currency", "pricing.model", "location.timezone"):
        assert path in joined, (path, problems)


@pytest.mark.parametrize(
    ("patch", "path"),
    [
        ({"booking": {"unitKind": "spaceship"}}, "booking.unitKind"),
        ({"booking": {"granularity": "fortnight"}}, "booking.granularity"),
        ({"booking": {"party": {"mode": "swarm"}}}, "booking.party.mode"),
        ({"pricing": {"model": "vibes"}}, "pricing.model"),
        ({"pricing": {"rate": {"per": "fortnight"}}}, "pricing.rate.per"),
        ({"payments": {"flow": "cheque"}}, "payments.flow"),
        ({"inventory": {"mode": "hoard"}}, "inventory.mode"),
        ({"timing": {"confirmation": "eventually"}}, "timing.confirmation"),
        ({"entitlements": {"kind": "loyalty"}}, "entitlements.kind"),
        ({"discovery": {"mode": "telepathy"}}, "discovery.mode"),
        ({"tenancy": {"mode": "federated"}}, "tenancy.mode"),
    ],
)
def test_validate_rejects_a_value_outside_its_enum(patch, path):
    problems = validate(normalize(patch))
    assert any(path in problem for problem in problems), (path, problems)


def test_the_enum_frozensets_are_what_the_validator_actually_accepts():
    for unit_kind in UNIT_KINDS:
        assert validate(normalize({"booking": {"unitKind": unit_kind}})) == []
    for model in PRICING_MODELS:
        assert validate(normalize({"pricing": {"model": model}})) == []
    for per in RATE_PERIODS:
        assert validate(normalize({"pricing": {"rate": {"per": per}}})) == []


# --- location ----------------------------------------------------------


@pytest.mark.parametrize("timezone_name", ["Mars/Olympus", "", None, "GMT+2", 5])
def test_validate_rejects_a_non_iana_timezone(timezone_name):
    """`location.timezone` is what an anonymous visitor's calendar is grouped
    by, so a bogus zone silently shifts every evening slot into the next day."""
    problems = validate(normalize({"location": {"timezone": timezone_name}}))
    assert any("location.timezone" in problem for problem in problems), problems


@pytest.mark.parametrize("timezone_name", ["UTC", "Europe/Warsaw", "America/New_York"])
def test_validate_accepts_a_real_iana_timezone(timezone_name):
    assert validate(normalize({"location": {"timezone": timezone_name}})) == []


def test_validate_rejects_a_default_location_mode_not_in_modes():
    problems = validate(
        normalize({"location": {"modes": ["remote"], "default": "on_site"}})
    )
    assert any("location.default" in problem for problem in problems), problems


def test_validate_accepts_a_default_that_is_one_of_the_modes():
    assert validate(normalize({"location": {"modes": ["remote", "delivery"], "default": "delivery"}})) == []


def test_validate_rejects_an_empty_or_unknown_location_mode_list():
    assert any("location.modes" in p for p in validate(normalize({"location": {"modes": []}})))
    problems = validate(normalize({"location": {"modes": ["teleport"], "default": "teleport"}}))
    assert any("location.modes[0]" in p for p in problems), problems


# --- currency ----------------------------------------------------------


@pytest.mark.parametrize("currency", ["EUROS", "E", "", None, 978, "eur "])
def test_validate_rejects_a_currency_that_is_not_three_letters(currency):
    problems = validate(normalize({"pricing": {"currency": currency}}))
    assert any("pricing.currency" in problem for problem in problems), problems


@pytest.mark.parametrize("currency", ["EUR", "PLN", "USD"])
def test_validate_accepts_a_three_letter_currency(currency):
    assert validate(normalize({"pricing": {"currency": currency}})) == []


# --- tenancy -----------------------------------------------------------


def test_single_tenancy_without_a_provider_code_is_rejected():
    """`providerCode` is how a single-business deployment resolves its one
    business; without it every page has nothing to render."""
    problems = validate(normalize({"tenancy": {"mode": "single"}}))
    assert any("tenancy.providerCode" in problem for problem in problems), problems


def test_single_tenancy_with_a_provider_code_is_accepted():
    assert validate(normalize({"tenancy": {"mode": "single", "providerCode": "VISTULA-4471"}})) == []


def test_multi_tenancy_needs_no_provider_code():
    assert validate(normalize({"tenancy": {"mode": "multi"}})) == []


# --- capabilities vs. payments ----------------------------------------


@pytest.mark.parametrize("flow", ["prepay", "pay_on_site", "invoice_after", "split"])
def test_payments_disabled_with_a_live_payment_flow_is_rejected(flow):
    """The UI would hide a step the API still enforces — a booking nobody can
    complete."""
    problems = validate(
        normalize({"capabilities": {"payments": False}, "payments": {"flow": flow}})
    )
    assert any("capabilities.payments is false" in problem for problem in problems), problems


def test_payments_disabled_with_flow_none_is_accepted():
    assert validate(normalize({"capabilities": {"payments": False}, "payments": {"flow": "none"}})) == []


def test_payments_enabled_with_any_flow_is_accepted():
    assert validate(normalize({"capabilities": {"payments": True}, "payments": {"flow": "prepay"}})) == []


def test_a_non_boolean_capability_is_rejected():
    problems = validate(normalize({"capabilities": {"waitlist": "yes"}}))
    assert any("capabilities.waitlist" in problem for problem in problems), problems


# --- metaFields --------------------------------------------------------


def test_validate_rejects_an_unknown_meta_field_type():
    """metaFields is the no-migration extension point, so a malformed
    descriptor silently disabling validation is the worst failure mode."""
    problems = validate(
        normalize({"metaFields": {"bookings": [{"key": "note", "label": "Note", "type": "blob"}]}})
    )
    assert any("metaFields.bookings[0].type" in problem for problem in problems), problems


@pytest.mark.parametrize("ftype", sorted(META_FIELD_TYPES - {"select"}))
def test_validate_accepts_every_declared_meta_field_type(ftype):
    assert validate(
        normalize({"metaFields": {"bookings": [{"key": "k", "label": "L", "type": ftype}]}})
    ) == []


def test_string_is_accepted_as_an_alias_for_text():
    """`type: "string"` shipped in domain.config.medical.example.json and matched
    nothing in the v1 validator, so it silently validated nothing. It is now an
    explicit alias rather than a break for a config already in the repo."""
    assert META_FIELD_TYPE_ALIASES["string"] == "text"
    assert validate(
        normalize({"metaFields": {"providers": [{"key": "nip", "label": "NIP", "type": "string"}]}})
    ) == []


def test_a_select_meta_field_without_options_is_rejected():
    problems = validate(
        normalize({"metaFields": {"slots": [{"key": "room", "label": "Room", "type": "select"}]}})
    )
    assert any("options is required" in problem for problem in problems), problems


def test_a_meta_field_missing_key_or_label_is_rejected():
    problems = validate(normalize({"metaFields": {"resources": [{"type": "text"}]}}))
    joined = "\n".join(problems)
    assert "metaFields.resources[0].key" in joined
    assert "metaFields.resources[0].label" in joined


def test_meta_fields_for_an_entity_must_be_a_list():
    problems = validate(normalize({"metaFields": {"bookings": {"note": "Note"}}}))
    assert any("must be a list" in problem for problem in problems), problems


# --- numeric guards ----------------------------------------------------


@pytest.mark.parametrize(
    ("patch", "path"),
    [
        ({"timing": {"maxBookingsPerSlot": 0}}, "timing.maxBookingsPerSlot"),
        ({"timing": {"slotDurationMinutes": 0}}, "timing.slotDurationMinutes"),
        ({"timing": {"cancellationWindowHours": -1}}, "timing.cancellationWindowHours"),
        ({"timing": {"bufferMinutes": -5}}, "timing.bufferMinutes"),
        ({"timing": {"leadTimeMinutes": -1}}, "timing.leadTimeMinutes"),
        ({"pricing": {"rate": {"amountMinorUnits": -1}}}, "pricing.rate.amountMinorUnits"),
        ({"booking": {"party": {"min": 0}}}, "booking.party.min"),
        ({"tenancy": {"commission": {"rateBps": -1}}}, "tenancy.commission.rateBps"),
    ],
)
def test_validate_rejects_an_out_of_range_number(patch, path):
    problems = validate(normalize(patch))
    assert any(path in problem for problem in problems), (path, problems)


# --- timing.seasons / timing.blackouts -------------------------------------
# Each entry is reported on its own, with `timing.<list>[i]` in the message. The
# path is not cosmetic: it is how an owner-facing surface points at the row that
# is actually broken, and how `rules.surviving_overrides` decides which block to
# drop. The old pathless phrasing ("timing seasons/blackouts entry 0 needs...")
# named no block at all, so the per-service override path could not attribute it.


@pytest.mark.parametrize("key", ["seasons", "blackouts"])
@pytest.mark.parametrize(
    "window",
    [
        {},
        {"startDate": "2026-01-01"},
        {"endDate": "2026-03-01"},
        {"startDate": "", "endDate": "2026-03-01"},
        {"startDate": "2026-01-01", "endDate": ""},
        "2026-01-01/2026-03-01",
        None,
    ],
)
def test_a_malformed_timing_window_is_rejected_with_its_indexed_path(key, window):
    assert validate(normalize({"timing": {key: [window]}})) == [
        f"timing.{key}[0] needs startDate and endDate"
    ]


@pytest.mark.parametrize("key", ["seasons", "blackouts"])
def test_a_well_formed_timing_window_validates_clean(key):
    assert validate(
        normalize({"timing": {key: [{"startDate": "2026-01-01", "endDate": "2026-03-01"}]}})
    ) == []


def test_the_two_timing_window_lists_are_enumerated_independently():
    good = {"startDate": "2026-01-01", "endDate": "2026-03-01"}
    problems = validate(
        normalize({"timing": {"seasons": [good, {}], "blackouts": [{}, good, {"startDate": "x"}]}})
    )
    assert set(problems) == {
        "timing.seasons[1] needs startDate and endDate",
        "timing.blackouts[0] needs startDate and endDate",
        "timing.blackouts[2] needs startDate and endDate",
    }


def test_a_config_file_with_a_malformed_window_cannot_load(tmp_path):
    config_file = tmp_path / "domain.config.json"
    config_file.write_text(
        json.dumps({"domain": "test", "timing": {"blackouts": [{"startDate": "2026-12-24"}]}})
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(config_file)
    assert "timing.blackouts[0]" in str(excinfo.value)


def test_a_min_duration_above_the_max_is_rejected():
    problems = validate(normalize({"booking": {"duration": {"minUnits": 5, "maxUnits": 2}}}))
    assert any("minUnits must not exceed" in problem for problem in problems), problems


def test_an_empty_term_or_copy_string_is_rejected():
    problems = validate(normalize({"terms": {"booking": ""}, "copy": {"confirmTitle": ""}}))
    joined = "\n".join(problems)
    assert "terms.booking" in joined
    assert "copy.confirmTitle" in joined


# ======================================================================
# validate — the list-of-descriptor blocks
# ======================================================================
#
# `pricing.fees`, `pricing.deposit`, `payments.schedule`, `booking.options`,
# `recurrence.patterns` and `entitlements.plans` are lists (or small objects) of
# descriptors keyed by a `kind`/`type` string. An unrecognised value used to make
# the entry evaluate to *nothing* at runtime — a fee that never charges, an
# option that never renders — which is the exact silent-failure mode this
# validator exists to prevent. Every one of them is now checked at load.


def _fee(**overrides) -> dict:
    fee = {"key": "clean", "label": "Cleaning", "kind": "flat", "amountMinorUnits": 1500}
    fee.update(overrides)
    return fee


def _fee_problems(fee) -> list[str]:
    return validate(normalize({"pricing": {"fees": [fee]}}))


# --- pricing.fees ------------------------------------------------------


def test_fee_kinds_is_the_vocabulary_the_validator_documents():
    assert FEE_KINDS == {"flat", "percent", "distanceBand"}


def test_a_well_formed_fee_of_every_kind_is_accepted():
    for fee in (
        _fee(kind="flat", amountMinorUnits=0),
        _fee(kind="percent", rateBps=1250),
        _fee(kind="distanceBand", bands=[{"maxKm": None, "feeMinorUnits": 500}]),
    ):
        assert _fee_problems(fee) == [], fee


def test_a_fee_with_no_kind_defaults_to_flat_and_is_accepted():
    assert _fee_problems({"key": "clean", "label": "Cleaning", "amountMinorUnits": 100}) == []


@pytest.mark.parametrize("kind", ["percentage", "PERCENT", "distance_band", "", None, 5])
def test_an_unknown_fee_kind_is_a_load_error(kind):
    """`kind: "percentage"` is the motivating typo: it matched nothing in
    `pricing._fee_amount`, so the fee silently vanished from every quote (see
    `test_pricing.test_a_typo_fee_kind_contributes_nothing_...`)."""
    problems = _fee_problems(_fee(kind=kind))
    assert any("pricing.fees[0].kind" in problem for problem in problems), (kind, problems)


def test_a_percent_fee_without_a_rate_is_rejected():
    problems = _fee_problems({"key": "svc", "label": "Service", "kind": "percent"})
    assert any("pricing.fees[0].rateBps" in problem for problem in problems), problems


def test_a_negative_percent_rate_is_rejected():
    problems = _fee_problems(_fee(kind="percent", rateBps=-1))
    assert any("pricing.fees[0].rateBps" in problem for problem in problems), problems


_MISSING = object()


@pytest.mark.parametrize("bands", [_MISSING, None, [], "10km", 0, {"maxKm": 5}])
def test_a_distance_band_fee_without_a_usable_band_list_is_rejected(bands):
    """`bands` must be a non-empty LIST. A truthy non-list ("10km", an object)
    used to slip through the emptiness check and then price as 0 on every
    booking, because `pricing._fee_amount` iterates `fee.get("bands") or []`."""
    fee = {"key": "travel", "label": "Travel", "kind": "distanceBand"}
    if bands is not _MISSING:
        fee["bands"] = bands
    problems = _fee_problems(fee)
    assert (
        "pricing.fees[0].bands must be a non-empty list for a distanceBand fee" in problems
    ), (bands, problems)


@pytest.mark.parametrize(
    ("band", "path"),
    [
        ({"maxKm": 5}, "pricing.fees[0].bands[0].feeMinorUnits"),          # no fee
        ({"maxKm": 5, "feeMinorUnits": None}, "pricing.fees[0].bands[0].feeMinorUnits"),
        ({"maxKm": 5, "feeMinorUnits": -1}, "pricing.fees[0].bands[0].feeMinorUnits"),
        ({"maxKm": 5, "feeMinorUnits": "500"}, "pricing.fees[0].bands[0].feeMinorUnits"),
        ({"maxKm": -3, "feeMinorUnits": 500}, "pricing.fees[0].bands[0].maxKm"),
        ({"maxKm": "5", "feeMinorUnits": 500}, "pricing.fees[0].bands[0].maxKm"),
        ("nope", "pricing.fees[0].bands[0] must be an object"),
        (None, "pricing.fees[0].bands[0] must be an object"),
        (7, "pricing.fees[0].bands[0] must be an object"),
        (["5", 500], "pricing.fees[0].bands[0] must be an object"),
    ],
)
def test_a_malformed_distance_band_entry_is_rejected(band, path):
    problems = _fee_problems(_fee(kind="distanceBand", bands=[band]))
    assert any(path in problem for problem in problems), (band, problems)


def test_every_bad_band_in_the_list_is_reported_with_its_index():
    problems = _fee_problems(
        _fee(
            kind="distanceBand",
            bands=[
                {"maxKm": 5, "feeMinorUnits": 0},      # fine
                {"maxKm": 10},                          # missing feeMinorUnits
                "nope",                                 # not an object
            ],
        )
    )
    joined = "\n".join(problems)
    assert "pricing.fees[0].bands[1].feeMinorUnits" in joined, problems
    assert "pricing.fees[0].bands[2] must be an object" in joined, problems
    assert "pricing.fees[0].bands[0]" not in joined, problems


def test_a_multi_band_distance_fee_with_a_null_catch_all_top_band_is_accepted():
    """`maxKm: null` is the deliberate open-ended top band, so a valid ladder
    ends with one — `_int(..., allow_none=True)` on maxKm is what allows it."""
    fee = _fee(
        kind="distanceBand",
        bands=[
            {"maxKm": 5, "feeMinorUnits": 0},
            {"maxKm": 10, "feeMinorUnits": 500},
            {"maxKm": None, "feeMinorUnits": 1500},
        ],
    )
    assert _fee_problems(fee) == []


def test_a_validated_multi_band_fee_prices_a_distance_beyond_every_numbered_band():
    """Validation and the pricer agree: the same fee that loads clean charges the
    `maxKm: null` catch-all for a distance no numbered band covers."""
    from app.pricing import quote

    fee = _fee(
        key="travel",
        label="Travel",
        kind="distanceBand",
        bands=[
            {"maxKm": 5, "feeMinorUnits": 0},
            {"maxKm": 10, "feeMinorUnits": 500},
            {"maxKm": None, "feeMinorUnits": 1500},
        ],
    )
    raw = {"pricing": {"rate": {"per": "booking", "amountMinorUnits": 3000}, "fees": [fee]}}
    assert validate(normalize(raw)) == []

    block = normalize(raw)["pricing"]
    result = quote(block, {"party_size": 1, "distance_km": 400})
    assert result["amountMinorUnits"] == 4500          # 3000 + the catch-all band
    assert any(line["key"] == "travel" and line["amountMinorUnits"] == 1500
               for line in result["breakdown"]), result["breakdown"]
    # ...and a distance inside a numbered band still takes that band.
    assert quote(block, {"party_size": 1, "distance_km": 7})["amountMinorUnits"] == 3500


def test_a_flat_fee_without_an_amount_is_rejected():
    problems = _fee_problems({"key": "clean", "label": "Cleaning", "kind": "flat"})
    assert any("pricing.fees[0].amountMinorUnits" in problem for problem in problems), problems


def test_a_negative_flat_fee_amount_is_rejected():
    problems = _fee_problems(_fee(amountMinorUnits=-500))
    assert any("pricing.fees[0].amountMinorUnits" in problem for problem in problems), problems


@pytest.mark.parametrize("entry", ["nonsense", None, 7, ["clean", 100]])
def test_a_non_object_fee_entry_is_rejected(entry):
    problems = _fee_problems(entry)
    assert any("pricing.fees[0] must be an object" in problem for problem in problems), problems


def test_every_bad_fee_in_the_list_is_reported_with_its_index():
    problems = validate(
        normalize(
            {
                "pricing": {
                    "fees": [
                        _fee(),                                   # fine
                        _fee(kind="percentage"),                  # bad kind
                        {"key": "svc", "kind": "percent"},        # missing rateBps
                    ]
                }
            }
        )
    )
    joined = "\n".join(problems)
    assert "pricing.fees[1].kind" in joined, problems
    assert "pricing.fees[2].rateBps" in joined, problems
    assert "pricing.fees[0]" not in joined, problems


# --- pricing.deposit ---------------------------------------------------


def test_deposit_kinds_is_the_vocabulary_the_validator_documents():
    assert DEPOSIT_KINDS == {"percent", "flat"}


@pytest.mark.parametrize("kind", sorted(DEPOSIT_KINDS))
def test_every_deposit_kind_is_accepted(kind):
    assert validate(normalize({"pricing": {"deposit": {"enabled": True, "kind": kind,
                                                       "value": 2500}}})) == []


@pytest.mark.parametrize("kind", ["fraction", "percentage", "", None])
def test_an_unknown_deposit_kind_is_rejected(kind):
    problems = validate(normalize({"pricing": {"deposit": {"kind": kind, "value": 10}}}))
    assert any("pricing.deposit.kind" in problem for problem in problems), (kind, problems)


# --- payments.schedule -------------------------------------------------


def test_a_well_formed_payment_schedule_is_accepted():
    schedule = [
        {"key": "deposit", "kind": "percent", "value": 2500},
        {"key": "balance", "kind": "flat", "value": 0},
    ]
    assert validate(normalize({"payments": {"schedule": schedule}})) == []


def test_a_payment_step_with_no_kind_defaults_to_percent():
    assert validate(normalize({"payments": {"schedule": [{"key": "deposit", "value": 50}]}})) == []


@pytest.mark.parametrize(
    ("step", "path"),
    [
        ({"kind": "percent", "value": 10}, "payments.schedule[0].key"),
        ({"key": "", "kind": "percent", "value": 10}, "payments.schedule[0].key"),
        ({"key": "balance", "kind": "instalment", "value": 10}, "payments.schedule[0].kind"),
        ({"key": "balance", "kind": "flat", "value": -1}, "payments.schedule[0].value"),
        ({"key": "balance", "kind": "flat"}, "payments.schedule[0].value"),
        ("nonsense", "payments.schedule[0] must be an object"),
        (None, "payments.schedule[0] must be an object"),
    ],
)
def test_a_malformed_payment_schedule_step_is_rejected(step, path):
    problems = validate(normalize({"payments": {"schedule": [step]}}))
    assert any(path in problem for problem in problems), (step, problems)


# --- booking.options ---------------------------------------------------


def test_option_types_is_the_vocabulary_the_validator_documents():
    assert OPTION_TYPES == {"boolean", "select"}


def test_a_well_formed_option_of_every_type_is_accepted():
    options = [
        {"key": "insurance", "label": "Insurance", "type": "boolean"},
        {"key": "seat", "label": "Seat", "type": "select", "choices": ["aisle", "window"]},
    ]
    assert validate(normalize({"booking": {"options": options}})) == []


def test_an_option_with_no_type_defaults_to_boolean():
    assert validate(normalize({"booking": {"options": [{"key": "gift", "label": "Gift"}]}})) == []


@pytest.mark.parametrize(
    ("option", "path"),
    [
        ({"label": "Insurance", "type": "boolean"}, "booking.options[0].key"),
        ({"key": "", "type": "boolean"}, "booking.options[0].key"),
        ({"key": "seat", "type": "dropdown"}, "booking.options[0].type"),
        ({"key": "seat", "type": "select"}, "booking.options[0].choices"),
        ({"key": "seat", "type": "select", "choices": []}, "booking.options[0].choices"),
        ("nonsense", "booking.options[0] must be an object"),
    ],
)
def test_a_malformed_booking_option_is_rejected(option, path):
    problems = validate(normalize({"booking": {"options": [option]}}))
    assert any(path in problem for problem in problems), (option, problems)


# --- recurrence.patterns / entitlements.plans --------------------------


def test_recurrence_patterns_is_the_vocabulary_the_validator_documents():
    assert RECURRENCE_PATTERNS == {"weekly", "biweekly", "monthly"}


@pytest.mark.parametrize("pattern", sorted(RECURRENCE_PATTERNS))
def test_every_recurrence_pattern_is_accepted(pattern):
    assert validate(normalize({"recurrence": {"enabled": True, "patterns": [pattern]}})) == []


@pytest.mark.parametrize("pattern", ["fortnightly", "daily", "", None, 7])
def test_an_unknown_recurrence_pattern_is_rejected(pattern):
    problems = validate(normalize({"recurrence": {"patterns": [pattern]}}))
    assert any("recurrence.patterns[0]" in problem for problem in problems), (pattern, problems)


# --- unhashable values in an enum position ----------------------------
#
# `_enum` type-guards before the membership test now, so a hand-edited config
# that drops an object/array where a scalar belongs is a *listed* validation
# error. Previously `value not in frozenset` raised TypeError, which escaped
# ConfigError entirely and made POST /config/reload a 500 instead of the
# documented 422.


@pytest.mark.parametrize("pattern", [{"every": "week"}, ["weekly"], {}, [], {"weekly": True}])
def test_an_unhashable_value_in_an_enum_position_is_a_load_error(pattern):
    problems = validate(normalize({"recurrence": {"patterns": [pattern]}}))
    assert any("recurrence.patterns[0]" in problem for problem in problems), (pattern, problems)


@pytest.mark.parametrize(
    ("raw", "path"),
    [
        ({"booking": {"unitKind": {"kind": "staff"}}}, "booking.unitKind"),
        ({"booking": {"unitKind": ["staff"]}}, "booking.unitKind"),
        ({"pricing": {"rate": {"per": ["hour"]}}}, "pricing.rate.per"),
        ({"pricing": {"rate": {"per": {"unit": "hour"}}}}, "pricing.rate.per"),
        ({"pricing": {"model": {"kind": "fixed"}}}, "pricing.model"),
        ({"booking": {"granularity": ["hour"]}}, "booking.granularity"),
        ({"payments": {"flow": {"mode": "none"}}}, "payments.flow"),
        ({"location": {"modes": [["onsite"]]}}, "location.modes[0]"),
        ({"tenancy": {"mode": {"kind": "multi"}, "providerCode": "X"}}, "tenancy.mode"),
    ],
)
def test_an_unhashable_value_in_a_scalar_enum_position_is_a_load_error(raw, path):
    """Not just the list-valued enums: every `_enum` call site is guarded, so a
    dict/list dropped on a scalar key is reported by path instead of raising."""
    problems = validate(normalize(raw))
    assert any(path in problem for problem in problems), (raw, problems)


def test_an_unhashable_enum_value_is_reported_alongside_every_other_problem():
    """The guard must not short-circuit the pass — one edit session, one list."""
    problems = validate(
        normalize(
            {
                "recurrence": {"patterns": [{"every": "week"}]},
                "booking": {"unitKind": ["staff"]},
                "pricing": {"rate": {"per": {"unit": "hour"}}, "currency": "EUROS"},
            }
        )
    )
    joined = "\n".join(problems)
    for path in ("recurrence.patterns[0]", "booking.unitKind",
                 "pricing.rate.per", "pricing.currency"):
        assert path in joined, (path, problems)


@pytest.mark.parametrize(
    ("raw", "path"),
    [
        ({"recurrence": {"patterns": [{"every": "week"}]}}, "recurrence.patterns[0]"),
        ({"booking": {"unitKind": {"kind": "staff"}}}, "booking.unitKind"),
        ({"pricing": {"rate": {"per": ["hour"]}}}, "pricing.rate.per"),
    ],
)
def test_load_config_raises_config_error_not_type_error_for_an_unhashable_enum(
    tmp_path, raw, path
):
    """The load path is what the endpoint sits on: a TypeError here would be an
    unhandled 500, so it has to arrive as ConfigError naming the key."""
    config_file = tmp_path / "domain.config.json"
    config_file.write_text(json.dumps({"domain": "test", **raw}))

    with pytest.raises(ConfigError) as excinfo:
        load_config(config_file)
    assert path in str(excinfo.value), str(excinfo.value)


def test_a_well_formed_entitlement_plan_is_accepted():
    plans = [{"key": "gold", "label": "Gold", "credits": 10}]
    assert validate(normalize({"entitlements": {"enabled": True, "kind": "credits",
                                                "plans": plans}})) == []


@pytest.mark.parametrize("plan", [{}, {"label": "Gold"}, {"key": ""}, "gold", None, 3])
def test_a_plan_that_is_not_an_object_with_a_key_is_rejected(plan):
    problems = validate(normalize({"entitlements": {"plans": [plan]}}))
    assert any("entitlements.plans[0]" in problem for problem in problems), (plan, problems)


# --- booking.party min/max --------------------------------------------


def test_a_min_party_above_the_max_is_rejected():
    """Mirrors the duration min/max check: a range nothing can satisfy makes
    every booking fail at request time instead of at load."""
    problems = validate(normalize({"booking": {"party": {"min": 4, "max": 2}}}))
    assert any("booking.party.min must not exceed" in problem for problem in problems), problems


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 1), (2, 2), (1, 12), (4, None)])
def test_a_satisfiable_party_range_is_accepted(minimum, maximum):
    assert validate(normalize({"booking": {"party": {"min": minimum, "max": maximum}}})) == []


def test_the_descriptor_checks_all_report_together():
    """One pass, every problem — a hand-edited pivot file gets fixed once, not
    one failed request at a time."""
    problems = validate(
        normalize(
            {
                "pricing": {"fees": [_fee(kind="percentage")], "deposit": {"kind": "fraction"}},
                "payments": {"schedule": [{"kind": "instalment", "value": -5}]},
                "booking": {"options": [{"key": "seat", "type": "select"}],
                            "party": {"min": 9, "max": 2}},
                "recurrence": {"patterns": ["fortnightly"]},
                "entitlements": {"plans": ["gold"]},
            }
        )
    )
    joined = "\n".join(problems)
    for path in (
        "pricing.fees[0].kind",
        "pricing.deposit.kind",
        "payments.schedule[0].key",
        "payments.schedule[0].kind",
        "payments.schedule[0].value",
        "booking.options[0].choices",
        "booking.party.min",
        "recurrence.patterns[0]",
        "entitlements.plans[0]",
    ):
        assert path in joined, (path, problems)


# ======================================================================
# declared-but-unenforced inventory
# ======================================================================
#
# Some keys are in DEFAULTS but do not GATE anything yet: each would need
# machinery this repo does not have (a cross-booking daily total, a payments
# layer, a scheduled job). The point of this section is NOT to assert behaviour
# they lack — it is to pin the *list*, so a dead key cannot be added quietly and
# so an enforced key can't be mistaken for one of them.
#
# The list used to be one bucket, checked with "no engine module reads this
# key". That conflated two different properties:
#
#   ENFORCED — the engine gates behaviour on the key (refuses, prices, expires).
#   READ     — the engine merely reads it to put it on the wire.
#
# A display-only key is READ but not ENFORCED, so the old check failed the
# moment `timing.approvalWindowHours` was surfaced through `serialize_service`
# — reporting a *feature* as a regression. The invariant that still has teeth is
# the narrower one, so it is split in two here:
#
#   INERT          — neither enforced nor surfaced -> must have NO reader at all.
#   SURFACED_ONLY  — read for display -> must have a reader, that reader must be
#                    the declared wire path and nothing else, and the key must
#                    still change no behaviour (pinned as real assertions below).
#
# Deleting the check instead would have thrown away the only thing standing
# between `backend/CLAUDE.md`'s "Declared but NOT enforced" table and v1's
# cautionary tale of config that looks live and does nothing.

BACKEND_APP = REPO_ROOT / "backend" / "app"
BACKEND_DOC = REPO_ROOT / "backend" / "CLAUDE.md"
CHECK_PIVOTS = REPO_ROOT / "scripts" / "check_pivots.py"

# Neither enforced NOR surfaced: no engine module may mention these at all.
INERT = {
    "pricing.caps.perDayMinorUnits": "perDayMinorUnits",
    "payments.noShowFee": "noShowFee",
}

# Read for DISPLAY only. Value is (leaf key, the exact module set allowed to
# read it) — the module set is what makes this non-vacuous: wiring one of these
# into a gate means editing `bookings.py` / `pricing.py` / `rules.py`'s rule
# dispatch, which grows the set and fails the test.
SURFACED_ONLY = {
    # serialize_service -> Service.approvalWindowHours ("a reply within N
    # hours"). Nothing expires a stale pending request.
    "timing.approvalWindowHours": ("approvalWindowHours", {"serialize.py"}),
    # rules.payment_state -> Booking.payment.payer (address the invoice to an
    # estate/insurer/employer). It changes nothing about what is owed.
    "payments.payer": ("payer", {"rules.py"}),
}

UNENFORCED = {**INERT, **{path: key for path, (key, _) in SURFACED_ONLY.items()}}

# Controls: same shape, but these two ARE read by engine code. They prove the
# source scan below can actually see enforcement.
ENFORCED_CONTROLS = {
    "timing.leadTimeMinutes": "leadTimeMinutes",
    "pricing.caps.perBookingMinorUnits": "perBookingMinorUnits",
}


def _dig(tree: dict, path: str):
    node = tree
    for part in path.split("."):
        assert isinstance(node, dict) and part in node, f"{path} is not declared in DEFAULTS"
        node = node[part]
    return node


# Modules that declare the config shape rather than act on it. Both name every
# key by construction, so a mention in either is evidence of nothing —
# `config_schema.py` declares them in DEFAULTS, `config_models.py` as pydantic
# fields. Excluding them is what keeps this scan a test of *enforcement*.
_SHAPE_DECLARING_MODULES = {"config_schema.py", "config_models.py"}


def _modules_reading(key: str) -> set[str]:
    """Backend modules whose *code* (comments stripped) mentions `key`.
    The shape-declaring modules are excluded: declaring a key is not
    enforcing it."""
    found = set()
    for path in sorted(BACKEND_APP.rglob("*.py")):
        if path.name in _SHAPE_DECLARING_MODULES:
            continue
        for line in path.read_text().splitlines():
            if key in line.split("#", 1)[0]:
                found.add(path.name)
    return found


@pytest.mark.parametrize("path", sorted(UNENFORCED))
def test_an_unenforced_key_is_still_declared_in_defaults(path):
    _dig(DEFAULTS, path)  # readable + overridable per service even while inert


@pytest.mark.parametrize(("path", "key"), sorted(INERT.items()))
def test_an_inert_key_is_read_by_no_engine_code(path, key):
    """The surviving half of the original invariant: a key that is neither
    enforced nor surfaced must have no reader anywhere in `backend/app`.

    If this fails the key was wired up — good news, but move it to
    SURFACED_ONLY (with its wire path) or out of the inventory entirely, and
    write the behaviour tests that now exist to be written."""
    assert _modules_reading(key) == set(), path


@pytest.mark.parametrize(("path", "key", "readers"),
                         sorted((p, k, r) for p, (k, r) in SURFACED_ONLY.items()))
def test_a_surfaced_key_is_read_only_where_it_reaches_the_wire(path, key, readers):
    """A display-only key must be read (otherwise it is inert and belongs in
    INERT), and read ONLY by the module that puts it on the wire. Equality, not
    a subset: a new reader in `bookings.py`/`pricing.py`/`availability.py` is
    exactly the "it started gating something" event this section exists to
    catch, and it must be re-classified rather than absorbed."""
    assert _modules_reading(key) == readers, path


@pytest.mark.parametrize(("path", "key"), sorted(ENFORCED_CONTROLS.items()))
def test_the_control_keys_prove_the_scan_can_see_enforcement(path, key):
    assert _modules_reading(key), path


@pytest.mark.parametrize(("path", "key"), sorted(INERT.items()))
def test_an_inert_key_carries_a_comment_saying_so(path, key):
    """DEFAULTS is the only place an operator reads about an inert key, so it
    must say so where it is declared. (A SURFACED_ONLY key is visible on the
    wire, so its promise is documented in the table checked below instead.)"""
    lines = (BACKEND_APP / "config_schema.py").read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if f'"{key}"' in line)
    context = "\n".join(lines[max(0, index - 5):index]).lower()
    assert "enforc" in context, (path, context)


# --- the promise the repo makes about itself, in the two places it makes it --
#
# `backend/CLAUDE.md`'s "Declared but NOT enforced" table and
# `scripts/check_pivots.py`'s ENFORCED/DECLARED_ONLY maps are the human-readable
# half of this inventory. They are only worth keeping if they agree with the
# code, so the classification above is cross-checked against both.


def _doc_table_row(path: str) -> str:
    """The `backend/CLAUDE.md` row documenting `path`, lowercased."""
    for line in BACKEND_DOC.read_text().splitlines():
        if line.startswith("|") and f"`{path}`" in line.split("|")[1]:
            return line.lower()
    return ""


@pytest.mark.parametrize("path", sorted(UNENFORCED))
def test_every_unenforced_key_is_listed_in_the_backend_doc_table(path):
    assert _doc_table_row(path), f"{path} is missing from backend/CLAUDE.md's table"


@pytest.mark.parametrize("path", sorted(SURFACED_ONLY))
def test_the_doc_table_says_a_surfaced_key_is_surfaced_but_not_enforced(path):
    """Both halves have to be stated: a reader skimming the table must learn
    that the key DOES reach the UI (so they don't wire it up twice) and that it
    still enforces nothing (so they don't trust it as a gate)."""
    row = _doc_table_row(path)
    assert "surfaced" in row, (path, row)
    assert "not enforced" in row, (path, row)


@pytest.mark.parametrize("path", sorted(INERT))
def test_check_pivots_lists_an_inert_key_as_declared_only(path):
    """`check_pivots.py` fails on any DEFAULTS leaf in neither map, so the two
    maps are the machine-readable version of the same promise. An inert key
    belongs in DECLARED_ONLY ("nothing reads it yet") and must not be claimed
    as enforced."""
    enforced, declared_only = _check_pivots_maps()
    assert path in declared_only, path
    assert path not in enforced, path


@pytest.mark.parametrize("path", sorted(SURFACED_ONLY))
def test_check_pivots_lists_a_surfaced_key_as_read_but_not_gated(path):
    """A surfaced key has a real reader, so it is no longer DECLARED_ONLY
    ("nothing reads it yet") — but its ENFORCED note must admit it is only
    displayed, or the map would over-claim exactly what this section guards."""
    enforced, declared_only = _check_pivots_maps()
    assert path in enforced, path
    assert path not in declared_only, path
    note = enforced[path].lower()
    assert "display" in note or "not gated" in note or "expires nothing" in note, (path, note)


def _check_pivots_maps() -> tuple[dict, dict]:
    """ENFORCED / DECLARED_ONLY out of `scripts/check_pivots.py`, read as source
    rather than imported: the script pulls in `app.pricing` and shells out over
    100 pivot files, and this suite only needs its two literal maps."""
    module: dict = {}
    tree = ast.parse(CHECK_PIVOTS.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("ENFORCED", "DECLARED_ONLY"):
                module[name] = ast.literal_eval(node.value)
    assert set(module) == {"ENFORCED", "DECLARED_ONLY"}, sorted(module)
    return module["ENFORCED"], module["DECLARED_ONLY"]


# --- and the behaviour: surfaced means surfaced, not enforced ---------------


def test_the_approval_window_reaches_the_wire_and_gates_nothing():
    """`timing.approvalWindowHours` on `Service.approvalWindowHours`, and two
    configs differing ONLY in that number serialize identically apart from it —
    the mechanical statement of "display only"."""
    from app.serialize import serialize_service

    row = {"id": "s", "provider_id": "p", "name": "N", "metadata": {}}
    a = serialize_service({**row, "metadata": {"timing": {"approvalWindowHours": 4}}})
    b = serialize_service({**row, "metadata": {"timing": {"approvalWindowHours": 720}}})
    assert (a["approvalWindowHours"], b["approvalWindowHours"]) == (4, 720)
    assert {k: v for k, v in a.items() if k != "approvalWindowHours"} == {
        k: v for k, v in b.items() if k != "approvalWindowHours"
    }


@pytest.mark.parametrize("payer", sorted(PAYERS))
def test_the_payer_reaches_the_wire_and_changes_no_money(payer):
    """`payments.payer` on `Booking.payment.payer`. Who is billed must not move
    a single amount or the payment state — if it ever does, it has become an
    enforced key and needs its own behaviour tests."""
    from app.rules import payment_state

    md = {"price_minor_units": 5000, "deposit_minor_units": 1000, "currency": "EUR"}
    svc = {"metadata": {"payments": {"flow": "prepay", "payer": payer}}}
    state = payment_state(md, svc, "confirmed")
    baseline = payment_state(md, {"metadata": {"payments": {"flow": "prepay"}}}, "confirmed")
    assert state["payer"] == payer
    assert {k: v for k, v in state.items() if k != "payer"} == {
        k: v for k, v in baseline.items() if k != "payer"
    }


# ======================================================================
# the three money paths pricing._int would silently coerce (regression)
# ======================================================================


def test_junk_in_the_three_pricing_money_paths_is_listed():
    """`pricing._int` coerces junk to 0 at quote time, so an unvalidated cap of
    "free" would zero every price (and a junk deposit/secondary rate would bill
    0) instead of failing at the edit. All three are reported in one pass."""
    cfg = normalize({"pricing": {
        "caps": {"perBookingMinorUnits": "free"},
        "deposit": {"enabled": True, "kind": "flat", "value": "free"},
        "secondaryRate": {"per": "week", "amountMinorUnits": "free"},
    }})
    problems = validate(cfg)
    for path in (
        "pricing.caps.perBookingMinorUnits",
        "pricing.deposit.value",
        "pricing.secondaryRate.amountMinorUnits",
    ):
        assert any(p.startswith(path) for p in problems), (path, problems)
