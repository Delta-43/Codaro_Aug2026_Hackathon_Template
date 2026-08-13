#!/usr/bin/env python3
"""Validate domain.config.json — the single file a domain pivot edits.

The engine reads vocabulary from `terms`, business numbers from `rules`, and
UI strings from `copy`; nothing in the code hard-codes them. So a missing key
here does not fail loudly at build time, it fails at runtime in whichever
request happens to read it first. This script turns that into a CI failure.

Run it locally the same way CI does:

    python .github/scripts/validate_domain_config.py

Pass a path to check an alternative domain file:

    python .github/scripts/validate_domain_config.py domain.config.medical.example.json
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Keys the backend and frontend read by name. Adding a rule to the engine
# means adding it here too, so every domain file is forced to define it.
REQUIRED_SECTIONS = ["domain", "terms", "rules", "copy", "theme", "metaFields"]
REQUIRED_TERMS = ["resource", "resources", "slot", "slots", "booking", "bookings", "client", "admin"]
REQUIRED_RULES = {
    "cancellationWindowHours": (int, float),
    "maxBookingsPerSlot": int,
    "slotDurationMinutes": int,
    "advanceBookingWindowDays": int,
    "bufferMinutes": (int, float),
}
REQUIRED_COPY = [
    "landingTitle",
    "landingSubtitle",
    "confirmTitle",
    "emptyStateSlots",
    "emptyStateBookings",
]
REQUIRED_THEME = ["primaryColor", "radius"]
REQUIRED_META_FIELD_GROUPS = ["resources", "bookings"]


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        return [f"{path} does not exist."]
    except json.JSONDecodeError as e:
        return [f"{path} is not valid JSON: {e}"]

    if not isinstance(config, dict):
        return [f"{path} must contain a JSON object at the top level."]

    for section in REQUIRED_SECTIONS:
        if section not in config:
            errors.append(f"missing top-level key: {section!r}")

    terms = config.get("terms", {})
    for term in REQUIRED_TERMS:
        if not isinstance(terms.get(term), str) or not terms.get(term):
            errors.append(f"terms.{term} must be a non-empty string (<Term> renders it)")

    rules = config.get("rules", {})
    for rule, expected_type in REQUIRED_RULES.items():
        value = rules.get(rule)
        if value is None:
            errors.append(f"rules.{rule} is missing")
        elif isinstance(value, bool) or not isinstance(value, expected_type):
            errors.append(f"rules.{rule} must be a number, got {value!r}")
        elif value < 0:
            errors.append(f"rules.{rule} must not be negative, got {value!r}")

    # A slot that allows zero bookings makes the whole engine unusable, and
    # it is an easy typo to make when pivoting domains.
    if isinstance(rules.get("maxBookingsPerSlot"), int) and rules["maxBookingsPerSlot"] < 1:
        errors.append("rules.maxBookingsPerSlot must be at least 1")
    if isinstance(rules.get("slotDurationMinutes"), int) and rules["slotDurationMinutes"] < 1:
        errors.append("rules.slotDurationMinutes must be at least 1")

    copy = config.get("copy", {})
    for key in REQUIRED_COPY:
        if not isinstance(copy.get(key), str) or not copy.get(key):
            errors.append(f"copy.{key} must be a non-empty string")

    theme = config.get("theme", {})
    for key in REQUIRED_THEME:
        if not isinstance(theme.get(key), str) or not theme.get(key):
            errors.append(f"theme.{key} must be a non-empty string")

    meta_fields = config.get("metaFields", {})
    for group in REQUIRED_META_FIELD_GROUPS:
        fields = meta_fields.get(group)
        if not isinstance(fields, list):
            errors.append(f"metaFields.{group} must be a list (use [] when the domain adds no extra fields)")
            continue
        # Each entry drives a rendered form input, so all three keys are load-bearing.
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                errors.append(f"metaFields.{group}[{i}] must be an object")
                continue
            for required in ("key", "label", "type"):
                if not isinstance(field.get(required), str) or not field.get(required):
                    errors.append(f"metaFields.{group}[{i}].{required} must be a non-empty string")

    return errors


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or [REPO_ROOT / "domain.config.json"]

    failed = False
    for target in targets:
        errors = validate(target)
        if errors:
            failed = True
            print(f"✗ {target.name}")
            for error in errors:
                print(f"    {error}")
                print(f"::error file={target.name}::{error}")
        else:
            print(f"✓ {target.name}")

    if failed:
        print("\ndomain.config.json is the file a pivot edits — fix the keys above before merging.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
