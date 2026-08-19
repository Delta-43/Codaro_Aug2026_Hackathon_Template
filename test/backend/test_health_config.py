"""GET /health, GET /config and POST /config/reload.

`/config` is the load-bearing endpoint of the whole pivot thesis: the
frontend renders every label and every limit from it, so it must be driven by
`domain.config.json` (whatever `DOMAIN_CONFIG_PATH` points at) and never be a
hard-coded payload.

**Config v2 contract change.** `/config` no longer echoes the file verbatim: it
serves `config_schema.normalize()`d + `validate()`d tree, so every v2 key is
guaranteed present even for a file that declares five sections. What the
operator typed must still *survive* that normalization untouched — that is what
these tests pin, instead of dict equality against the raw file.
"""

import json
import os
from pathlib import Path

import pytest

from app.config_schema import DEFAULTS, normalize


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _assert_facets(facets):
    """The derived `search.facets` map is three booleans (price/distance/rating)."""
    assert set(facets) == {"price", "distance", "rating"}
    assert all(isinstance(value, bool) for value in facets.values())


def _assert_declared_survives(declared, served, path="config"):
    """Every value the pivot file declares must still be there, unchanged, in the
    served tree. Normalization may only ADD defaults — it must never drop or
    rewrite what the operator actually typed. The one exception is v1's `theme`
    block, which the engine deliberately drops: the frontend owns its palette."""
    for key, value in declared.items():
        if path == "config" and key == "theme":
            assert key not in served, "the removed `theme` block is still served"
            continue
        assert key in served, f"{path}.{key} vanished from the served config"
        if isinstance(value, dict):
            _assert_declared_survives(value, served[key], f"{path}.{key}")
        else:
            assert served[key] == value, (
                f"{path}.{key} was rewritten by normalization: "
                f"{served[key]!r} != declared {value!r}"
            )


def test_config_serves_the_normalized_tree_of_the_file_it_was_pointed_at(
    client, domain_config
):
    """v2: /config serves the NORMALIZED config, not the file verbatim. The
    fixture is a v1 file (five sections); everything it declares survives, and
    every v2 block it never mentioned is filled from the defaults."""
    declared = domain_config()  # the untouched fixture config
    response = client.get("/config")
    assert response.status_code == 200
    payload = response.json()

    # `search`/`discovery` facets are resolved against the live catalog, so they
    # are deliberately not a straight read of the file — covered separately below.
    declared.pop("search", None)
    declared.pop("discovery", None)
    _assert_declared_survives(declared, payload)

    # ...and the blocks the v1 file never heard of are present with defaults.
    for block in DEFAULTS:
        assert block in payload, f"normalization did not fill in {block}"
    assert payload["configVersion"] == 2
    assert payload["pricing"]["currency"] == DEFAULTS["pricing"]["currency"]
    assert payload["location"]["timezone"] == DEFAULTS["location"]["timezone"]
    assert payload["timing"]["confirmation"] == "instant"


def test_config_mirrors_the_v1_rules_block_into_timing(client, domain_config):
    """Back-compat: the five legacy `rules` keys are mirrored into `timing` (and
    back), so a v1 reader and a v2 reader can never disagree over the wire."""
    domain_config(rules={"cancellationWindowHours": 9, "bufferMinutes": 7})
    payload = client.get("/config").json()
    for key in DEFAULTS["rules"]:
        assert payload["rules"][key] == payload["timing"][key], key
    assert payload["timing"]["cancellationWindowHours"] == 9
    assert payload["timing"]["bufferMinutes"] == 7


def test_config_keeps_search_and_discovery_facets_consistent(client, db):
    """`discovery.facets` is the v2 five-key set; `search.facets` keeps the
    three-key v1 shape. The keys they share must carry the same value."""
    payload = client.get("/config").json()
    discovery_facets = payload["discovery"]["facets"]
    search_facets = payload["search"]["facets"]
    assert set(search_facets) == {"price", "distance", "rating"}
    assert set(discovery_facets) == {
        "price",
        "distance",
        "rating",
        "availability",
        "unitKind",
    }
    for key in search_facets:
        assert discovery_facets[key] == search_facets[key], key


def test_config_is_not_hardcoded_and_follows_a_pivot(client, domain_config):
    """Edit the config file -> /config changes. No code change involved."""
    before = client.get("/config").json()
    assert before["terms"]["resource"] == "Widget"

    domain_config(
        domain="medical",
        terms={"resource": "Doctor", "resources": "Doctors", "client": "Patient"},
        rules={"cancellationWindowHours": 2, "maxBookingsPerSlot": 4},
        copy={"landingTitle": "Book a Doctor"},
    )

    after = client.get("/config").json()
    assert after["domain"] == "medical"
    assert after["terms"]["resource"] == "Doctor"
    assert after["terms"]["client"] == "Patient"
    assert after["rules"]["cancellationWindowHours"] == 2
    assert after["rules"]["maxBookingsPerSlot"] == 4
    assert after["copy"]["landingTitle"] == "Book a Doctor"


def test_config_reload_picks_up_a_file_edit_without_a_restart(client, auth):
    """POST /config/reload drops the cached config and returns the fresh file
    — the instant-pivot mechanism. v2 made it **owner-gated**, so it runs as an
    owner here.

    Edits the file on disk *directly* (not through the `domain_config`
    fixture, which clears the cache for us) so the GET below is genuinely
    stale and only `/config/reload` refreshes it.
    """
    import json as _json
    import os

    auth(role="owner")

    # Prime the lru_cache.
    assert client.get("/config").json()["terms"]["resource"] == "Widget"

    path = os.environ["DOMAIN_CONFIG_PATH"]
    config = _json.loads(open(path).read())
    config["terms"]["resource"] = "Doctor"
    with open(path, "w") as handle:
        handle.write(_json.dumps(config))

    # Still cached: the plain GET has not noticed the edit.
    assert client.get("/config").json()["terms"]["resource"] == "Widget"

    reloaded = client.post("/config/reload")
    assert reloaded.status_code == 200
    assert reloaded.json()["terms"]["resource"] == "Doctor"
    # And the plain GET now reflects it too.
    assert client.get("/config").json()["terms"]["resource"] == "Doctor"


def test_config_exposes_the_derived_search_facets(client):
    """/config carries a derived `search.facets` map (price/distance/rating)."""
    payload = client.get("/config").json()
    assert "search" in payload
    _assert_facets(payload["search"]["facets"])


def test_config_reload_also_carries_search_facets(client, auth):
    """POST /config/reload goes through the same `_config_with_facets` helper."""
    auth(role="owner")
    payload = client.post("/config/reload").json()
    assert "search" in payload
    _assert_facets(payload["search"]["facets"])


# --- POST /config/reload is a control-plane endpoint: owner-gated ---------


def test_config_reload_rejects_an_unauthenticated_call(client):
    """No `auth` fixture -> the real `require_user` runs -> 401 for the missing
    bearer token. v1 let anyone re-read a file off disk."""
    assert client.post("/config/reload").status_code == 401


def test_config_reload_rejects_a_signed_in_client(client, auth):
    auth(role="client")
    response = client.post("/config/reload")
    assert response.status_code == 403


def test_config_reload_allows_an_owner(client, auth):
    auth(role="owner")
    assert client.post("/config/reload").status_code == 200


def _write_config(path, **sections):
    config = json.loads(Path(path).read_text())
    for section, value in sections.items():
        if isinstance(value, dict) and isinstance(config.get(section), dict):
            config[section] = {**config[section], **value}
        else:
            config[section] = value
    Path(path).write_text(json.dumps(config))
    return config


def test_config_reload_rejects_a_broken_file_with_422_and_keeps_the_good_one(
    client, auth
):
    """The fresh file is validated BEFORE the good cache is dropped, so a typo
    made mid-pivot returns 422 and the running app keeps serving the last good
    config instead of falling over."""
    auth(role="owner")
    # Prime the cache with the good fixture config.
    assert client.get("/config").json()["terms"]["resource"] == "Widget"

    path = os.environ["DOMAIN_CONFIG_PATH"]
    _write_config(
        path,
        terms={"resource": "Doctor"},
        rules={"maxBookingsPerSlot": 0},
        pricing={"currency": "EUROS", "model": "guesswork"},
    )

    response = client.post("/config/reload")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    # Every problem is listed at once, not just the first one.
    assert "maxBookingsPerSlot" in detail["message"]
    assert "pricing.currency" in detail["message"]
    assert "pricing.model" in detail["message"]

    # The bad file did NOT take the app down: the cached good config still serves.
    still = client.get("/config").json()
    assert still["terms"]["resource"] == "Widget"
    assert still["rules"]["maxBookingsPerSlot"] == 1


def test_config_reload_of_a_malformed_json_file_is_a_422_not_a_500(client, auth):
    auth(role="owner")
    assert client.get("/config").json()["domain"] == "test-domain"
    Path(os.environ["DOMAIN_CONFIG_PATH"]).write_text("{ not json at all")

    response = client.post("/config/reload")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert client.get("/config").json()["domain"] == "test-domain"


def test_config_facets_reflect_the_live_catalog(client, db):
    """An empty catalog supports neither price nor distance; seeding a priced
    service and a provider with real coordinates flips both facets on — proving
    the endpoint derives facets from live data, not a hard-coded map."""
    from helpers import make_provider, make_service

    empty = client.get("/config").json()["search"]["facets"]
    assert empty == {"price": False, "distance": False, "rating": True}

    provider = make_provider(db, metadata={"location": {"lat": 52.2, "lng": 21.0}})
    make_service(db, provider["id"], price_minor_units=1500)

    facets = client.get("/config").json()["search"]["facets"]
    assert facets == {"price": True, "distance": True, "rating": True}


def test_config_override_forces_a_facet_off(client, db, domain_config):
    """A config-declared `search.facets` can only force a facet OFF: the resolved
    value is `derived AND declared` (declared defaulting to true). Seed data that
    derivation would use to enable BOTH price and distance, then declare
    `distance: false` and assert only distance is vetoed — price, whose override
    is omitted (defaults true), still reflects derivation."""
    from helpers import make_provider, make_service

    provider = make_provider(db, metadata={"location": {"lat": 52.2, "lng": 21.0}})
    make_service(db, provider["id"], price_minor_units=1500)

    domain_config(search={"facets": {"distance": False}})

    facets = client.get("/config").json()["search"]["facets"]
    # derivation-on AND declared-false -> off.
    assert facets["distance"] is False
    # override omitted (defaults true) -> defers to derivation (data present) -> on.
    assert facets["price"] is True
    assert facets["rating"] is True


def test_config_declared_true_cannot_conjure_a_missing_dimension(client, db, domain_config):
    """The override can only subtract: a declared `true` for every facet against
    an empty catalog leaves price/distance OFF (derivation has no data to offer
    them) — `true AND False` is False — while rating stays on."""
    domain_config(search={"facets": {"price": True, "distance": True, "rating": True}})

    facets = client.get("/config").json()["search"]["facets"]
    assert facets == {"price": False, "distance": False, "rating": True}


def test_config_exposes_every_section_the_frontend_consumes(client):
    """lib/domain.tsx types DomainConfig with these sections."""
    payload = client.get("/config").json()
    for section in ("domain", "terms", "rules", "copy", "metaFields"):
        assert section in payload, f"missing config section: {section}"
    assert isinstance(payload["terms"], dict)
    assert isinstance(payload["rules"], dict)
    assert isinstance(payload["metaFields"], dict)


@pytest.mark.parametrize(
    "rule_key",
    [
        "cancellationWindowHours",
        "maxBookingsPerSlot",
        "slotDurationMinutes",
        "advanceBookingWindowDays",
        "bufferMinutes",
    ],
)
def test_repo_config_declares_every_rule_key(client, use_real_config, rule_key):
    """Contract test against the repo's actual domain.config.json."""
    rules = client.get("/config").json()["rules"]
    assert rule_key in rules
    assert isinstance(rules[rule_key], int)


def test_repo_config_file_is_a_normalize_fixpoint(use_real_config):
    """`domain.config.json` is now an explicit v2 file: normalizing it is a
    no-op, so what an operator reads in the repo is exactly what the engine
    resolves. (A v1 file still works — see test_config_schema.py — this just
    pins that the shipped file needs no filling in.)"""
    on_disk = json.loads(use_real_config.read_text())
    assert set(on_disk) == set(DEFAULTS)
    assert normalize(on_disk) == on_disk


def test_repo_config_endpoint_matches_the_file_on_disk(client, use_real_config):
    """The endpoint serves the normalized file. Since the repo config is a
    normalize fixpoint, `normalize(file)` must equal the payload once the
    derived facet maps (the endpoint's only non-file contribution) are stripped
    from both sides."""
    on_disk = normalize(json.loads(use_real_config.read_text()))
    payload = client.get("/config").json()

    facets = payload["search"].pop("facets")
    on_disk["search"].pop("facets", None)
    payload["discovery"].pop("facets", None)
    on_disk["discovery"].pop("facets", None)

    assert payload == on_disk
    _assert_facets(facets)


def test_repo_config_declares_every_term_the_ui_uses(client, use_real_config):
    terms = client.get("/config").json()["terms"]
    for term in ("resource", "resources", "slot", "slots", "booking", "bookings", "client", "admin"):
        assert term in terms and terms[term], f"missing term: {term}"


def test_config_reload_rejects_a_typo_in_a_descriptor_list(client, auth):
    """The new list-of-descriptor checks are wired into the load path, not just
    callable: a fee with `kind: "percentage"` — which would otherwise price as 0
    on every booking — stops the reload with a 422 naming the entry."""
    auth(role="owner")
    assert client.get("/config").json()["terms"]["resource"] == "Widget"

    _write_config(
        os.environ["DOMAIN_CONFIG_PATH"],
        pricing={
            "fees": [
                {"key": "service", "label": "Service", "kind": "percentage", "rateBps": 1250}
            ]
        },
        booking={"options": [{"key": "seat", "label": "Seat", "type": "select"}]},
    )

    response = client.post("/config/reload")
    assert response.status_code == 422
    message = response.json()["detail"]["message"]
    assert "pricing.fees[0].kind" in message
    assert "booking.options[0].choices" in message

    # And the running app still serves the last good config.
    assert client.get("/config").json()["pricing"]["fees"] == []


@pytest.mark.parametrize(
    ("sections", "path"),
    [
        ({"recurrence": {"patterns": [{"every": "week"}]}}, "recurrence.patterns[0]"),
        ({"booking": {"unitKind": {"kind": "staff"}}}, "booking.unitKind"),
        ({"pricing": {"rate": {"per": ["hour"]}}}, "pricing.rate.per"),
    ],
)
def test_config_reload_of_an_object_in_an_enum_position_is_a_422_not_a_500(
    client, auth, sections, path
):
    """`_enum` type-guards before the membership test, so a hand-edited file that
    drops an object/array where a scalar enum belongs comes back as the
    documented 422 — it used to raise TypeError out of `validate()` and 500."""
    auth(role="owner")
    assert client.get("/config").json()["terms"]["resource"] == "Widget"

    _write_config(os.environ["DOMAIN_CONFIG_PATH"], **sections)

    response = client.post("/config/reload")
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert path in detail["message"], detail["message"]

    # The last good config is still what the app serves.
    still = client.get("/config").json()
    assert still["terms"]["resource"] == "Widget"
    assert still["recurrence"]["patterns"] == []
    assert still["booking"]["unitKind"] == "time_slot"
