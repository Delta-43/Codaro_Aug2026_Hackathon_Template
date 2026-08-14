"""Config-driven `metadata` validator.

Built from ``get_config()["metaFields"][entity]`` *at request time*, so a
pivot that adds/removes a domain field needs no code change. Semantics:

* **Lenient on undeclared keys** — the ``metadata jsonb`` column is the
  extension point, so unknown keys pass through untouched.
* **Strict on declared keys** — a declared field present with the wrong type
  is a 422 with ``{field, label, expected}`` detail.
* **Optional by default** — a declared field may set ``"required": true`` to
  force its presence; otherwise its absence is fine.

Type map: ``text → str``, ``number → int|float`` (not ``bool``),
``boolean → bool``; unknown types pass through unchecked.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.config import get_config

# bool is a subclass of int, so "number" must exclude it explicitly.
_CHECKS = {
    "text": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def validate_metadata(entity: str, metadata: dict | None) -> None:
    metadata = metadata or {}
    fields = get_config().get("metaFields", {}).get(entity, [])
    for field in fields:
        key = field.get("key")
        if not key:
            continue
        label = field.get("label", key)
        ftype = field.get("type")
        if key not in metadata:
            if field.get("required"):
                raise HTTPException(
                    422, {"field": key, "label": label, "error": "required"}
                )
            continue
        check = _CHECKS.get(ftype)
        if check is not None and not check(metadata[key]):
            raise HTTPException(
                422, {"field": key, "label": label, "expected": ftype}
            )
