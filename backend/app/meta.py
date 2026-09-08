# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Config-driven `metadata` validator.

Built from ``get_config()["metaFields"][entity]`` *at request time*, so a
pivot that adds/removes a domain field needs no code change. Semantics:

* **Lenient on undeclared keys** — the ``metadata jsonb`` column is the
  extension point, so unknown keys pass through untouched.
* **Strict on declared keys** — a declared field present with the wrong type
  is a 422 carrying the frontend ``ApiError`` envelope (``VALIDATION_ERROR``
  with ``{field, label, expected}`` in ``details``).
* **Optional by default** — a declared field may set ``"required": true`` to
  force its presence; otherwise its absence is fine.

Type map: ``text → str``, ``number → int|float`` (not ``bool``),
``boolean → bool``, ``date → an ISO date string``; ``select`` and ``file``
pass through unchecked (their contents are a UI concern, not a data one).

Declared types are resolved through ``config_schema.META_FIELD_TYPE_ALIASES``
first. The alias table was added to the load-time validator so a ``"string"``
field would stop silently validating nothing — but this map was left keyed on
the canonical names only, so ``"string"`` passed validation at load and then
matched no check at request time: the same silent-no-op, one layer down.
"""
from __future__ import annotations

from datetime import date, datetime

from app.config import get_config
from app.config_schema import META_FIELD_TYPE_ALIASES
from app.errors import VALIDATION_ERROR, api_error


def _is_date(value) -> bool:
    """A full ISO date, or an ISO datetime whose date part is one.

    Parsing `value[:10]` accepted anything that merely STARTED with a date, so
    `"2026-08-18 or whenever"` validated and was stored verbatim in the
    `metadata jsonb` column — the same declared-type-that-checks-nothing this
    module's alias handling exists to prevent. Both parses read the whole
    string, so trailing junk is rejected while datetimes still pass.
    """
    if not isinstance(value, str):
        return False
    for parse in (date.fromisoformat, datetime.fromisoformat):
        try:
            parse(value)
            return True
        except ValueError:
            continue
    return False


# bool is a subclass of int, so "number" must exclude it explicitly.
_CHECKS = {
    "text": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "date": _is_date,
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
                # ApiError envelope, not a bare detail dict: the frontend seam
                # reads {code, message} and would otherwise render this as a
                # raw "POST ... failed (422)" NETWORK error.
                raise api_error(
                    VALIDATION_ERROR,
                    f"{label} is required.",
                    details={"field": key, "label": label, "error": "required"},
                    status=422,
                )
            continue
        check = _CHECKS.get(META_FIELD_TYPE_ALIASES.get(ftype, ftype))
        if check is not None and not check(metadata[key]):
            raise api_error(
                VALIDATION_ERROR,
                f"{label} must be a {ftype} value.",
                details={"field": key, "label": label, "expected": ftype},
                status=422,
            )


def merged_metadata(entity: str, supplied: dict | None, *, reserved: tuple[str, ...] = ()) -> dict:
    """Validate a client-supplied `metadata` blob and return it ready to merge.

    `metaFields` is billed as the no-migration extension point for every base
    table, but only `resources` and `slots` ever accepted a `metadata` body — so
    a `metaFields.bookings` / `.providers` / `.services` descriptor (the shipped
    medical example declares one) had no input path and validated nothing. The
    routers merge this UNDER their own engine-owned keys, and `reserved` drops
    the names the engine writes itself, so a domain field can never shadow a
    price, an owner id or a config override block.
    """
    supplied = {k: v for k, v in (supplied or {}).items() if k not in reserved}
    validate_metadata(entity, supplied)
    return supplied
