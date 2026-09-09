#!/usr/bin/env python3
# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Exit 0 if a seed currently holds the seed lock, 1 otherwise.

`make reseed` runs INSIDE the backend container, so `make reload`, which
restarts that container, kills a reseed in flight and leaves a half-built
dataset with no error anyone sees. The lock is the one reliable signal that a
seed is running, so `reload` checks it rather than guessing.

Exits 1 (safe to proceed) whenever the answer is unknown: no DB URL, an
unreachable database, an import failure. A guard that blocks on its own
malfunction is worse than the hazard it guards.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

try:
    import psycopg
    from app.db import get_db_url
    from seed import _SEED_LOCK_KEY

    url = get_db_url()
    if not url:
        sys.exit(1)
    with psycopg.connect(url, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute(
            "select count(*) from pg_locks where locktype = 'advisory' and objid = %s",
            (_SEED_LOCK_KEY,),
        )
        sys.exit(0 if cur.fetchone()[0] else 1)
except Exception:
    sys.exit(1)
