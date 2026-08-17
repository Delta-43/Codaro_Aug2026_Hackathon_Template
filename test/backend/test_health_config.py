"""GET /health and GET /config.

`/config` is the load-bearing endpoint of the whole pivot thesis: the
frontend renders every label and every limit from it, so it must be a
straight read of `domain.config.json` (whatever `DOMAIN_CONFIG_PATH` points
at) and never a hard-coded payload.
"""

import json

import pytest


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _assert_facets(facets):
    """The derived `search.facets` map is three booleans (price/distance/rating)."""
    assert set(facets) == {"price", "distance", "rating"}
    assert all(isinstance(value, bool) for value in facets.values())


def test_config_returns_the_file_it_was_pointed_at(client, domain_config):
    expected = domain_config()  # the untouched fixture config
    response = client.get("/config")
    assert response.status_code == 200
    payload = response.json()
    # /config serves the on-disk config verbatim plus a resolved `search.facets`
    # block (derivation AND-ed with any declared override). The config file may or
    # may not carry its own `search`, so strip it from BOTH sides before comparing
    # the rest, then assert the facets separately.
    facets = payload.pop("search")["facets"]
    expected.pop("search", None)
    assert payload == expected
    _assert_facets(facets)


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


def test_config_reload_picks_up_a_file_edit_without_a_restart(client):
    """POST /config/reload drops the cached config and returns the fresh file
    — the instant-pivot mechanism.

    Edits the file on disk *directly* (not through the `domain_config`
    fixture, which clears the cache for us) so the GET below is genuinely
    stale and only `/config/reload` refreshes it.
    """
    import json as _json
    import os

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


def test_config_reload_also_carries_search_facets(client):
    """POST /config/reload goes through the same `_config_with_facets` helper."""
    payload = client.post("/config/reload").json()
    assert "search" in payload
    _assert_facets(payload["search"]["facets"])


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
    """lib/domain.tsx types DomainConfig with these five sections."""
    payload = client.get("/config").json()
    for section in ("domain", "terms", "rules", "copy", "theme", "metaFields"):
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


def test_repo_config_endpoint_matches_the_file_on_disk(client, use_real_config):
    on_disk = json.loads(use_real_config.read_text())
    payload = client.get("/config").json()
    # The on-disk config now carries its own `search` block, and the endpoint
    # resolves `search.facets` from live data (AND declared overrides), so the
    # served `search` need not equal the file's. Strip `search` from BOTH sides
    # and assert the rest is served verbatim, then check the facet shape.
    facets = payload.pop("search")["facets"]
    on_disk.pop("search", None)
    assert payload == on_disk
    _assert_facets(facets)


def test_repo_config_declares_every_term_the_ui_uses(client, use_real_config):
    terms = client.get("/config").json()["terms"]
    for term in ("resource", "resources", "slot", "slots", "booking", "bookings", "client", "admin"):
        assert term in terms and terms[term], f"missing term: {term}"
