"""Wipe + reseed the demo dataset to match the current domain.config.json.

Delegates to `seed_vertical()`, which fully wipes the extended + booking tables
(keeping profiles / auth.users) and rebuilds them. The vertical reseeded is the
one currently in the DB (`active_vertical()`), falling back to the default on a
fresh/empty DB. Deletes all existing demo data -- run only when a fresh,
domain-matching dataset is wanted after a pivot."""
import logging

from app.db import get_db_url
from seed import active_vertical, seed_vertical


def reseed() -> None:
    if not get_db_url():
        raise SystemExit("SUPABASE_DB_URL must be set to reseed.")
    seed_vertical(active_vertical())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reseed()
