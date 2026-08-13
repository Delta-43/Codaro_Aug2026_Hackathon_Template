"""Idempotently applies supabase/schema.sql over a direct Postgres
connection. Guarded so a failure here never crashes the server — startup
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
        logger.info("SUPABASE_DB_URL not set — skipping schema setup.")
        return
    try:
        sql = SCHEMA_PATH.read_text()
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        logger.info("Schema applied (idempotent).")
    except Exception:
        logger.exception("Schema setup failed — continuing startup anyway.")
