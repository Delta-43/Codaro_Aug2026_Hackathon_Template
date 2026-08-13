"""Supabase client + optional direct Postgres connection for schema setup."""
import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_db_url() -> str | None:
    """Direct Postgres connection string, used only for schema setup/seeding
    (SUPABASE_DB_URL). Optional — if unset, schema.sql must be run manually."""
    return os.environ.get("SUPABASE_DB_URL")
