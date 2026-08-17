#!/usr/bin/env python3
"""Creates dedicated CUSTOMER (never owner) accounts for the benchmark suite,
completely separate from the seeded demo@codaro.app / owner@codaro.app
accounts (backend/seed.py) — so a benchmark run never touches the bookings/
reviews/follows attached to the "real" demo account other people use to look
at the product. Idempotent: an account that already exists is left as-is
(no metadata reset, unlike backend/seed.py's reseed behaviour).

Mirrors the exact Supabase admin-API pattern backend/seed.py uses
(`_ensure_user`: try create_user, on conflict fall back to list_users +
match by email), just against a "bench-customer-N@codaro.bench" address
instead of the demo one, and with `role: "client"` always (this script never
creates an owner/business account).

Run inside the backend container, which already has the `supabase` package
and SUPABASE_URL/SUPABASE_SERVICE_KEY loaded from backend/.env. Called
automatically by lib.sh's ensure_bench_user (every run.sh/run-k6.sh/
run-playwright.sh invocation) — run it directly only to provision the
account by hand:

    docker compose -f ../docker-compose.yml --project-directory .. \
      exec backend python /workspace/benchmark/create_bench_users.py

BENCH_USER_COUNT (default 1) controls how many numbered accounts exist —
raise it only if you parallelize the Playwright matrix across devices and
want each device on its own session.
"""
from __future__ import annotations

import os

from supabase import create_client

BENCH_EMAIL_DOMAIN = "codaro.bench"
BENCH_PASSWORD = os.environ.get("BENCH_PASSWORD", "Codaro-Bench-2026")
BENCH_USER_COUNT = int(os.environ.get("BENCH_USER_COUNT", "1"))


def bench_email(n: int) -> str:
    return f"bench-customer-{n}@{BENCH_EMAIL_DOMAIN}"


def ensure_bench_user(db, email: str, password: str, metadata: dict) -> tuple[str, bool]:
    """Returns (user_id, created). On an existing user, does NOT touch its
    metadata — a benchmark account keeps whatever state prior runs left it in."""
    try:
        resp = db.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True, "user_metadata": metadata}
        )
        return resp.user.id, True
    except Exception:
        for u in db.auth.admin.list_users():
            if getattr(u, "email", None) == email:
                return u.id, False
        raise


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    db = create_client(url, key)

    for n in range(1, BENCH_USER_COUNT + 1):
        email = bench_email(n)
        uid, created = ensure_bench_user(
            db,
            email,
            BENCH_PASSWORD,
            {
                "display_name": f"Benchmark Customer {n}",
                "timezone": "UTC",
                "verified": True,
                "role": "client",
            },
        )
        print(f"{'created' if created else 'exists '}  {email}  ({uid})")


if __name__ == "__main__":
    main()
