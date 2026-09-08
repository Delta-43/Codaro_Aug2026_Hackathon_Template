# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Domain-aware seeding for the three demo verticals (fleet / oneToOne / group).

Ports `frontend/src/api/seed/*` to the backend: it turns the declarative
`seed_data.VERTICALS` config into real DB rows — providers, services, resources,
DST-aware slot grids, edge-case occupancy (a blocked day, a fully-booked day, a
one-seat-left slot), plus a demo user's seed bookings + a review + a follow.

Auth users provisioned via the Supabase admin API:
  * the **demo user** (login below) owns the seed bookings/reviews/follows.
  * a **holds user** owns the "someone else already booked" occupancy so full /
    partial slots are real (occupancy is derived from confirmed bookings).
  * the **owner** (`owner@codaro.app`) owns the demo provider, so the business
    dashboard is populated; the primary service is manual-approve.
  * a **prospect** (`prospect@codaro.app`) — a fresh client whose pending
    request appears in the owner's Requests tab.

`seed_if_empty()` seeds the default vertical when no providers exist. It is no
longer called on startup — the app serves only real Supabase data; run it (or
`make reseed`) manually to populate demo data. `seed_vertical(id)` is the
destructive reseed used by `reseed.py` and the demo vertical-switch endpoint.
"""
from __future__ import annotations

import logging
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psycopg
from postgrest.exceptions import APIError

from app.db import get_db_url, get_supabase
from app.references import booking_reference
from seed_data import DEFAULT_VERTICAL, VERTICALS

logger = logging.getLogger(__name__)

# Demo credentials — surfaced to the operator so they can log in and see the
# seeded bookings. (Anyone can also register their own empty account.)
DEMO_EMAIL = "demo@codaro.app"
DEMO_PASSWORD = "Codaro-Demo-2026"
OWNER_EMAIL = "owner@codaro.app"
OWNER_PASSWORD = "Codaro-Owner-2026"
# A fresh prospective client — appears in the owner's Requests tab as a new
# member (little history), the counterpart to the established demo user.
PROSPECT_EMAIL = "prospect@codaro.app"
PROSPECT_PASSWORD = "Codaro-Prospect-2026"
_HOLDS_EMAIL = "holds@codaro.app"
_HOLDS_PASSWORD = secrets.token_urlsafe(18)

_MINUTE = 60
_HOUR = 3600

BOOKING_MODEL_TO_VERTICAL = {
    "unit_selection": "fleet",
    "one_to_one": "oneToOne",
    "shared_capacity": "group",
}

_EXTENDED_TABLES = [
    "messages",       # child of conversations
    "conversations",  # child of providers
    "booking_slots",
    "reviews",
    "bookings",
    "follows",
    "slots",
    "resources",
    "services",
    "providers",
]


# --- deterministic inline-SVG imagery (ported from seed/common.ts) ---------


def _hash(s: str) -> int:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _svg_uri(svg: str) -> str:
    return "data:image/svg+xml," + quote(" ".join(svg.split()))


def _initials(name: str) -> str:
    parts = [p for p in "".join(c if c.isalnum() or c == " " else "" for c in name).split() if p]
    a = parts[0][0] if parts else "?"
    b = parts[-1][0] if len(parts) > 1 else (parts[0][1:2] if parts else "")
    return (a + b).upper()


def avatar_uri(seed: str, label: str) -> str:
    hue = _hash(seed) % 360
    hue2 = (hue + 40) % 360
    return _svg_uri(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue} 60% 55%)"/>'
        f'<stop offset="1" stop-color="hsl({hue2} 62% 42%)"/></linearGradient></defs>'
        f'<rect width="160" height="160" rx="80" fill="url(#g)"/>'
        f'<text x="80" y="98" font-family="system-ui, sans-serif" font-size="62" '
        f'font-weight="600" fill="white" text-anchor="middle">{_initials(label)}</text></svg>'
    )


def cover_uri(seed: str) -> str:
    hue = _hash(seed) % 360
    hue2 = (hue + 60) % 360
    return _svg_uri(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue} 55% 46%)"/>'
        f'<stop offset="1" stop-color="hsl({hue2} 58% 34%)"/></linearGradient></defs>'
        f'<rect width="960" height="360" fill="url(#g)"/>'
        f'<circle cx="820" cy="70" r="180" fill="white" opacity="0.06"/>'
        f'<circle cx="120" cy="320" r="220" fill="black" opacity="0.08"/></svg>'
    )


def tile_uri(seed: str, label: str) -> str:
    hue = _hash(seed) % 360
    return _svg_uri(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue} 45% 52%)"/>'
        f'<stop offset="1" stop-color="hsl({(hue + 30) % 360} 48% 38%)"/></linearGradient></defs>'
        f'<rect width="640" height="420" fill="url(#g)"/>'
        f'<text x="32" y="392" font-family="system-ui, sans-serif" font-size="34" '
        f'font-weight="600" fill="white" opacity="0.9">{label}</text></svg>'
    )


# --- time helpers ----------------------------------------------------------


def _wall_to_utc(y: int, m: int, d: int, hour: int, minute: int, tz: str) -> datetime:
    """A wall-clock time in `tz` as a true UTC instant (DST-aware)."""
    return datetime(y, m, d, hour, minute, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def _local_days(tz: str, back: int, forward: int, step: int = 1):
    """Local calendar days across the window, every `step`-th day.

    `step` > 1 is how a multi-day unit (a week, a month) lays one slot per unit
    instead of one per day. Anchored on today, so the sequence is stable no
    matter how far back the window reaches."""
    today = datetime.now(ZoneInfo(tz)).date()
    for i in range(-back, forward + 1, max(1, step)):
        day = today + timedelta(days=i)
        yield day, day.isoweekday() % 7  # 0=Sun … 6=Sat (JS getUTCDay convention)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_utc(iso: str) -> datetime:
    """Parse a stored timestamp as UTC-aware, so it can be compared with `now`.
    Postgres hands back an offset; a naive value would raise on subtraction."""
    dt = datetime.fromisoformat(iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _local_date_str(iso: str, tz: str) -> str:
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")


# --- DB helpers ------------------------------------------------------------


def _chunked_insert(db, table: str, rows: list[dict], chunk: int = 500) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(rows), chunk):
        out += db.table(table).insert(rows[i : i + chunk]).execute().data or []
    return out


# One seeder at a time, enforced by Postgres rather than by convention.
#
# Seeding is a TRUNCATE on a direct connection followed by hundreds of inserts
# through PostgREST, which is not one transaction and not one connection. Two
# seeders overlapping therefore corrupt each other: the documented workflow
# (`make reload` restarting the backend while `make reseed` runs) has startup's
# `seed_if_empty` read an empty `providers` mid-wipe and start its own seed, and
# whichever one truncates second deletes rows the other is still referencing —
# surfacing as `services_provider_id_fkey` / `reviews_provider_id_fkey`
# violations against a provider that was inserted seconds earlier.
#
# An advisory lock is session-scoped, so the connection is held open for the
# whole seed and released when it closes — including on a crash, which a table
# flag would not survive.
_SEED_LOCK_KEY = 0x0C0DA205  # arbitrary but stable; "codaro seed"


@contextmanager
def seed_lock(*, wait: bool = True):
    """Serialise seeding. Yields True when the lock is held, False when another
    seeder has it and `wait=False` — the caller should then do nothing.

    Without `SUPABASE_DB_URL` there is no way to take the lock, so it yields
    True and says so once: a deployment with no direct connection cannot wipe
    either, so the concurrent case does not arise there.
    """
    url = get_db_url()
    if not url:
        logger.warning("No SUPABASE_DB_URL — seeding is not serialised.")
        yield True
        return
    conn = psycopg.connect(url)
    # Bound before the try so the finally's `if held` can't NameError (masking
    # the real error) when lock acquisition itself raises before `held` is set.
    held = False
    try:
        with conn.cursor() as cur:
            if wait:
                cur.execute("select pg_advisory_lock(%s)", (_SEED_LOCK_KEY,))
                held = True
            else:
                cur.execute("select pg_try_advisory_lock(%s)", (_SEED_LOCK_KEY,))
                held = bool(cur.fetchone()[0])
        conn.commit()
        yield held
    finally:
        # Closing the session drops the lock; explicit unlock keeps the intent
        # obvious and releases it fractionally sooner.
        try:
            if held:
                with conn.cursor() as cur:
                    cur.execute("select pg_advisory_unlock(%s)", (_SEED_LOCK_KEY,))
                conn.commit()
        except Exception:
            logger.exception("Could not release the seed lock (session close will).")
        conn.close()


def _wipe(db) -> None:
    """Truncate the extended + booking data (keeps profiles / auth.users)."""
    url = get_db_url()
    if url:
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                f"truncate {', '.join(_EXTENDED_TABLES)} restart identity cascade"
            )
            conn.commit()
        return
    # Fallback: REST deletes (no direct DB URL configured).
    for table in _EXTENDED_TABLES:
        key = "booking_id" if table == "booking_slots" else ("user_id" if table == "follows" else "id")
        db.table(table).delete().neq(key, "00000000-0000-0000-0000-000000000000").execute()


def _ensure_user(db, email: str, password: str, metadata: dict) -> str:
    """Create (or find) a Supabase auth user; return its id. On an existing user
    the profile metadata is reset to the seed values, so a reseed restores the
    demo user to a pristine state."""
    try:
        resp = db.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True, "user_metadata": metadata}
        )
        return resp.user.id
    except Exception:
        # Already exists — locate by email and reset its metadata.
        try:
            for u in db.auth.admin.list_users():
                if getattr(u, "email", None) == email:
                    try:
                        db.auth.admin.update_user_by_id(u.id, {"user_metadata": metadata})
                    except Exception:
                        pass
                    return u.id
        except Exception:
            logger.exception("Could not resolve existing user %s", email)
        raise


# --- the assembler ---------------------------------------------------------


def seed_vertical(vertical_id: str, spec: dict | None = None) -> dict:
    """Wipe and reseed the DB from a vertical spec. Returns a small summary.

    `spec` overrides the `seed_data.VERTICALS` entry — that is how
    `seed_from_config()` feeds in a spec derived from `domain.config.json`
    instead. The assembler below reads only the spec, so both sources go through
    exactly the same code path."""
    with seed_lock() as held:   # waits: an explicit reseed should happen, not skip
        assert held
        return _seed_vertical_locked(vertical_id, spec)


def _seed_vertical_locked(vertical_id: str, spec: dict | None = None) -> dict:
    cfg = spec or VERTICALS[vertical_id]
    tz = cfg["baseTz"]
    currency = cfg["currency"]
    model = cfg["bookingModel"]
    db = get_supabase()

    _wipe(db)
    demo_uid = _ensure_user(
        db, DEMO_EMAIL, DEMO_PASSWORD,
        {"display_name": "Mara Lindqvist", "timezone": tz, "verified": True, "role": "client"},
    )
    holds_uid = _ensure_user(
        db, _HOLDS_EMAIL, _HOLDS_PASSWORD,
        {"display_name": "Guest", "timezone": tz, "verified": True, "role": "client"},
    )
    # The demo owner owns the demo provider (index 0), so logging in as the owner
    # shows a populated dashboard (its services/units/occupancy) rather than a
    # blank slate.
    owner_uid = _ensure_user(
        db, OWNER_EMAIL, OWNER_PASSWORD,
        {"display_name": "Olga Owner", "timezone": tz, "verified": True, "role": "owner"},
    )
    prospect_uid = _ensure_user(
        db, PROSPECT_EMAIL, PROSPECT_PASSWORD,
        {"display_name": "Pedro Prospect", "timezone": tz, "verified": False, "role": "client"},
    )

    counts = {"providers": 0, "services": 0, "resources": 0, "slots": 0, "bookings": 0}
    demo_provider_id = None
    primary_service = None  # (service_id, resource rows, dur, cutoff, price)
    provider_ids: list[str] = []

    def add_service(
        provider_id: str, spec: dict, resources: list[dict], owner_id: str | None = None,
        auto_approve: bool = True,
    ) -> tuple[str, list[dict]]:
        svc = db.table("services").insert({
            "provider_id": provider_id,
            "name": spec["name"],
            "description": spec["description"],
            "booking_model": model,
            "slot_duration_minutes": spec["slotDurationMinutes"],
            "min_slots_per_booking": spec["minSlotsPerBooking"],
            "max_slots_per_booking": spec["maxSlotsPerBooking"],
            "price_minor_units": spec["priceMinorUnits"],
            "currency": currency,
            "cancellation_cutoff_hours": spec["cancellationCutoffHours"],
            # auto_approve rides in metadata (no column): the demo's primary
            # service is manual-approve so the Requests tab has something to act on.
            "metadata": {
                **(spec.get("metaFields", {}).get("service") or {}),
                "image_url": tile_uri(spec["name"], spec["name"]),
                "auto_approve": auto_approve,
            },
        }).execute().data[0]
        counts["services"] += 1
        service_id = svc["id"]
        dur = spec["slotDurationMinutes"]
        grid = spec["grid"]

        res_rows: list[dict] = []
        slot_rows: list[dict] = []
        for r in resources:
            res_md = {
                **(spec.get("metaFields", {}).get("resource") or {}),
                "service_id": service_id,
                "capacity": r["capacity"],
                "active": True,
                "attributes": r["attributes"],
                "image_url": tile_uri(service_id + r["name"], r["name"]),
            }
            if owner_id:  # so the demo owner can manage (add slots to) these units
                res_md["owner_id"] = owner_id
            res = db.table("resources").insert({
                "name": r["name"],
                "description": r.get("description"),
                "metadata": res_md,
            }).execute().data[0]
            counts["resources"] += 1
            res_rows.append({**res, "_capacity": r["capacity"]})
            for day, weekday in _local_days(
                tz, grid["daysBack"], grid["daysForward"], grid.get("dayStep", 1)
            ):
                if "weekdays" in grid and weekday not in grid["weekdays"]:
                    continue
                for t in grid["startTimes"]:
                    start = _wall_to_utc(day.year, day.month, day.day, t["hour"], t["minute"], tz)
                    end = start + timedelta(minutes=dur)
                    slot_rows.append({
                        "resource_id": res["id"],
                        "starts_at": _iso(start),
                        "ends_at": _iso(end),
                        "capacity": r["capacity"],
                        "metadata": {
                            **(spec.get("metaFields", {}).get("slot") or {}),
                            "service_id": service_id,
                        },
                    })
        inserted_slots = _chunked_insert(db, "slots", slot_rows)
        counts["slots"] += len(inserted_slots)
        return service_id, res_rows

    # providers + services
    for i, p in enumerate(cfg["providers"]):
        prov = db.table("providers").insert({
            "name": p["name"],
            "public_code": p["publicCode"],
            "category_id": p["categoryId"],
            "owner_id": owner_uid if i == 0 else None,  # demo owner owns the demo provider
            "metadata": {
                # Provenance, so a checker reads what this data was built from
                # instead of inferring it from the shape of the rows (which is
                # how `active_vertical()` guesses, and it can only ever return
                # one of the three canned verticals).
                "seeded": {
                    "source": vertical_id,
                    "tz": tz,
                    "currency": currency,
                    "bookingModel": model,
                },
                "avatar_url": avatar_uri(p["name"], p["name"]),
                "cover_url": cover_uri(p["name"]),
                "tagline": p["tagline"],
                "bio": p["bio"],
                "location": {"city": p["city"], "country": p["country"], "lat": p["lat"], "lng": p["lng"]},
                "links": p.get("links") or [],
                "rating": p["rating"],
                "review_count": p["reviewCount"],
            },
        }).execute().data[0]
        counts["providers"] += 1
        provider_ids.append(prov["id"])
        if i == 0:
            demo_provider_id = prov["id"]
            for si, spec in enumerate(cfg["demoServices"]):
                # The primary service is manual-approve so incoming requests wait
                # in the owner's Requests tab; the rest auto-approve.
                sid, res_rows = add_service(
                    prov["id"], spec, spec["resources"],
                    owner_id=owner_uid, auto_approve=si != 0,
                )
                if si == 0:
                    primary_service = {"id": sid, "spec": spec, "resource": res_rows[0], "resources": res_rows}
        else:
            t = cfg["simpleService"]
            add_service(prov["id"], t, [t["resource"]])

    # occupancy edge cases + demo bookings on the primary demo service
    if primary_service:
        edge_holds, edge_slots = _inject_edge_cases(
            db, primary_service, tz, holds_uid, demo_provider_id, currency
        )
        counts["bookings"] += edge_holds
        counts["bookings"] += _seed_bookings(
            db, primary_service, demo_provider_id, demo_uid, DEMO_EMAIL, model, currency, tz,
            reserved=edge_slots,
        )
        # Pending requests waiting on the owner (Requests tab): one from the
        # established demo user, one from a fresh prospect.
        counts["bookings"] += _seed_requests(
            db, primary_service, demo_provider_id, model, currency,
            [(demo_uid, DEMO_EMAIL), (prospect_uid, PROSPECT_EMAIL)], tz,
        )
        # The demo user's reputation: reviews the provider left about them.
        _seed_client_reviews(db, demo_uid, demo_provider_id)
        # Working chat threads so both demo logins land on a populated inbox.
        counts["messages"] = _seed_messages(db, demo_provider_id, demo_uid, owner_uid, provider_ids)

    # demo user follows the second provider
    if len(provider_ids) > 1:
        try:
            db.table("follows").insert({"user_id": demo_uid, "provider_id": provider_ids[1]}).execute()
        except Exception:
            pass

    logger.info("Seeded vertical %s: %s", vertical_id, counts)
    return {"verticalId": vertical_id, **counts}


def _insert_dedicated_slot(db, service_id, resource_id, capacity, start: datetime, dur: int) -> dict:
    end = start + timedelta(minutes=dur)
    return db.table("slots").insert({
        "resource_id": resource_id,
        "starts_at": _iso(start),
        "ends_at": _iso(end),
        "capacity": capacity,
        "metadata": {"service_id": service_id},
    }).execute().data[0]


def _align_to_unit_grid(start: datetime, dur: int, tz: str) -> datetime:
    """Snap `start` onto the same lattice `seed_config._grid` lays down: local
    midnight, every `dur // 1440` days, anchored on today. Slots built off this
    tile the calendar exactly, so consecutive units abut instead of overlapping."""
    zone = ZoneInfo(tz)
    today = datetime.now(zone).date()
    step = max(1, dur // 1440)
    offset = (start.astimezone(zone).date() - today).days
    aligned = today + timedelta(days=(round(offset / step) * step))
    return _wall_to_utc(aligned.year, aligned.month, aligned.day, 0, 0, tz)


def _slot_for_booking(db, service_id, resource_id, capacity, start: datetime, dur: int,
                      used: set[str], tz: str) -> dict:
    """The slot a demo lifecycle booking should occupy.

    Below a day the grid is dense and a dedicated slot sits harmlessly between
    two grid ones, so each booking keeps getting its own. From a day upward the
    grid holds exactly ONE slot per unit, and a dedicated slot at an arbitrary
    time necessarily overlaps the grid slot around it — the resource then reads
    as double-booked and its occupancy is wrong. So reuse the nearest grid slot
    instead, skipping any already taken by an earlier booking.

    Falls back to a dedicated insert when nothing is in range — the lifecycle
    bookings reach past both ends of the seeded window — but aligns it to the
    same lattice first. An unaligned fallback landing just beyond the grid's
    forward edge still overlaps the last grid slot, which is most of what this
    function exists to prevent.
    """
    if dur < 1440:
        return _insert_dedicated_slot(db, service_id, resource_id, capacity, start, dur)
    window = timedelta(minutes=dur)
    rows = (
        db.table("slots").select("*").eq("resource_id", resource_id)
        .gte("starts_at", _iso(start - window)).lte("starts_at", _iso(start + window))
        .execute().data
        or []
    )
    # `capacity: 0` is how `_inject_edge_cases` marks a blocked day, and a slot
    # already spoken for cannot take another booking. Either one would trip the
    # DB capacity check the moment the booking is inserted.
    free = [r for r in rows if r["id"] not in used and (r.get("capacity") or 0) > 0]
    if free:
        slot = min(free, key=lambda r: abs(_parse_utc(r["starts_at"]) - start))
        used.add(slot["id"])
        return slot
    slot = _insert_dedicated_slot(
        db, service_id, resource_id, capacity, _align_to_unit_grid(start, dur, tz), dur
    )
    used.add(slot["id"])
    return slot


def _hold(db, slot, service_id, provider_id, resource_id, party, holds_uid, currency, price) -> None:
    """A confirmed booking by the holds user, consuming `party` seats on `slot`."""
    booking = db.table("bookings").insert({
        "slot_id": slot["id"],
        "client_email": _HOLDS_EMAIL,
        "client_id": holds_uid,
        "status": "confirmed",
        "history": [{"status": "confirmed", "at": _iso(datetime.now(timezone.utc))}],
        "metadata": {
            "party_size": party,
            "reference": booking_reference(),
            "price_minor_units": price * party,
            "currency": currency,
            "provider_id": provider_id,
            "service_id": service_id,
            "resource_id": resource_id,
            "user_id": holds_uid,
            "slot_ids": [slot["id"]],
            "change_history": [],
        },
    }).execute().data[0]
    db.table("booking_slots").insert({"booking_id": booking["id"], "slot_id": slot["id"]}).execute()


def _seed_requests(db, primary, provider_id, model, currency, requesters, tz: str) -> int:
    """Pending booking requests on the primary (manual-approve) service, so the
    owner's Requests tab is populated. Each gets a dedicated future slot (pending
    holds no capacity, so this never collides with real occupancy). Mirrors the
    shape create_booking would produce, but with status 'pending'."""
    service_id = primary["id"]
    spec = primary["spec"]
    resource_id = primary["resource"]["id"]
    capacity = primary["resource"]["_capacity"]
    dur = spec["slotDurationMinutes"]
    price = spec["priceMinorUnits"]
    # The demo party size is illustrative, but slot capacity is enforced in the
    # DB (schema.sql, `slot_capacity_exceeded`). A config that seats fewer than
    # the party we would like to show has to win, or the seed aborts part-way
    # through and leaves the demo data half-built.
    party = min(2, capacity) if model == "shared_capacity" else 1
    now = datetime.now(timezone.utc)
    day = timedelta(days=1)

    made = 0
    # A pending request holds no capacity, so sharing a slot with a confirmed
    # booking is harmless — but a dedicated slot at an arbitrary hour is not:
    # for a day-or-longer unit it straddles the grid slot beside it, and the
    # resource's own calendar then shows two units covering the same days.
    used: set[str] = set()
    for i, (uid, email) in enumerate(requesters):
        start = now + (4 + 3 * i) * day + timedelta(hours=2)
        slot = _slot_for_booking(db, service_id, resource_id, capacity, start, dur, used, tz)
        created = now - timedelta(hours=6 + i)
        booking = db.table("bookings").insert({
            "slot_id": slot["id"],
            "client_email": email,
            "client_id": uid,
            "status": "pending",
            "history": [{"status": "pending", "at": _iso(created)}],
            "metadata": {
                "party_size": party,
                "reference": booking_reference(),
                "price_minor_units": price * party,
                "currency": currency,
                "provider_id": provider_id,
                "service_id": service_id,
                "resource_id": resource_id,
                "user_id": uid,
                "slot_ids": [slot["id"]],
                "change_history": [],
            },
            "created_at": _iso(created),
        }).execute().data[0]
        db.table("booking_slots").insert(
            {"booking_id": booking["id"], "slot_id": slot["id"]}
        ).execute()
        made += 1
    return made


_CLIENT_REVIEW_LINES = [
    (5, "Punctual, friendly and left everything spotless. A pleasure to host."),
    (5, "Clear communicator and easy to work with — welcome back any time."),
    (4, "Respectful of our space and prompt with everything. Highly rated."),
]


def _seed_client_reviews(db, client_uid, provider_id) -> int:
    """Reviews the provider left about the demo customer → their reputation.
    Attached to a few of the customer's existing bookings (one review each)."""
    bookings = db.table("bookings").select("id").eq("client_id", client_uid).execute().data or []
    now = datetime.now(timezone.utc)
    made = 0
    for i, b in enumerate(bookings[:3]):
        rating, text = _CLIENT_REVIEW_LINES[i % len(_CLIENT_REVIEW_LINES)]
        try:
            db.table("client_reviews").insert({
                "booking_id": b["id"],
                "client_id": client_uid,
                "provider_id": provider_id,
                "rating": rating,
                "text": text,
                "created_at": _iso(now - timedelta(days=4 * (i + 1))),
            }).execute()
            made += 1
        except Exception:
            pass  # table may not exist on an older DB — reputation just stays empty
    return made


def _seed_messages(db, demo_provider_id, demo_uid, owner_uid, provider_ids) -> int:
    """Seed working chat threads so both demo logins open a populated inbox.

    One full two-sided thread between the demo client and the owner on the demo
    provider (provider 0, which the owner actually owns → RLS valid on both
    sides), pre-populated with a couple of days of messages that mix directions,
    include a URL (to exercise the link chip), leave the last message on each
    side unread (so both inboxes show an unread badge) and use a reply. Plus a
    couple of one-sided client inquiries to other providers so the client inbox
    isn't a single thread. Service-key insert (system work bypasses RLS);
    best-effort so an older DB without the messaging tables just skips."""
    now = datetime.now(timezone.utc)
    m = timedelta(minutes=1)
    hour = timedelta(hours=1)
    day = timedelta(days=1)

    def _thread(provider_id, client_id, owner_id, msgs) -> int:
        # msgs: (sender_id, body, created, read_at | None, reply_index | None)
        conv = db.table("conversations").insert({
            "provider_id": provider_id,
            "client_id": client_id,
            "owner_id": owner_id,
        }).execute().data[0]
        ids: list[str] = []
        last_body, last_at = "", None
        for sender_id, body, created, read_at, reply_idx in msgs:
            row = {
                "conversation_id": conv["id"],
                "sender_id": sender_id,
                "body": body,
                "delivered_at": _iso(created),
                "created_at": _iso(created),
            }
            if read_at is not None:
                row["read_at"] = _iso(read_at)
            if reply_idx is not None:
                row["reply_to_id"] = ids[reply_idx]
            ids.append(db.table("messages").insert(row).execute().data[0]["id"])
            last_body, last_at = body, created
        db.table("conversations").update({
            "last_message_preview": last_body,
            "last_message_at": _iso(last_at),
        }).eq("id", conv["id"]).execute()
        return len(msgs)

    made = 0
    c, o = demo_uid, owner_uid
    # Read receipts on the earlier messages; the two most-recent (one each way)
    # stay unread, so the client inbox and the owner inbox each show one unread.
    main = [
        (c, "Hi! I just booked with you for next week — any chance we could start a little earlier?",
         now - 2 * day, now - 2 * day + 10 * m, None),
        (o, "Hi Mara! Of course — we can start 30 minutes earlier. I've noted it on your booking.",
         now - 2 * day + 5 * m, now - 2 * day + 12 * m, None),
        (c, "Amazing, thank you so much 🙏", now - 2 * day + 6 * m, now - 2 * day + 12 * m, None),
        (o, "You're welcome. Here's everything you'll need beforehand: https://service.example.com/welcome-guide",
         now - 2 * day + 8 * m, now - 2 * day + 20 * m, None),
        (c, "Perfect, got it — found it straight away.", now - day, now - day + 30 * m, None),
        (o, "Great! Let me know if anything comes up before then.", now - day + 3 * m, now - day + 30 * m, None),
        (c, "Will do. One more thing — could I bring a friend along?", now - 5 * hour, None, None),
        (o, "Absolutely, the more the merrier. I'll update the details.", now - 4 * hour, None, 6),
    ]
    try:
        made += _thread(demo_provider_id, c, o, main)
    except Exception:
        return made  # messaging tables absent (older DB) — skip cleanly

    inquiries = [
        [(demo_uid, "Hi! Do you have any availability this weekend?", now - 3 * day, None, None),
         (demo_uid, "Would love to book if it works out 😊", now - 3 * day + 2 * m, None, None)],
        [(demo_uid, "Hello — would it be possible to move my booking to next month?", now - 6 * hour, None, None)],
    ]
    for provider_id, msgs in zip(provider_ids[1:3], inquiries):
        try:
            made += _thread(provider_id, demo_uid, None, msgs)
        except Exception:
            pass
    return made


def _inject_edge_cases(db, primary, tz, holds_uid, provider_id, currency) -> tuple[int, set[str]]:
    """A blocked day (capacity 0), a fully-booked day, and — for shared capacity
    — a one-seat-left slot. Occupancy is made real via holds bookings."""
    service_id = primary["id"]
    price = primary["spec"]["priceMinorUnits"]
    now = datetime.now(timezone.utc)

    resource_ids = [r["id"] for r in primary["resources"]]
    slots = (
        db.table("slots").select("*").in_("resource_id", resource_ids)
        .gt("starts_at", _iso(now)).execute().data
        or []
    )
    dates = sorted({_local_date_str(s["starts_at"], tz) for s in slots})
    if not dates:
        return 0
    full_date = dates[6] if len(dates) > 6 else dates[min(1, len(dates) - 1)]
    blocked_date = dates[11] if len(dates) > 11 else dates[min(2, len(dates) - 1)]
    partial_date = dates[3] if len(dates) > 3 else dates[0]

    holds = 0
    # Slots this function blocks or fills. `_seed_bookings` runs next and reuses
    # grid slots, so it has to treat these as taken.
    consumed: set[str] = set()
    for s in slots:
        date = _local_date_str(s["starts_at"], tz)
        if date == blocked_date:
            db.table("slots").update({"capacity": 0}).eq("id", s["id"]).execute()
            consumed.add(s["id"])
        elif date == full_date:
            _hold(db, s, service_id, provider_id, s["resource_id"], s["capacity"], holds_uid, currency, price)
            consumed.add(s["id"])
            holds += 1

    if partial_date not in (blocked_date, full_date):
        partial = next(
            (s for s in slots if _local_date_str(s["starts_at"], tz) == partial_date and s["capacity"] > 1),
            None,
        )
        if partial:
            _hold(db, partial, service_id, provider_id, partial["resource_id"],
                  partial["capacity"] - 1, holds_uid, currency, price)
            consumed.add(partial["id"])
            holds += 1
    return holds, consumed


def _seed_bookings(db, primary, provider_id, demo_uid, demo_email, model, currency, tz,
                   reserved: set[str] | None = None) -> int:
    """The 5–6 lifecycle bookings owned by the demo user (mirrors seedBookings)."""
    service_id = primary["id"]
    spec = primary["spec"]
    resource_id = primary["resource"]["id"]
    capacity = primary["resource"]["_capacity"]
    dur = spec["slotDurationMinutes"]
    price = spec["priceMinorUnits"]
    cutoff_s = spec["cancellationCutoffHours"] * _HOUR
    max_slots = spec["maxSlotsPerBooking"]
    shared = model == "shared_capacity"

    def party_of(n: int) -> int:
        """A demo party that actually fits. See the note in `_seed_requests`."""
        return min(n, capacity) if shared else 1
    now = datetime.now(timezone.utc)
    # Slots already claimed by an earlier lifecycle booking, so a day-or-longer
    # unit never hands the same grid slot to two of them.
    used_slot_ids: set[str] = set(reserved or ())

    def commit(start: datetime, party: int, status: str, created: datetime,
               *, review: dict | None = None, cancelled: datetime | None = None,
               extra_starts: list[datetime] | None = None) -> None:
        starts = [start] + (extra_starts or [])
        slots = [
            _slot_for_booking(db, service_id, resource_id, capacity, s, dur, used_slot_ids, tz)
            for s in starts
        ]
        slot_ids = [s["id"] for s in slots]
        md = {
            "party_size": party,
            "reference": booking_reference(),
            "price_minor_units": price * len(slots) * party,
            "currency": currency,
            "provider_id": provider_id,
            "service_id": service_id,
            "resource_id": resource_id,
            "user_id": demo_uid,
            "slot_ids": slot_ids,
            "change_history": [],
        }
        if cancelled:
            md["cancelled_at_utc"] = _iso(cancelled)
        booking = db.table("bookings").insert({
            "slot_id": slot_ids[0],
            "client_email": demo_email,
            "client_id": demo_uid,
            "status": status,
            "history": [{"status": "confirmed", "at": _iso(created)}]
            + ([{"status": "cancelled", "at": _iso(cancelled)}] if cancelled else []),
            "metadata": md,
            "created_at": _iso(created),
        }).execute().data[0]
        db.table("booking_slots").insert(
            [{"booking_id": booking["id"], "slot_id": sid} for sid in slot_ids]
        ).execute()
        if review:
            db.table("reviews").insert({
                "booking_id": booking["id"],
                "provider_id": provider_id,
                "rating": review["rating"],
                "text": review["text"],
                "created_at": _iso(review["at"]),
            }).execute()

    hour = timedelta(hours=1)
    day = timedelta(days=1)
    # These lifecycle bookings each get a DEDICATED slot, so their starts must be
    # at least one unit apart or the same resource ends up holding overlapping
    # slots and its capacity reads as double-booked. The day-sized offsets below
    # were written for a 30-minute grid, where any two of them are trivially
    # disjoint; once `booking.granularity` can make a unit a week or a month,
    # "5 days apart" is the SAME week. So space them by whole units whenever the
    # unit is at least a day. `created`/`cancelled` stay in real days — they are
    # history timestamps and never define a slot.
    step = timedelta(minutes=dur) if dur >= 1440 else day
    # 1) upcoming, outside cutoff (changeable)
    commit(now + timedelta(seconds=cutoff_s) + 5 * step, party_of(2), "confirmed", now - 3 * day)
    # 2) upcoming, inside cutoff (locked)
    inside = min(cutoff_s * 0.4, cutoff_s - _HOUR)
    commit(now + timedelta(seconds=inside) + timedelta(minutes=30), party_of(3), "confirmed", now - day)
    # 3) completed, no review
    commit(now - 7 * step, 1, "confirmed", now - 13 * day)
    # 4) completed, with review
    past4 = now - 16 * step
    commit(past4, 1, "confirmed", now - 21 * day,
           review={"rating": 5, "text": "Exactly as described. Smooth from start to finish — would book again.",
                   "at": past4 + timedelta(minutes=dur) + 2 * hour})
    # 5) cancelled (capacity released — no hold)
    commit(now + timedelta(seconds=cutoff_s) + 12 * step, 1, "cancelled", now - 10 * day,
           cancelled=now - 9 * day)
    # 6) multi-slot completed (only where the model allows > 1 slot)
    n = 6 if max_slots > 1 else 5
    if max_slots > 1:
        count = min(3, max_slots)
        first = now - 12 * step
        commit(first, 1, "confirmed", now - 16 * day,
               extra_starts=[first + i * timedelta(minutes=dur) for i in range(1, count)])
    return n


# --- startup + active-vertical --------------------------------------------


def active_vertical() -> str:
    """Infer the currently-seeded vertical from any service's booking model."""
    try:
        rows = get_supabase().table("services").select("booking_model").limit(1).execute().data or []
        if rows:
            return BOOKING_MODEL_TO_VERTICAL.get(rows[0]["booking_model"], DEFAULT_VERTICAL)
    except Exception:
        pass
    return DEFAULT_VERTICAL


def seed_from_config() -> dict:
    """Wipe and reseed from the loaded `domain.config.json`.

    This is what makes a pivot show up in the data: currency, timezone,
    durations, prices, cutoffs, capacity and the single-tenant provider code all
    come from the config rather than from `seed_data.VERTICALS`. Verify the
    result with `scripts/check_seed.py` (`make checkseed`)."""
    from app.config import get_config  # local: avoids a seed -> config import at module load
    from seed_config import spec_from_config

    spec = spec_from_config(get_config())
    return seed_vertical(spec["verticalId"], spec)


def _seed_from_config_locked() -> dict:
    """`seed_from_config` for a caller that ALREADY holds the seed lock.

    The lock is per-connection, and `seed_lock()` opens its own — so taking it
    again from inside would wait on a lock held by a session that is waiting for
    this call to return. That is a deadlock, not re-entrancy.
    """
    from app.config import get_config
    from seed_config import spec_from_config

    spec = spec_from_config(get_config())
    return _seed_vertical_locked(spec["verticalId"], spec)


def seed_if_empty() -> None:
    # On a fresh DB the tables are created via a direct Postgres connection
    # (schema_setup) moments before this runs, but PostgREST reloads its schema
    # cache asynchronously after the `NOTIFY pgrst, 'reload schema'`. Until it
    # does, the REST client 404s with PGRST205 even though the table exists, so
    # poll past that reload window instead of giving up on the first miss.
    existing = None
    for attempt in range(10):
        try:
            existing = get_supabase().table("providers").select("id").limit(1).execute().data
            break
        except APIError as exc:
            if exc.code == "PGRST205" and attempt < 9:
                logger.info("providers not in PostgREST cache yet; waiting for reload...")
                time.sleep(1)
                continue
            logger.exception("Could not check providers; skipping seed.")
            return
        except Exception:
            logger.exception("Could not check providers; skipping seed.")
            return
    if existing:
        return
    # Try, never wait. A seeder already holding the lock is mid-wipe, so
    # `providers` reading empty above says nothing about the end state — and
    # blocking here would stall boot behind a full reseed. Skipping is correct:
    # when that seeder finishes the data is there.
    with seed_lock(wait=False) as held:
        if not held:
            logger.info("Another seed is in progress; skipping boot-time seeding.")
            return
        _seed_if_empty_locked()


def _seed_if_empty_locked() -> None:
    # Boot-time seeding is best-effort and must never take the app down with
    # it: the check above and this insert are not one transaction, so the
    # documented pivot workflow (`make reload` restarting the backend while
    # `make reseed` has the tables truncated) can read "empty", then insert into
    # a table the reseed has already refilled. That surfaced as a startup crash
    # loop on a duplicate `providers.public_code` — the API never came up, and
    # every screen degraded to "we couldn't load your profile" / "no business
    # yet" with nothing pointing at the seed. A DB that already has data is the
    # success case for this function, so log and carry on.
    try:
        _seed_from_config_locked()   # the lock is already held by seed_if_empty
    except Exception:
        logger.exception("Boot-time seed failed; starting anyway with the existing data.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_from_config()
