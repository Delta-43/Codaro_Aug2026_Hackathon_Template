"""Demo data seeding. Domain-aware: names rows from the *current*
domain.config.json (e.g. medical config -> "Doctor 1..3"). Run directly to
force-insert another batch; `seed_if_empty` is what startup calls
automatically, and only when the DB has zero resources."""
from datetime import datetime, timedelta, timezone

from app.config import get_config
from app.db import get_supabase


def seed() -> None:
    db = get_supabase()
    config = get_config()
    resource_term = config["terms"]["resource"]
    slot_minutes = config["rules"]["slotDurationMinutes"]
    capacity = config["rules"]["maxBookingsPerSlot"]

    for i in range(1, 4):
        resource = (
            db.table("resources")
            .insert({"name": f"{resource_term} {i}", "metadata": {}})
            .execute()
            .data[0]
        )
        start = datetime.now(timezone.utc) + timedelta(days=1)
        for j in range(5):
            slot_start = start + timedelta(hours=j)
            db.table("slots").insert(
                {
                    "resource_id": resource["id"],
                    "starts_at": slot_start.isoformat(),
                    "ends_at": (slot_start + timedelta(minutes=slot_minutes)).isoformat(),
                    "capacity": capacity,
                    "metadata": {},
                }
            ).execute()


def seed_if_empty() -> None:
    db = get_supabase()
    existing = db.table("resources").select("id").limit(1).execute().data
    if existing:
        return
    seed()


if __name__ == "__main__":
    seed()
