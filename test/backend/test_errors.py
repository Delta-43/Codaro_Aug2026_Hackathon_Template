"""Pure unit tests for `app.errors.api_error` — the typed-error factory that maps
the frontend's ApiError codes to HTTP statuses and wraps them in the
`{code, message, details?}` envelope the frontend reads back."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import errors as E


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (E.NOT_FOUND, 404),
        (E.SLOT_UNAVAILABLE, 409),
        (E.CAPACITY_EXCEEDED, 409),
        (E.CUTOFF_PASSED, 409),
        (E.INVALID_RANGE, 400),
    ],
)
def test_code_maps_to_status(code, status):
    exc = E.api_error(code, "boom")
    assert isinstance(exc, HTTPException)
    assert exc.status_code == status
    assert exc.detail == {"code": code, "message": "boom"}


def test_details_are_included_when_given():
    exc = E.api_error(E.SLOT_UNAVAILABLE, "taken", details={"slotId": "s1"})
    assert exc.detail == {
        "code": E.SLOT_UNAVAILABLE,
        "message": "taken",
        "details": {"slotId": "s1"},
    }


def test_details_omitted_when_absent():
    exc = E.api_error(E.NOT_FOUND, "nope")
    assert "details" not in exc.detail


def test_unknown_code_defaults_to_400():
    exc = E.api_error("SOMETHING_NEW", "x")
    assert exc.status_code == 400
    assert exc.detail["code"] == "SOMETHING_NEW"


def test_explicit_status_overrides_the_mapping():
    exc = E.api_error(E.NOT_FOUND, "x", status=418)
    assert exc.status_code == 418
