"""Time primitives.

`now_utc()` and `tz_or_utc()` were each written out several times across the
routers — `_now()` in `routers/bookings.py`, `routers/messages.py`,
`routers/owner.py` and `serialize.py`, and `_tz()` in `routers/availability.py`
and `routers/owner.py`. Identical logic in each copy, which is exactly the kind
of thing that drifts: a test that wants to freeze the clock has to find every
definition, and a timezone fallback that changes in one router silently does not
in the next.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    """The current instant, always timezone-aware and always UTC."""
    return datetime.now(timezone.utc)


def tz_or_utc(name: str | None) -> ZoneInfo | timezone:
    """An IANA zone by name, falling back to UTC when absent or unrecognised.

    Never raises: an unknown zone from a client `?tz=` or a stale profile row
    must degrade to UTC, not 500 the request.
    """
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc
