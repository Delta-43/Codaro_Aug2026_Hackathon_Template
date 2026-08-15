#!/usr/bin/env python3
"""Manual live-stack smoke test for auth + per-user isolation (RLS).

NOT part of the pytest suite (that lives in test/ and is owned by the
test-writer agent). This hits a *running* backend and a *real* Supabase project
with two real user logins and asserts that one client cannot see or touch
another's bookings — i.e. that the user-JWT-scoped client + RLS actually enforce.

Usage:
    export API_BASE=http://localhost:8000            # backend under test
    export SUPABASE_URL=https://<ref>.supabase.co
    export SUPABASE_ANON_KEY=<anon public key>
    export SMOKE_A_EMAIL=alice@example.com  SMOKE_A_PASSWORD=...
    export SMOKE_B_EMAIL=bob@example.com    SMOKE_B_PASSWORD=...
    python backend/smoke_auth.py

Both users must already exist (sign them up via the app or the Supabase
dashboard) and there must be at least one open, future slot to book. Exit code
0 = all checks passed, non-zero = a failure (details printed).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_BASE = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")

_passed = 0
_failed = 0


def _check(ok: bool, label: str, detail: str = "") -> None:
    global _passed, _failed
    mark = "PASS" if ok else "FAIL"
    if ok:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


def _request(method: str, url: str, token: str | None = None, body: dict | None = None):
    """Return (status, parsed_json_or_text). Never raises on HTTP error status."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def sign_in(email: str, password: str) -> str:
    """Exchange email/password for a Supabase access token (JWT)."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    req = urllib.request.Request(
        url, data=json.dumps({"email": email, "password": password}).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("apikey", ANON)
    try:
        with urllib.request.urlopen(req) as resp:
            token = json.loads(resp.read().decode()).get("access_token")
    except urllib.error.HTTPError as e:
        sys.exit(f"Sign-in failed for {email}: {e.code} {e.read().decode()}")
    if not token:
        sys.exit(f"Sign-in for {email} returned no access_token")
    return token


def pick_open_slot(token: str) -> str:
    """First slot with room whose start is in the future."""
    status, rows = _request("GET", f"{API_BASE}/slots/occupancy", token=token)
    if status != 200 or not isinstance(rows, list):
        sys.exit(f"Could not list slot occupancy: {status} {rows}")
    now = datetime.now(timezone.utc)
    future_open = [
        r for r in rows
        if r.get("available_count", 0) > 0
        and datetime.fromisoformat(r["starts_at"]) > now
    ]
    if not future_open:
        sys.exit("No open, future slot to book — create one (as an owner) first.")
    future_open.sort(key=lambda r: r["starts_at"])
    return future_open[0]["slot_id"]


def main() -> int:
    if not (SUPABASE_URL and ANON):
        sys.exit("Set SUPABASE_URL and SUPABASE_ANON_KEY (see this file's docstring).")
    creds = {k: os.environ.get(k) for k in
             ("SMOKE_A_EMAIL", "SMOKE_A_PASSWORD", "SMOKE_B_EMAIL", "SMOKE_B_PASSWORD")}
    if not all(creds.values()):
        sys.exit(f"Missing creds: {[k for k, v in creds.items() if not v]}")

    print(f"Backend: {API_BASE}\nSupabase: {SUPABASE_URL}\n")
    token_a = sign_in(creds["SMOKE_A_EMAIL"], creds["SMOKE_A_PASSWORD"])
    token_b = sign_in(creds["SMOKE_B_EMAIL"], creds["SMOKE_B_PASSWORD"])
    print("Signed in both users.\n")

    # 0. Unauthenticated access is rejected.
    status, _ = _request("GET", f"{API_BASE}/bookings")
    _check(status == 401, "no token -> 401 on GET /bookings", f"got {status}")

    # 1. Client A books an open slot.
    slot_id = pick_open_slot(token_a)
    status, created = _request("POST", f"{API_BASE}/bookings", token=token_a,
                               body={"slot_id": slot_id})
    ok = status == 200 and isinstance(created, list) and created
    _check(bool(ok), "client A creates a booking", f"status {status}: {created}")
    if not ok:
        return _summary()
    booking = created[0]
    booking_id = booking["id"]
    _check(booking.get("client_email") == creds["SMOKE_A_EMAIL"].lower(),
           "booking client_email derived from A's token (not the body)",
           f"got {booking.get('client_email')}")

    # 2. A sees the booking; B does not.
    _, a_list = _request("GET", f"{API_BASE}/bookings", token=token_a)
    _check(any(b["id"] == booking_id for b in (a_list or [])),
           "A's GET /bookings includes A's booking")
    _, b_list = _request("GET", f"{API_BASE}/bookings", token=token_b)
    _check(not any(b["id"] == booking_id for b in (b_list or [])),
           "B's GET /bookings does NOT include A's booking (isolation)",
           f"B sees {len(b_list or [])} booking(s)")

    # 3. B cannot cancel A's booking (RLS / own-or-owner) — expect 403 or 404.
    status, detail = _request("POST", f"{API_BASE}/bookings/{booking_id}/cancel", token=token_b)
    _check(status in (403, 404), "B cannot cancel A's booking", f"got {status}: {detail}")

    # 4. A's booking is still active after B's attempt.
    _, a_list2 = _request("GET", f"{API_BASE}/bookings", token=token_a)
    still = next((b for b in (a_list2 or []) if b["id"] == booking_id), None)
    _check(bool(still) and still.get("status") != "cancelled",
           "A's booking survived B's cancel attempt",
           f"status={still and still.get('status')}")

    # Cleanup: A cancels their own booking (best effort).
    _request("POST", f"{API_BASE}/bookings/{booking_id}/cancel", token=token_a)
    return _summary()


def _summary() -> int:
    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
