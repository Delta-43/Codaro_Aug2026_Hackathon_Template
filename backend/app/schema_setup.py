# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Idempotently applies supabase/schema.sql over a direct Postgres
connection. Guarded so a failure here never crashes the server, startup
just logs and continues (schema.sql may already have been applied by hand)."""
import logging
from pathlib import Path

import psycopg

from app.db import get_db_url

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "supabase" / "schema.sql"


def create_tables_if_configured() -> None:
    db_url = get_db_url()
    if not db_url:
        # Loud on purpose: without a DB URL there is no way to run DDL, so
        # tables are NOT auto-created and seeding will find nothing to seed.
        logger.warning(
            "SUPABASE_DB_URL not set, tables will NOT be auto-created. Set it "
            "to the Supabase session-pooler connection string, or apply "
            "supabase/schema.sql by hand in the Supabase SQL editor."
        )
        return
    try:
        sql = SCHEMA_PATH.read_text()
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                # Freshly created tables stay invisible to PostgREST, and so
                # to the Supabase client the seeder uses, until it reloads
                # its schema cache.
                cur.execute("NOTIFY pgrst, 'reload schema'")
            conn.commit()
        logger.info("Schema applied from %s (idempotent).", SCHEMA_PATH)
    except Exception:
        logger.exception(
            "Schema setup FAILED, tables may be missing and seeding will be "
            "skipped. Verify SUPABASE_DB_URL (use the session-pooler string, "
            "not the IPv6-only direct host)."
        )
