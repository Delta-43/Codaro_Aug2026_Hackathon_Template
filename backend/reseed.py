# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Wipe + rebuild the demo dataset.

Fully wipes the extended + booking tables (keeping profiles / auth.users) and
rebuilds them. Deletes all existing demo data.

The spec comes from `seed_config.spec_from_config()`, so the rebuilt data
follows the loaded `domain.config.json`: its currency, timezone, durations,
prices, cutoffs, capacity and -- in single-tenant mode -- its
`tenancy.providerCode`. `scripts/check_seed.py` (`make checkseed`) verifies it."""
import logging

from app.db import get_db_url
from seed import seed_from_config


def reseed() -> None:
    if not get_db_url():
        raise SystemExit("SUPABASE_DB_URL must be set to reseed.")
    seed_from_config()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reseed()
