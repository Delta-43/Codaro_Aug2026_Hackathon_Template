# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for `app.config_models`, the Pydantic mirror of the v2 config tree.

Pure dict/model work: no Supabase, no FastAPI, no fixtures.

`config_models` is the new single source of truth for the config *shape*
(`scripts/gen_config_schema.py` publishes a JSON Schema from it, and the frontend
generates its TypeScript from that). It is **generation-only for now**,
`config_schema.validate()` is still the production validator, so nothing in the
running app would notice if the models drifted from `config_schema.DEFAULTS`.
These tests are what notices:

* **the golden test**: `config_dump() == config_schema.DEFAULTS`, reported as the
  first differing dotted path so a drift names itself;
* **enum agreement**: every `Literal` alias covers exactly the matching
  frozenset in `config_schema`, one test id per enum;
* **every shipped config validates**: `domain.config.json` (a model too
  narrow for a real pivot would publish a schema that rejects the repo's own
  data);
* **strictness holds**: the models reject what `config_schema._int`/`_bool`
  reject. Lax coercion (`"30"` as an int, `1` as a bool) would silently widen the
  published schema in a way the golden test cannot see, because defaults are
  well-typed;
* **no import warnings**: the module is written to avoid pydantic's
  "field shadows parent attribute" `UserWarning` on `copy` (hence `copy_`, aliased).
"""

from __future__ import annotations

import copy
import importlib
import json
import typing
import warnings
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app import config_models, config_schema
from app.config_models import DomainConfig, config_dump

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_CONFIG = REPO_ROOT / "domain.config.json"


SHIPPED_CONFIGS = [REPO_CONFIG]

# Keys a shipped config declares that `config_schema.DEFAULTS` does not, so the
# models (blocks are `extra="ignore"`, matching `check_shape`) drop them on a
# round trip. `inventory.seatMap` is deliberate: `scripts/check_pivots.py` lists
# it as "positional inventory (E3, deferred)" and no reader exists. A NEW entry
# appearing here means someone put a key in a pivot that neither DEFAULTS nor the
# models declare, so `GET /config` serves it but the generated schema/TS hides it.
UNDECLARED_IN_DEFAULTS = {"inventory.seatMap"}

# (Literal alias in config_models, frozenset in config_schema).
ENUM_PAIRS = (
    ("UnitKind", "UNIT_KINDS"),
    ("Granularity", "GRANULARITIES"),
    ("DurationMode", "DURATION_MODES"),
    ("PartyMode", "PARTY_MODES"),
    ("PricingModel", "PRICING_MODELS"),
    ("RatePeriod", "RATE_PERIODS"),
    ("InventoryMode", "INVENTORY_MODES"),
    ("LocationMode", "LOCATION_MODES"),
    ("PrereqKind", "PREREQ_KINDS"),
    ("PrereqTarget", "PREREQ_TARGETS"),
    ("ConfirmationMode", "CONFIRMATION_MODES"),
    ("PaymentFlow", "PAYMENT_FLOWS"),
    ("Payer", "PAYERS"),
    ("BillingCycle", "BILLING_CYCLES"),
    ("EntitlementKind", "ENTITLEMENT_KINDS"),
    ("DiscoveryMode", "DISCOVERY_MODES"),
    ("TenancyMode", "TENANCY_MODES"),
    # `config_schema.META_FIELD_TYPES` does NOT contain "string": that is a
    # separate alias (`META_FIELD_TYPE_ALIASES`), expressed on the model as
    # `MetaFieldType | Literal["string"]` on `MetaField.type`. So the enum itself
    # is compared against META_FIELD_TYPES alone.
    ("MetaFieldType", "META_FIELD_TYPES"),
    ("FeeKind", "FEE_KINDS"),
    ("DepositKind", "DEPOSIT_KINDS"),
    ("OptionType", "OPTION_TYPES"),
    ("RecurrencePattern", "RECURRENCE_PATTERNS"),
)


def _lost_or_rewritten(source: Any, dumped: Any, path: str = "") -> list[str]:
    """Every place `dumped` fails to reproduce `source`, as dotted paths.

    Directional on purpose: the models materialise their optional fields, so a
    dump legitimately carries `"bands": null` for a flat fee that never mentioned
    `bands`. That is the shape the generated JSON Schema/TS declares, not a
    rewrite. An added key with a **non-null** value would be the models inventing
    a default the engine does not have, and is reported.
    """
    where = path or "<root>"

    if isinstance(source, dict):
        if not isinstance(dumped, dict):
            return [f"{where}: object became {type(dumped).__name__}"]
        problems: list[str] = []
        for key, value in source.items():
            child = f"{path}.{key}" if path else key
            if key not in dumped:
                problems.append(f"{child}: dropped by the models (was {value!r})")
            else:
                problems.extend(_lost_or_rewritten(value, dumped[key], child))
        for key, value in dumped.items():
            child = f"{path}.{key}" if path else key
            if key not in source and value is not None:
                problems.append(f"{child}: invented by the models ({value!r})")
        return problems

    if isinstance(source, list):
        if not isinstance(dumped, list):
            return [f"{where}: list became {type(dumped).__name__}"]
        if len(source) != len(dumped):
            return [f"{where}: length {len(source)} != {len(dumped)}"]
        problems = []
        for index, (a, b) in enumerate(zip(source, dumped)):
            problems.extend(_lost_or_rewritten(a, b, f"{path}[{index}]"))
        return problems

    return _differences(dumped, source, path)


def _differences(left: Any, right: Any, path: str = "") -> list[str]:
    """Every leaf where `left` and `right` disagree, as dotted paths.

    A plain `==` on two ~20-block dicts prints an unreadable wall of JSON; this
    walks them so the assertion message names the key that drifted.
    """
    where = path or "<root>"

    if isinstance(left, dict) and isinstance(right, dict):
        problems: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else key
            if key not in left:
                problems.append(f"{child}: missing from config_dump(), DEFAULTS has {right[key]!r}")
            elif key not in right:
                problems.append(f"{child}: extra in config_dump() ({left[key]!r}), not in DEFAULTS")
            else:
                problems.extend(_differences(left[key], right[key], child))
        return problems

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{where}: length {len(left)} != {len(right)}"]
        problems = []
        for index, (a, b) in enumerate(zip(left, right)):
            problems.extend(_differences(a, b, f"{path}[{index}]"))
        return problems

    # bool is an int subclass; keep True vs 1 a difference.
    if isinstance(left, bool) != isinstance(right, bool):
        return [f"{where}: {left!r} ({type(left).__name__}) != {right!r} ({type(right).__name__})"]
    if type(left) is not type(right) and not (
        isinstance(left, (int, float)) and isinstance(right, (int, float))
    ):
        return [f"{where}: {left!r} ({type(left).__name__}) != {right!r} ({type(right).__name__})"]
    if left != right:
        return [f"{where}: {left!r} != {right!r}"]
    return []


# -- 1. the golden test --------------------------------------------------------


def test_default_model_dump_equals_config_schema_defaults():
    """THE test. While the models validate nothing in production, this is the
    only thing holding them to the dict the engine actually resolves."""
    dumped = config_dump()
    problems = _differences(dumped, config_schema.DEFAULTS)
    assert not problems, (
        "config_models.DomainConfig() has drifted from config_schema.DEFAULTS "
        f"({len(problems)} difference(s)):\n  " + "\n  ".join(problems)
    )


def test_config_dump_round_trips_an_explicit_config():
    """`config_dump(config)` is the same dump path, not a defaults-only shortcut."""
    model = DomainConfig.model_validate(config_schema.DEFAULTS)
    assert not _differences(config_dump(model), config_schema.DEFAULTS)


def test_config_dump_uses_the_copy_alias_not_the_field_name():
    """`copy_` is an implementation detail; the JSON key is `copy`."""
    dumped = config_dump()
    assert "copy" in dumped
    assert "copy_" not in dumped


def test_declared_blocks_match_defaults_top_level_keys():
    """A whole block added to one side and not the other is the drift that hurts
    most, so name it separately from the leaf walk."""
    assert set(config_dump()) == set(config_schema.DEFAULTS)


def test_config_version_agrees():
    assert config_models.CONFIG_VERSION == config_schema.CONFIG_VERSION


# -- 2. enum agreement --------------------------------------------------------


@pytest.mark.parametrize(("literal_name", "frozenset_name"), ENUM_PAIRS, ids=[p[0] for p in ENUM_PAIRS])
def test_literal_enum_matches_config_schema_frozenset(literal_name, frozenset_name):
    members = set(typing.get_args(getattr(config_models, literal_name)))
    allowed = getattr(config_schema, frozenset_name)
    assert members == set(allowed), (
        f"{literal_name} vs config_schema.{frozenset_name}: "
        f"only in the model {sorted(members - set(allowed))!r}, "
        f"only in config_schema {sorted(set(allowed) - members)!r}"
    )


def test_every_config_schema_enum_frozenset_is_covered():
    """A new vocabulary added to `config_schema` must gain a model Literal (and a
    row in ENUM_PAIRS) rather than quietly going unmirrored."""
    declared = {
        name
        for name in dir(config_schema)
        if name.isupper() and isinstance(getattr(config_schema, name), frozenset)
    }
    assert declared == {pair[1] for pair in ENUM_PAIRS}


def test_meta_field_type_accepts_the_string_alias_only_on_the_field():
    """`"string"` is an alias `config_schema` handles separately, so it must be on
    `MetaField.type` but NOT in the `MetaFieldType` enum."""
    assert "string" not in typing.get_args(config_models.MetaFieldType)
    assert set(config_schema.META_FIELD_TYPE_ALIASES) == {"string"}
    assert config_models.MetaField(key="k", type="string").type == "string"
    assert config_models.MetaField(key="k", type="text").type == "text"
    with pytest.raises(ValidationError):
        config_models.MetaField(key="k", type="stringy")


# -- 3. every real config validates against the models ------------------------


def test_the_shipped_config_set_is_what_we_think_it_is():
    """Guard the set: a renamed or missing config would make the suite below
    pass by covering nothing."""
    assert REPO_CONFIG.is_file()
    assert SHIPPED_CONFIGS == [REPO_CONFIG]


@pytest.mark.parametrize("path", SHIPPED_CONFIGS, ids=lambda p: p.name)
def test_shipped_config_validates_against_the_models(path):
    raw = json.loads(path.read_text())
    # The models describe the NORMALIZED tree (that is what DEFAULTS is, and what
    # `GET /config` serves), so normalize first, exactly as the load path does.
    DomainConfig.model_validate(config_schema.normalize(raw))


@pytest.mark.parametrize("path", SHIPPED_CONFIGS, ids=lambda p: p.name)
def test_shipped_config_survives_a_model_round_trip(path):
    """Parsing then dumping must not drop or rewrite a value the engine reads:
    the generated schema/TS would then describe a tree the app does not have.

    Optional fields the file omits come back as `null`, the models declare them,
    which is the point of publishing a schema, so this is directional; see
    `_lost_or_rewritten`.
    """
    normalized = config_schema.normalize(json.loads(path.read_text()))
    problems = [
        problem
        for problem in _lost_or_rewritten(
            normalized, config_dump(DomainConfig.model_validate(normalized))
        )
        if problem.split(":")[0] not in UNDECLARED_IN_DEFAULTS
    ]
    assert not problems, f"{path.name} changed through the models:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("path", UNDECLARED_IN_DEFAULTS, ids=sorted(UNDECLARED_IN_DEFAULTS))
def test_the_undeclared_exceptions_really_are_undeclared(path):
    """The allow-list above exists because `DEFAULTS` does not declare the key,
    not to paper over a model that forgot one. If the engine ever declares it,
    this fails and the exception must go."""
    node: Any = config_schema.DEFAULTS
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]
    assert node is None, f"{path} is declared in DEFAULTS now, drop it from UNDECLARED_IN_DEFAULTS"


# -- 4. strictness holds ------------------------------------------------------


def _mutated(path: str, value: Any) -> dict:
    """A deep copy of the normalized defaults with one leaf replaced."""
    config = copy.deepcopy(config_schema.DEFAULTS)
    node = config
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    assert parts[-1] in node, f"{path} is not a DEFAULTS leaf, fix the test, not the model"
    node[parts[-1]] = value
    return config


STRICTNESS_CASES = (
    # A string where `config_schema._int` wants a number. Lax pydantic coerces
    # "30" -> 30, which would let the published schema accept a config the
    # validator rejects.
    ("timing.slotDurationMinutes", "30"),
    ("timing.cancellationWindowHours", "24"),
    ("pricing.rate.amountMinorUnits", "1000"),
    ("pricing.currencyExponent", None),
    # An int where `_bool` wants a bool.
    ("capabilities.payments", 1),
    ("capabilities.reviews", 0),
    ("pricing.chargePerPerson", "true"),
    ("timing.waitlist.enabled", 1),
    # A bool where a number belongs, `_int` rejects bool explicitly.
    ("timing.leadTimeMinutes", True),
    # Unknown enum members.
    ("booking.unitKind", "nope"),
    ("booking.granularity", "fortnight"),
    ("pricing.model", "per_vibe"),
    ("pricing.rate.per", "fortnight"),
    ("payments.flow", "cash_maybe"),
    ("tenancy.mode", "triple"),
    ("location.default", "somewhere"),
    ("timing.confirmation", "eventually"),
    ("discovery.mode", "vibes"),
    # A dict/list in a scalar position (the `_enum` type-guard case).
    ("booking.unitKind", {"kind": "staff"}),
    ("location.modes", "on_site"),
    # Strings where a string block is not a block at all.
    ("terms", "Business"),
    ("metaFields", []),
)


@pytest.mark.parametrize(("path", "value"), STRICTNESS_CASES, ids=[f"{p}={v!r}" for p, v in STRICTNESS_CASES])
def test_models_reject_what_config_schema_rejects(path, value):
    with pytest.raises(ValidationError):
        DomainConfig.model_validate(_mutated(path, value))


@pytest.mark.parametrize(
    ("path", "value"),
    (
        ("timing.slotDurationMinutes", 45),
        ("timing.slotDurationMinutes", 45.5),
        ("capabilities.payments", False),
        ("booking.unitKind", "staff"),
        ("pricing.rate.per", "night"),
        ("location.modes", ["remote", "delivery"]),
    ),
    ids=lambda v: repr(v),
)
def test_models_accept_what_config_schema_accepts(path, value):
    """The mirror of the above: strictness must not have become a blanket
    rejection of legitimate values (a float is a valid `_int`)."""
    assert DomainConfig.model_validate(_mutated(path, value)) is not None


def test_defaults_mutation_helper_does_not_touch_defaults():
    before = copy.deepcopy(config_schema.DEFAULTS)
    _mutated("timing.slotDurationMinutes", "30")
    assert config_schema.DEFAULTS == before


def test_unknown_top_level_keys_are_ignored_like_check_shape():
    """`config_schema` only inspects keys `DEFAULTS` declares, so an unknown
    block is dropped, not an error, the models must agree or the published
    schema would reject a file the engine loads."""
    config = copy.deepcopy(config_schema.DEFAULTS)
    config["theme"] = {"primary": "#000"}  # v1's removed block
    dumped = config_dump(DomainConfig.model_validate(config))
    assert "theme" not in dumped
    assert not _differences(dumped, config_schema.DEFAULTS)


def test_list_item_models_keep_extra_presentational_keys():
    """Shipped pivots carry `label`/`helpText`/`appliesWhen` the engine ignores;
    dropping them on a round trip would silently rewrite a pivot file."""
    config = copy.deepcopy(config_schema.DEFAULTS)
    config["pricing"]["fees"] = [
        {"key": "clean", "kind": "flat", "amountMinorUnits": 500, "helpText": "kept"}
    ]
    dumped = config_dump(DomainConfig.model_validate(config))
    assert dumped["pricing"]["fees"][0]["helpText"] == "kept"


# -- 5. no import warnings ----------------------------------------------------


def test_importing_config_models_emits_no_warning():
    """The module is written to avoid pydantic's "field shadows parent
    attribute" UserWarning on `copy` (declared as `copy_`, aliased). Any warning
    at import is a regression: it appears in every `python -c "import app"`, in
    the schema generator's output and in CI logs."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(config_models)
    assert not caught, "importing app.config_models warned: " + "; ".join(
        f"{w.category.__name__}: {w.message}" for w in caught
    )


def test_reload_leaves_the_module_usable():
    """`importlib.reload` above rebinds the classes; make sure the reloaded module
    still satisfies the golden test, so test order cannot matter."""
    importlib.reload(config_models)
    assert not _differences(config_models.config_dump(), config_schema.DEFAULTS)
