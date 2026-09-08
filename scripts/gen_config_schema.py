#!/usr/bin/env python3
# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generate `domain.config.schema.json` from the pydantic models.

`domain.config.json` is the file a pivot edits, and until now editing it was
blind: no autocomplete, no inline documentation, and a typo surfaced only when
the backend refused to boot. A published JSON Schema fixes all three — VS Code,
JetBrains and every other editor that speaks JSON Schema read it automatically
via the `$schema` key the config file now carries.

The schema is DERIVED, never hand-written. `backend/app/config_models.py` is the
single source of truth; the descriptions in this schema are the `Field(...)`
descriptions there, and the frontend's `src/api/config.generated.ts` is in turn
generated from this file. That chain is what stops the config shape drifting
between the backend, the schema and the TypeScript — which it already had.

    python3 scripts/gen_config_schema.py            # write the schema
    python3 scripts/gen_config_schema.py --check    # verify it is current (CI)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config_models import DomainConfig  # noqa: E402

OUT_PATH = REPO_ROOT / "domain.config.schema.json"
SCHEMA_URL = (
    "https://raw.githubusercontent.com/kaveOO/Arbor/main/domain.config.schema.json"
)


def _strip_property_titles(node: object) -> None:
    """Drop the auto-generated `title` pydantic puts on every property.

    json-schema-to-typescript promotes any sub-schema carrying a `title` into a
    named top-level type. Pydantic titles every field, so the generated
    TypeScript came out as ~200 aliases with mangled names (`Providercode`,
    `Ratebps`) and collisions on the generic ones (`Key`, `Label`, `Mode`,
    `Required`). Without them the properties inline and only the models — whose
    titles live on the `$defs` entries, which this deliberately does not touch —
    become named interfaces.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop in value.values():
                    if isinstance(prop, dict):
                        prop.pop("title", None)
            _strip_property_titles(value)
    elif isinstance(node, list):
        for item in node:
            _strip_property_titles(item)


def build() -> dict:
    """The model's own JSON Schema, plus the identifying keys pydantic omits."""
    schema = DomainConfig.model_json_schema(by_alias=True, mode="validation")
    _strip_property_titles(schema)
    # Ordered so the file reads top-down: what it is, then the shape.
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_URL,
        "title": "Arbor domain config",
        "description": (
            "The pivot file. Vocabulary and global defaults for one deployment — "
            "every block here is also overridable per service through "
            "services.metadata.<block>. Generated from backend/app/config_models.py "
            "by scripts/gen_config_schema.py; do not edit by hand."
        ),
        **schema,
    }


def main() -> int:
    check = "--check" in sys.argv
    body = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"

    if check:
        if not OUT_PATH.exists():
            print(f"{OUT_PATH.name} is missing — run: python3 scripts/gen_config_schema.py")
            return 1
        if OUT_PATH.read_text(encoding="utf-8") != body:
            print(
                f"{OUT_PATH.name} is stale — the models in backend/app/config_models.py "
                "changed.\nRun: python3 scripts/gen_config_schema.py"
            )
            return 1
        print(f"{OUT_PATH.name} is current")
        return 0

    OUT_PATH.write_text(body, encoding="utf-8")
    defs = len(build().get("$defs", {}))
    print(f"wrote {OUT_PATH.name} — {defs} block definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
