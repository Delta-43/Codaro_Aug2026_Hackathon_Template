# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Typed API errors that carry the frontend's ApiError codes.

The frontend (`frontend/src/api/errors.ts`) models failures as an `ApiError`
with a `code` from a fixed union. Rather than flattening every rule violation
into a bare status line, the backend raises `HTTPException` whose `detail` is a
structured `{code, message, details?}` object; the frontend seam reads
`body.detail.code` back into an `ApiError`. Transport failures map to NETWORK on
the client side (never raised here).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

# ApiErrorCode union, keep in lockstep with frontend/src/api/errors.ts.
NOT_FOUND = "NOT_FOUND"
SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
CUTOFF_PASSED = "CUTOFF_PASSED"
INVALID_RANGE = "INVALID_RANGE"
VALIDATION_ERROR = "VALIDATION_ERROR"
NETWORK = "NETWORK"  # client-side only

_STATUS = {
    NOT_FOUND: 404,
    SLOT_UNAVAILABLE: 409,
    CAPACITY_EXCEEDED: 409,
    CUTOFF_PASSED: 409,
    INVALID_RANGE: 400,
    VALIDATION_ERROR: 400,
}


def api_error(
    code: str,
    message: str,
    *,
    details: Optional[dict[str, Any]] = None,
    status: Optional[int] = None,
) -> HTTPException:
    """Build an HTTPException whose detail is the frontend ApiError envelope.
    Raise the return value: ``raise api_error(SLOT_UNAVAILABLE, "...")``."""
    detail: dict[str, Any] = {"code": code, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status or _STATUS.get(code, 400), detail=detail)
