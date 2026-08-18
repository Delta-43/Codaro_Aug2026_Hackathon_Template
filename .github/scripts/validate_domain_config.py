#!/usr/bin/env python3
"""Validate domain.config.json — the single file a domain pivot edits.

v1 of this script kept its own copy of the required keys and their types, which
meant CI and the engine could disagree about what a valid config was. It now
imports the same `app.config_schema` the backend loads through, so there is
exactly one definition of "valid" and adding a field to the engine cannot leave
CI behind.

Run it locally the same way CI does:

    python .github/scripts/validate_domain_config.py

Pass a path to check an alternative domain file:

    python .github/scripts/validate_domain_config.py domain.config.medical.example.json
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config_schema import normalize, validate  # noqa: E402


def check(path: Path) -> list[str]:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return [f"{path} does not exist."]
    except json.JSONDecodeError as e:
        return [f"{path} is not valid JSON: {e}"]

    if not isinstance(raw, dict):
        return [f"{path} must contain a JSON object at the top level."]

    # Validate what the engine will actually resolve — defaults applied and the
    # v1 `rules`/`search` aliases folded in — so a v1 file still passes.
    return validate(normalize(raw))


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or [REPO_ROOT / "domain.config.json"]

    failed = False
    for target in targets:
        errors = check(target)
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
