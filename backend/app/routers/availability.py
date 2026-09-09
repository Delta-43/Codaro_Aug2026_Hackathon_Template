# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Availability grouping + month density, the calendar's two read endpoints.

Both group slots by *local* date in the viewer's timezone (from `?tz=`, else the
signed-in user's `user_metadata.timezone`, else the business's own
`location.timezone`, else UTC). Slot status and occupancy
are computed server-side (the UI never recomputes them). Reads use the service
key (public); occupancy already reflects party-size + multi-slot holds.
"""
from __future__ import annotations

import calendar as _cal
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from app.clock import now_utc, tz_or_utc
from app.auth import AuthUser, optional_user
from app.db import fetch_all, get_supabase, maybe_row
from app.rules import closure_reason, effective_service_config
from app.serialize import _parse, serialize_slot
from app.users import user_metadata

router = APIRouter(tags=["availability"])


def _viewer_tz(tz: str | None, user: AuthUser | None, load_service=lambda: None):
    """`?tz=` -> the signed-in user's timezone -> the BUSINESS's timezone -> UTC.

    The third step is new. Without it an anonymous visitor always saw days
    grouped in UTC, which silently shifts every evening slot into the next day
    for a business east of Greenwich, the calendar looked wrong to exactly the
    people who had not logged in yet.

    "The business" means THIS service's business. Both endpoints here are already
    scoped to one `service_id`, and `location` is overridable per service, but the
    global block was read regardless, so pricing honoured a tenant's timezone
    (`bookings._business_tz`) while the calendar next to it did not, and every
    marketplace tenant off the platform zone had its days grouped wrong."""
    name = tz or (user_metadata(user).get("timezone") if user else None)
    # Only reach for the service when the first two steps missed. `load_service`
    # is a thunk, not a row: passing the row meant the SELECT ran on every
    # request, and the client never sends `?tz=`, so for any signed-in viewer,
    # the whole `(app)` group is auth-gated, the row was fetched and discarded
    # on the two most interaction-heavy endpoints in the app.
    if not name:
        name = effective_service_config(load_service())["location"].get("timezone")
    return tz_or_utc(name or "UTC")


def _service(db, service_id: str) -> dict | None:
    return maybe_row(db.table("services").select("*").eq("id", service_id))


def _norm_ts(value: str) -> str:
    """Canonicalise an incoming ISO timestamp. Tolerates the classic
    unencoded-'+' footgun (a '+00:00' offset arriving as a space) so a bad query
    string becomes a clean value rather than a Postgres 22007."""
    try:
        return _parse(value.replace(" ", "+")).isoformat()
    except Exception:
        return value


def _resource_ids(db, service_id: str, resource_id: str | None) -> list[str]:
    rows = db.table("resources").select("id,metadata").execute().data or []
    ids = [r["id"] for r in rows if (r.get("metadata") or {}).get("service_id") == service_id]
    if resource_id:
        ids = [rid for rid in ids if rid == resource_id]
    return ids


def _occ_to_slot(r: dict, service_id: str, now: datetime) -> dict:
    slot = {
        "id": r["slot_id"],
        "resource_id": r["resource_id"],
        "starts_at": r["starts_at"],
        "ends_at": r["ends_at"],
        "capacity": r["capacity"],
        "metadata": {"service_id": service_id},
    }
    return serialize_slot(slot, booked_count=r["booked_count"], service_id=service_id, now=now)


@router.get("/availability")
def availability(
    service_id: str,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    resource_id: str | None = None,
    tz: str | None = None,
    user: AuthUser | None = Depends(optional_user),
):
    db = get_supabase()
    # Fetched once: the viewer-timezone fallback and the closure test below both
    # need it, and it used to be loaded twice on the busiest read in the app.
    service = _service(db, service_id)
    tzinfo = _viewer_tz(tz, user, lambda: service)
    rids = _resource_ids(db, service_id, resource_id)
    if not rids:
        return []
    # Date-bounded, so this is far less exposed than `/slots`, but a wide
    # range on a busy multi-resource service still passes 1000 rows, and a
    # truncated day reads as "no availability" rather than as an error.
    rows = fetch_all(
        db.table("slot_occupancy")
        .select("*")
        .in_("resource_id", rids)
        .gte("starts_at", _norm_ts(from_))
        .lt("starts_at", _norm_ts(to)),
        # The view has no `id`; see the note in routers/slots.py.
        order="slot_id",
    )
    now = now_utc()
    # A day the business has declared shut (`timing.blackouts` / outside
    # `timing.seasons`) carries no availability. Tested against the BUSINESS's
    # calendar even though the grouping below is the viewer's, because a closure
    # is the business's own date.
    days: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if closure_reason(r["starts_at"], service):
            continue
        local_date = _parse(r["starts_at"]).astimezone(tzinfo).strftime("%Y-%m-%d")
        days[local_date].append(r)

    out = []
    for date in sorted(days):
        entries = sorted(days[date], key=lambda r: _parse(r["starts_at"]))
        out.append(
            {
                "date": date,
                "slots": [_occ_to_slot(r, service_id, now) for r in entries],
                "totalCapacity": sum(r["capacity"] for r in entries),
                "totalBooked": sum(r["booked_count"] for r in entries),
            }
        )
    return out


@router.get("/month-density")
def month_density(
    service_id: str,
    month: str,  # 'YYYY-MM'
    resource_id: str | None = None,
    tz: str | None = None,
    user: AuthUser | None = Depends(optional_user),
):
    db = get_supabase()
    service = _service(db, service_id)
    tzinfo = _viewer_tz(tz, user, lambda: service)
    year, mon = int(month[:4]), int(month[5:7])
    days_in = _cal.monthrange(year, mon)[1]

    rids = _resource_ids(db, service_id, resource_id)
    rows = []
    if rids:
        # Window the local month (± a day for tz edges) back to a UTC range.
        start_local = datetime(year, mon, 1, tzinfo=tzinfo)
        end_local = datetime(year, mon, days_in, 23, 59, 59, tzinfo=tzinfo)
        lo = (start_local - timedelta(days=1)).astimezone(timezone.utc).isoformat()
        hi = (end_local + timedelta(days=1)).astimezone(timezone.utc).isoformat()
        rows = (
            db.table("slot_occupancy")
            .select("*")
            .in_("resource_id", rids)
            .gte("starts_at", lo)
            .lte("starts_at", hi)
            .execute()
            .data
            or []
        )

    now = now_utc()
    total_by: dict[str, int] = defaultdict(int)
    remaining_by: dict[str, int] = defaultdict(int)
    for r in rows:
        # Same closure test as the day view, so the month heatmap and the day it
        # opens agree about which days are shut.
        if closure_reason(r["starts_at"], service):
            continue
        d = _parse(r["starts_at"]).astimezone(tzinfo).strftime("%Y-%m-%d")
        total_by[d] += r["capacity"]
        end = _parse(r["ends_at"])
        free = max(0, r["capacity"] - r["booked_count"]) if (end > now and r["capacity"] > 0) else 0
        remaining_by[d] += free

    out = []
    for day in range(1, days_in + 1):
        d = f"{year:04d}-{mon:02d}-{day:02d}"
        total, remaining = total_by.get(d, 0), remaining_by.get(d, 0)
        if total == 0 or remaining == 0:
            density = 0
        else:
            ratio = remaining / total
            density = 1 if ratio < 0.34 else 2 if ratio < 0.67 else 3
        out.append({"date": d, "density": density})
    return out
