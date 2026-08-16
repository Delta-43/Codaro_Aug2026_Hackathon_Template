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

`seed_if_empty()` runs on startup (default vertical when no providers exist);
`seed_vertical(id)` is the destructive reseed used by `reseed.py` and the demo
vertical-switch endpoint.
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psycopg
from postgrest.exceptions import APIError

from app.db import get_db_url, get_supabase
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
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

BOOKING_MODEL_TO_VERTICAL = {
    "unit_selection": "fleet",
    "one_to_one": "oneToOne",
    "shared_capacity": "group",
}

_EXTENDED_TABLES = [
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


def _local_days(tz: str, back: int, forward: int):
    today = datetime.now(ZoneInfo(tz)).date()
    for i in range(-back, forward + 1):
        day = today + timedelta(days=i)
        yield day, day.isoweekday() % 7  # 0=Sun … 6=Sat (JS getUTCDay convention)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _local_date_str(iso: str, tz: str) -> str:
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")


def _reference() -> str:
    return "BK-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


# --- DB helpers ------------------------------------------------------------


def _chunked_insert(db, table: str, rows: list[dict], chunk: int = 500) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(rows), chunk):
        out += db.table(table).insert(rows[i : i + chunk]).execute().data or []
    return out


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


def seed_vertical(vertical_id: str) -> dict:
    """Wipe and reseed the DB for one vertical. Returns a small summary."""
    cfg = VERTICALS[vertical_id]
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
            for day, weekday in _local_days(tz, grid["daysBack"], grid["daysForward"]):
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
                        "metadata": {"service_id": service_id},
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
        counts["bookings"] += _inject_edge_cases(db, primary_service, tz, holds_uid, demo_provider_id, currency)
        counts["bookings"] += _seed_bookings(
            db, primary_service, demo_provider_id, demo_uid, DEMO_EMAIL, model, currency, tz
        )
        # Pending requests waiting on the owner (Requests tab): one from the
        # established demo user, one from a fresh prospect.
        counts["bookings"] += _seed_requests(
            db, primary_service, demo_provider_id, model, currency,
            [(demo_uid, DEMO_EMAIL), (prospect_uid, PROSPECT_EMAIL)],
        )

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
            "reference": _reference(),
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


def _seed_requests(db, primary, provider_id, model, currency, requesters) -> int:
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
    party = 2 if model == "shared_capacity" else 1
    now = datetime.now(timezone.utc)
    day = timedelta(days=1)

    made = 0
    for i, (uid, email) in enumerate(requesters):
        start = now + (4 + 3 * i) * day + timedelta(hours=2)
        slot = _insert_dedicated_slot(db, service_id, resource_id, capacity, start, dur)
        created = now - timedelta(hours=6 + i)
        booking = db.table("bookings").insert({
            "slot_id": slot["id"],
            "client_email": email,
            "client_id": uid,
            "status": "pending",
            "history": [{"status": "pending", "at": _iso(created)}],
            "metadata": {
                "party_size": party,
                "reference": _reference(),
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


def _inject_edge_cases(db, primary, tz, holds_uid, provider_id, currency) -> int:
    """A blocked day (capacity 0), a fully-booked day, and — for shared capacity
    — a one-seat-left slot. Occupancy is made real via holds bookings."""
    service_id = primary["id"]
    price = primary["spec"]["priceMinorUnits"]
    dur = primary["spec"]["slotDurationMinutes"]
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
    for s in slots:
        date = _local_date_str(s["starts_at"], tz)
        if date == blocked_date:
            db.table("slots").update({"capacity": 0}).eq("id", s["id"]).execute()
        elif date == full_date:
            _hold(db, s, service_id, provider_id, s["resource_id"], s["capacity"], holds_uid, currency, price)
            holds += 1

    if partial_date not in (blocked_date, full_date):
        partial = next(
            (s for s in slots if _local_date_str(s["starts_at"], tz) == partial_date and s["capacity"] > 1),
            None,
        )
        if partial:
            _hold(db, partial, service_id, provider_id, partial["resource_id"],
                  partial["capacity"] - 1, holds_uid, currency, price)
            holds += 1
    return holds


def _seed_bookings(db, primary, provider_id, demo_uid, demo_email, model, currency, tz) -> int:
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
    now = datetime.now(timezone.utc)

    def commit(start: datetime, party: int, status: str, created: datetime,
               *, review: dict | None = None, cancelled: datetime | None = None,
               extra_starts: list[datetime] | None = None) -> None:
        starts = [start] + (extra_starts or [])
        slots = [_insert_dedicated_slot(db, service_id, resource_id, capacity, s, dur) for s in starts]
        slot_ids = [s["id"] for s in slots]
        md = {
            "party_size": party,
            "reference": _reference(),
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
    # 1) upcoming, outside cutoff (changeable)
    commit(now + timedelta(seconds=cutoff_s) + 5 * day, 2 if shared else 1, "confirmed", now - 3 * day)
    # 2) upcoming, inside cutoff (locked)
    inside = min(cutoff_s * 0.4, cutoff_s - _HOUR)
    commit(now + timedelta(seconds=inside) + timedelta(minutes=30), 3 if shared else 1, "confirmed", now - day)
    # 3) completed, no review
    commit(now - 7 * day, 1, "confirmed", now - 13 * day)
    # 4) completed, with review
    past4 = now - 16 * day
    commit(past4, 1, "confirmed", now - 21 * day,
           review={"rating": 5, "text": "Exactly as described. Smooth from start to finish — would book again.",
                   "at": past4 + timedelta(minutes=dur) + 2 * hour})
    # 5) cancelled (capacity released — no hold)
    commit(now + timedelta(seconds=cutoff_s) + 12 * day, 1, "cancelled", now - 10 * day,
           cancelled=now - 9 * day)
    # 6) multi-slot completed (only where the model allows > 1 slot)
    n = 6 if max_slots > 1 else 5
    if max_slots > 1:
        count = min(3, max_slots)
        first = now - 12 * day
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
    seed_vertical(DEFAULT_VERTICAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_vertical(DEFAULT_VERTICAL)
