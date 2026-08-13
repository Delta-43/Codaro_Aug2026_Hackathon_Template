"""Truncates resources/slots/bookings (cascading) then re-runs seed() with
the current config. Deletes all existing data -- run only when a fresh,
domain-matching demo dataset is wanted after a pivot."""
import psycopg

from app.db import get_db_url
from seed import seed


def reseed() -> None:
    db_url = get_db_url()
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set to reseed.")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate table bookings, slots, resources cascade;")
        conn.commit()
    seed()


if __name__ == "__main__":
    reseed()
