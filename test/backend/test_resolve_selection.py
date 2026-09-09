# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pure unit tests for `bookings._resolve_selection`, the commit-time slot
validator that every booking create/reschedule funnels through.

`_resolve_selection(rules, occ, slot_ids, resource_id, party_size, credit)` is a
pure function: no DB, no config, no clock injection beyond `datetime.now`. It
raises the frontend's typed `ApiError` (an `HTTPException` whose `.detail` is
`{code, message, details?}`), so each test asserts the `code` that comes back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.errors import CAPACITY_EXCEEDED, INVALID_RANGE, NOT_FOUND, SLOT_UNAVAILABLE
from app.routers.bookings import _resolve_selection

RES = "res-1"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _occ_row(slot_id, start, end, *, resource_id=RES, capacity=1, booked=0):
    return {
        "slot_id": slot_id,
        "resource_id": resource_id,
        "starts_at": _iso(start),
        "ends_at": _iso(end),
        "capacity": capacity,
        "booked_count": booked,
    }


# A single anchor so back-to-back slots share an exact boundary (each fresh
# datetime.now() would differ by microseconds and break contiguity).
_ANCHOR = datetime.now(timezone.utc).replace(microsecond=0)


def _future(hours):
    return _ANCHOR + timedelta(hours=hours)


def _rules(lo=1, hi=1):
    return {"minSlotsPerBooking": lo, "maxSlotsPerBooking": hi}


def _one_slot(**kw):
    """A single valid, free, future slot keyed 's1'."""
    row = _occ_row("s1", _future(48), _future(49), **kw)
    return {"s1": row}


def _code(exc_info) -> str:
    return exc_info.value.detail["code"]


# --- happy paths -----------------------------------------------------------


def test_single_slot_ok_returns_the_row():
    occ = _one_slot()
    rows = _resolve_selection(_rules(), occ, ["s1"], RES, 1, credit=set())
    assert [r["slot_id"] for r in rows] == ["s1"]


def test_contiguous_multi_slot_ok_and_sorted():
    a = _occ_row("a", _future(48), _future(49))
    b = _occ_row("b", _future(49), _future(50))
    occ = {"a": a, "b": b}
    # Pass out of order; the resolver sorts by start.
    rows = _resolve_selection(_rules(hi=3), occ, ["b", "a"], RES, 1, credit=set())
    assert [r["slot_id"] for r in rows] == ["a", "b"]


def test_shared_capacity_party_within_room():
    occ = _one_slot(capacity=4, booked=1)
    rows = _resolve_selection(_rules(), occ, ["s1"], RES, 3, credit=set())
    assert rows[0]["slot_id"] == "s1"


# --- error branches --------------------------------------------------------


def test_empty_selection_is_invalid_range():
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), {}, [], RES, 1, credit=set())
    assert _code(e) == INVALID_RANGE


def test_unknown_slot_is_not_found():
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), {}, ["ghost"], RES, 1, credit=set())
    assert _code(e) == NOT_FOUND


def test_cross_resource_selection_is_invalid_range():
    a = _occ_row("a", _future(48), _future(49))
    b = _occ_row("b", _future(49), _future(50), resource_id="res-2")
    occ = {"a": a, "b": b}
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(hi=3), occ, ["a", "b"], RES, 1, credit=set())
    assert _code(e) == INVALID_RANGE


def test_too_few_slots_is_invalid_range():
    a = _occ_row("a", _future(48), _future(49))
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(lo=2, hi=3), {"a": a}, ["a"], RES, 1, credit=set())
    assert _code(e) == INVALID_RANGE


def test_too_many_slots_is_invalid_range():
    a = _occ_row("a", _future(48), _future(49))
    b = _occ_row("b", _future(49), _future(50))
    occ = {"a": a, "b": b}
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(lo=1, hi=1), occ, ["a", "b"], RES, 1, credit=set())
    assert _code(e) == INVALID_RANGE


def test_non_contiguous_selection_is_invalid_range():
    a = _occ_row("a", _future(48), _future(49))
    # gap: c starts an hour after a ends
    c = _occ_row("c", _future(50), _future(51))
    occ = {"a": a, "c": c}
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(hi=3), occ, ["a", "c"], RES, 1, credit=set())
    assert _code(e) == INVALID_RANGE


def test_past_slot_is_slot_unavailable():
    row = _occ_row("s1", _future(-3), _future(-2))
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), {"s1": row}, ["s1"], RES, 1, credit=set())
    assert _code(e) == SLOT_UNAVAILABLE


def test_blocked_slot_is_slot_unavailable():
    occ = _one_slot(capacity=0)
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), occ, ["s1"], RES, 1, credit=set())
    assert _code(e) == SLOT_UNAVAILABLE


def test_party_larger_than_capacity_is_capacity_exceeded():
    occ = _one_slot(capacity=2, booked=0)
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), occ, ["s1"], RES, 5, credit=set())
    assert _code(e) == CAPACITY_EXCEEDED


def test_slot_just_taken_is_slot_unavailable_with_slot_id_detail():
    # capacity 2, already 2 booked -> no room for a party of 1.
    occ = _one_slot(capacity=2, booked=2)
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), occ, ["s1"], RES, 1, credit=set())
    assert _code(e) == SLOT_UNAVAILABLE
    assert e.value.detail["details"]["slotId"] == "s1"


def test_reschedule_credits_back_the_bookings_own_party():
    # A full slot (capacity 2, booked 2) that this booking already holds: the
    # booking's own 2 seats are credited back, so re-selecting it succeeds.
    occ = _one_slot(capacity=2, booked=2)
    rows = _resolve_selection(_rules(), occ, ["s1"], RES, 2, credit={"s1"})
    assert rows[0]["slot_id"] == "s1"


def test_reschedule_without_credit_would_fail_same_slot():
    occ = _one_slot(capacity=2, booked=2)
    with pytest.raises(HTTPException) as e:
        _resolve_selection(_rules(), occ, ["s1"], RES, 2, credit=set())
    assert _code(e) == SLOT_UNAVAILABLE
