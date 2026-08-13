"""Small builders shared by the backend tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fakes import FakeSupabase


def iso_in(hours: float = 0, minutes: float = 0) -> str:
    """UTC timestamp `hours`/`minutes` from now, PostgREST-style (+00:00)."""
    moment = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)
    return moment.isoformat()


def make_resource(db: FakeSupabase, name: str = "Widget 1", **extra) -> dict:
    return db.insert_row("resources", name=name, **extra)


def make_slot(
    db: FakeSupabase,
    resource_id: str | None = None,
    *,
    hours_ahead: float = 48,
    capacity: int = 1,
    duration_minutes: int = 30,
    starts_at: str | None = None,
    **extra,
) -> dict:
    if resource_id is None:
        resource_id = make_resource(db)["id"]
    start = starts_at if starts_at is not None else iso_in(hours=hours_ahead)
    ends_at = extra.pop(
        "ends_at",
        (datetime.fromisoformat(start) + timedelta(minutes=duration_minutes)).isoformat(),
    )
    return db.insert_row(
        "slots",
        resource_id=resource_id,
        starts_at=start,
        ends_at=ends_at,
        capacity=capacity,
        **extra,
    )


def make_booking(
    db: FakeSupabase,
    slot_id: str,
    *,
    client_email: str = "guest@example.com",
    status: str = "confirmed",
    history: list | None = None,
    **extra,
) -> dict:
    return db.insert_row(
        "bookings",
        slot_id=slot_id,
        client_email=client_email,
        status=status,
        history=history if history is not None else [{"status": status, "at": iso_in()}],
        **extra,
    )


def occupancy_for(db: FakeSupabase, slot_id: str) -> dict:
    """Read the derived slot_occupancy view for one slot."""
    return next(row for row in db.rows("slot_occupancy") if row["slot_id"] == slot_id)
