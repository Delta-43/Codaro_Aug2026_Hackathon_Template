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


def test_config_returns_the_file_it_was_pointed_at(client, domain_config):
    expected = domain_config()  # the untouched fixture config
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == expected


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
    assert client.get("/config").json() == on_disk


def test_repo_config_declares_every_term_the_ui_uses(client, use_real_config):
    terms = client.get("/config").json()["terms"]
    for term in ("resource", "resources", "slot", "slots", "booking", "bookings", "client", "admin"):
        assert term in terms and terms[term], f"missing term: {term}"
