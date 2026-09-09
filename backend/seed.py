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
import random
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

# Real photography + demo cast. Both are pure override layers: a miss returns
# None and the generated SVG gradient / inline prose below wins, so the engine
# still seeds correctly with either module absent.
try:
    import seed_media
except Exception:  # pragma: no cover - optional
    seed_media = None
try:
    import seed_people
except Exception:  # pragma: no cover - optional
    seed_people = None


def _media(fn: str, name: str) -> str | None:
    """Look up real photography for `name`, or None to keep the gradient."""
    if seed_media is None:
        return None
    try:
        return getattr(seed_media, fn)(name)
    except Exception:
        return None


def _person_avatar(name: str) -> str:
    """A seeded person's picture: the real portrait when `seed_media` knows the
    name, the deterministic initials gradient otherwise.

    Every seeded account goes through this. `serialize_user` reads
    `user_metadata.avatar_url` and nothing else, so an account created without
    that key has no face anywhere in the app — message threads, the conversation
    list, the account page, review authors, the owner's request cards. The key
    was simply never written: the provider path below has always set
    `avatar_url`, so every *business* in the demo was a photograph while every
    *person* was a coloured monogram.
    """
    return _media("person_avatar", name) or avatar_uri(name, name)


def _user_metadata(name: str, tz: str, *, role: str = "client",
                   verified: bool = True, **extra) -> dict:
    """The `user_metadata` blob for a seeded account. One place, so a new
    profile field cannot land on the demo user and miss the other twenty-odd."""
    return {
        "display_name": name,
        "avatar_url": _person_avatar(name),
        "timezone": tz,
        "verified": verified,
        "role": role,
        **extra,
    }


def _throwaway_password() -> str:
    fn = getattr(seed_people, "throwaway_password", None)
    try:
        return fn() if fn else "Cd-" + secrets.token_urlsafe(21) + "-9"
    except Exception:
        return "Cd-" + secrets.token_urlsafe(21) + "-9"


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


# email -> auth user id, filled once per process by `_known_users`.
_USER_IDS: dict[str, str] = {}


def _known_users(db) -> dict[str, str]:
    """Every existing account, by email. Populated once and then reused.

    A seed now provisions the whole cast — two dozen accounts — and
    `_ensure_user` used to discover an existing one by letting `create_user`
    fail and then listing *every* user to find it. That is an O(n) admin listing
    per person on the second seed onwards. One listing up front is the same
    information for one round trip. Best-effort: on failure the per-user
    fallback in `_ensure_user` still resolves the account.
    """
    if _USER_IDS:
        return _USER_IDS
    users: list = []
    try:
        page = 1
        while True:  # the admin API pages; a single call would cap at its default
            batch = list(db.auth.admin.list_users(page=page, per_page=200) or [])
            users += batch
            if len(batch) < 200:
                break
            page += 1
    except TypeError:  # older client without the paging kwargs
        try:
            users = list(db.auth.admin.list_users() or [])
        except Exception:
            logger.exception("Could not list existing users.")
            return _USER_IDS
    except Exception:
        logger.exception("Could not list existing users.")
        return _USER_IDS
    for u in users:
        email = getattr(u, "email", None)
        if email:
            _USER_IDS[email] = u.id
    return _USER_IDS


def _ensure_user(db, email: str, password: str, metadata: dict) -> str:
    """Create (or find) a Supabase auth user; return its id. On an existing user
    the profile metadata is reset to the seed values, so a reseed restores every
    seeded account — including its `avatar_url` — to a pristine state."""
    uid = _known_users(db).get(email)
    if uid:
        try:
            db.auth.admin.update_user_by_id(uid, {"user_metadata": metadata})
        except Exception:
            logger.warning("Could not refresh metadata for %s", email)
        return uid
    try:
        resp = db.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True, "user_metadata": metadata}
        )
        _USER_IDS[email] = resp.user.id
        return resp.user.id
    except Exception:
        # Exists but wasn't in the listing (a racing seeder, or a listing that
        # failed) — locate by email and reset its metadata.
        try:
            for u in db.auth.admin.list_users():
                if getattr(u, "email", None) == email:
                    try:
                        db.auth.admin.update_user_by_id(u.id, {"user_metadata": metadata})
                    except Exception:
                        pass
                    _USER_IDS[email] = u.id
                    return u.id
        except Exception:
            logger.exception("Could not resolve existing user %s", email)
        raise


def _seed_people_users(db, tz: str) -> dict[str, dict]:
    """Provision the whole cast as real Supabase accounts, keyed by email.

    The three contractual logins keep their published passwords; everyone else
    gets a throwaway one, because they exist to populate the demo — a face on a
    thread, a name on a review, a family in the request queue — rather than to
    be logged into. All of them carry `avatar_url`, so the app has a photograph
    for the person wherever it renders them.

    `seed_people` is an optional module, so the three fixed logins are inlined
    as the fallback roster and the seed still produces a usable demo without it.
    """
    fixed = {
        DEMO_EMAIL: DEMO_PASSWORD,
        OWNER_EMAIL: OWNER_PASSWORD,
        PROSPECT_EMAIL: PROSPECT_PASSWORD,
    }
    roster = list(getattr(seed_people, "CAST", None) or []) or [
        {"name": "Mara Lindqvist", "email": DEMO_EMAIL, "role": "client", "verified": True},
        {"name": "Tomasz Wiśniewski", "email": PROSPECT_EMAIL, "role": "client", "verified": False},
        {"name": "Henryk Walczak", "email": OWNER_EMAIL, "role": "owner", "verified": True},
    ]
    out: dict[str, dict] = {}
    for person in roster:
        email = person.get("email")
        if not email:
            continue
        # 'staff' is prose, not an engine role: the engine knows owner and
        # client only. The home's own people are stored as clients carrying a
        # job title, and `_client_pool` leaves them out of the demand below.
        role = "owner" if person.get("role") == "owner" else "client"
        md = _user_metadata(
            person["name"], tz, role=role,
            verified=bool(person.get("verified", True)),
            **({"job_title": person["title"]} if person.get("title") else {}),
        )
        try:
            uid = _ensure_user(db, email, fixed.get(email) or _throwaway_password(), md)
        except Exception:
            logger.exception("Could not provision %s; the demo goes on without them.", email)
            continue
        out[email] = {**person, "id": uid}
    return out


def _client_pool(people: dict[str, dict]) -> list[dict]:
    """The bereaved families — everyone seeded except the home's own people.
    Bookings, reviews and threads all draw from this list."""
    return [p for p in people.values() if p.get("role") == "client"]


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
    # The whole cast, not just the three logins: a demo of a busy business needs
    # twenty families with names and faces, and every one of them is a real auth
    # user so RLS, conversations and client reputation all behave normally.
    # The demo owner owns the demo provider (index 0), so logging in as the
    # owner shows a populated dashboard rather than a blank slate.
    people = _seed_people_users(db, tz)
    demo_uid = people[DEMO_EMAIL]["id"]
    owner_uid = people[OWNER_EMAIL]["id"]
    prospect_uid = people[PROSPECT_EMAIL]["id"]
    holds_uid = _ensure_user(
        db, _HOLDS_EMAIL, _HOLDS_PASSWORD,
        _user_metadata("Guest", tz),
    )

    # When the deployment confirms by request (`timing.confirmation`), NOTHING
    # auto-approves: every arrangement must land as a pending request for the
    # business to act on. Otherwise only the primary demo service is manual.
    try:
        from app.config import get_config  # local: avoids a module-load cycle

        _cfg = get_config()
        request_approve = _cfg["timing"]["confirmation"] == "request_approve"
        # Single-tenant deployments have exactly ONE business; the flagship
        # must answer to the code the config names or the whole app renders
        # "no business". Mirrors seed_config.spec_from_config.
        _tenancy = _cfg["tenancy"]
        single_tenant = _tenancy["mode"] == "single"
        provider_code = _tenancy.get("providerCode")
    except Exception:
        request_approve = False
        single_tenant, provider_code = False, None

    counts = {"providers": 0, "services": 0, "resources": 0, "slots": 0, "bookings": 0,
              "reviews": 0, "clientReviews": 0, "conversations": 0, "messages": 0,
              "users": len(people)}
    demo_provider_id = None
    primary_service = None  # (service_id, resource rows, dur, cutoff, price)
    # Every service the demo home offers, in catalogue order. The demand seeder
    # books across ALL of them — a catalogue of eleven arrangements where only
    # the first one has ever been sold does not read as a working business.
    demo_services: list[dict] = []
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
                "image_url": _media("tile", spec["name"]) or tile_uri(spec["name"], spec["name"]),
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
                "image_url": _media("tile", r["name"]) or tile_uri(service_id + r["name"], r["name"]),
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
    seed_providers = cfg["providers"][:1] if single_tenant else cfg["providers"]
    for i, p in enumerate(seed_providers):
        prov = db.table("providers").insert({
            "name": p["name"],
            "public_code": (provider_code if (single_tenant and i == 0 and provider_code) else p["publicCode"]),
            "category_id": p["categoryId"],
            "owner_id": owner_uid if i == 0 else None,  # demo owner owns the demo provider
            "metadata": {
                # Provenance, so a checker (and `active_vertical()`) reads what
                # this data was built from instead of inferring it from the
                # shape of the rows — a guess that can only ever name a vertical
                # whose `booking_model` happens to be unique.
                "seeded": {
                    "source": vertical_id,
                    # The vertical by NAME, so `active_vertical()` can read it
                    # back instead of guessing from `booking_model` — a mapping
                    # that can only ever name the three canned verticals and
                    # therefore cannot express a fourth.
                    "verticalId": vertical_id,
                    "tz": tz,
                    "currency": currency,
                    "bookingModel": model,
                },
                "avatar_url": _media("provider_avatar", p["name"]) or avatar_uri(p["name"], p["name"]),
                "cover_url": _media("provider_cover", p["name"]) or cover_uri(p["name"]),
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
                    owner_id=owner_uid, auto_approve=(si != 0) and not request_approve,
                )
                entry = {"id": sid, "spec": spec, "resource": res_rows[0], "resources": res_rows}
                demo_services.append(entry)
                if si == 0:
                    primary_service = entry
        else:
            # A provider may carry its own headline service; otherwise six
            # siblings sit in search reading the identical shared row.
            t = p.get("service") or cfg["simpleService"]
            # Specs write their venues either as a single `resource` or as a
            # `resources` list; accept both so a vertical can use whichever.
            venues = t.get("resources") or ([t["resource"]] if t.get("resource") else [])
            add_service(prov["id"], t, venues)

    # occupancy edge cases + demo bookings on the primary demo service
    if primary_service:
        edge_holds, edge_slots = _inject_edge_cases(
            db, primary_service, tz, holds_uid, demo_provider_id, currency
        )
        counts["bookings"] += edge_holds
        # Pending requests waiting on the owner (Requests tab): one from the
        # established demo user, one from a fresh prospect.
        counts["bookings"] += _seed_requests(
            db, primary_service, demo_provider_id, model, currency,
            [(demo_uid, DEMO_EMAIL, people[DEMO_EMAIL]["name"]),
             (prospect_uid, PROSPECT_EMAIL, people[PROSPECT_EMAIL]["name"])], tz,
        )
        # ONE pool, shared by every booking seeder below. A venue holds one
        # booking a day (`booking.party.max` is 1, every venue is capacity 1,
        # and `enforce_slot_capacity` rejects the second confirmed booking), so
        # the demo family and the trade have to draw their dates out of the same
        # hat or they collide. Built here, after the edge cases and the
        # requests, so it reads their occupancy out of `booking_slots` instead
        # of trying to predict it.
        pool = _SlotPool(db, tz, [r["id"] for s in demo_services for r in s["resources"]])
        # The demonstration account's own history: the six-booking lifecycle, so
        # the demo login is never empty. Seeded before the anonymous demand
        # below so it gets first pick of the dates.
        counts["bookings"] += _seed_bookings(
            db, primary_service, demo_provider_id, demo_uid, DEMO_EMAIL, model, currency, tz,
            people[DEMO_EMAIL]["name"], reserved=edge_slots,
        )
        # The rest of the trade: bookings across the whole catalogue, every
        # status the engine has, and ten weeks either side of today. The demo
        # account is left OUT of the client rotation so its own history above is
        # not contradicted by a second, anonymous set under the same login.
        trade = [c for c in _client_pool(people) if c.get("email") != DEMO_EMAIL]
        demand = _seed_demand(db, demo_services, demo_provider_id, trade, currency, tz, pool)
        counts["bookings"] += demand["count"]
        # Reviews hang off completed bookings: a review with nothing behind it
        # would not survive the first click into it.
        counts["reviews"] = _seed_provider_reviews(db, demo_provider_id, demand["completed"])
        # Customer reputations: reviews the business left about them.
        counts["clientReviews"] = _seed_client_reviews(db, demo_provider_id, demand["completed"])
        # Working chat threads so every demo login lands on a populated inbox.
        threads = _seed_messages(db, demo_provider_id, people, owner_uid)
        counts["conversations"], counts["messages"] = threads

    # Families follow the home they used. With one provider this is what gives
    # it a follower count and the account page something to list.
    if demo_provider_id:
        follows = [
            {"user_id": p["id"], "provider_id": demo_provider_id}
            for p in _client_pool(people)[:14]
        ]
        try:
            _chunked_insert(db, "follows", follows)
        except Exception:
            logger.warning("Could not seed follows.")
    elif len(provider_ids) > 1:
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


def _arrangement_price(base: int, extras: dict, add_ons: int) -> int:
    """What the family is billed: the service's own rate, plus the discreet-
    handling tier where the manner of death triggers it, plus the add-ons.

    Every seeded booking goes through this. A row whose `price_minor_units`
    ignores the add-ons it carries shows a total that its own breakdown
    contradicts, which is worse than showing no breakdown at all.
    """
    total = int(base)
    if ((extras.get("subject") or {}).get("manner_of_death")) == _DISCREET_MANNER:
        total += _DISCREET_SURCHARGE
    return total + int(add_ons)


def _hold(db, slot, service_id, provider_id, resource_id, party, holds_uid, currency, price,
          *, index: int = 0, tz: str = "UTC") -> None:
    """A confirmed booking by the holds user, consuming `party` seats on `slot`.

    It carries a subject and a payer like any other booking: these rows are
    what makes a day read as full, and the owner's calendar opens them."""
    service_date = _parse_utc(slot["starts_at"]).astimezone(ZoneInfo(tz)).date()
    extras, add_ons = _arrangement_extras(320 + index, service_date, "Another family",
                                          random.Random(index))
    booking = db.table("bookings").insert({
        "slot_id": slot["id"],
        "client_email": _HOLDS_EMAIL,
        "client_id": holds_uid,
        "status": "confirmed",
        "history": [{"status": "confirmed", "at": _iso(datetime.now(timezone.utc))}],
        "metadata": {
            "party_size": party,
            "reference": booking_reference(),
            "price_minor_units": _arrangement_price(price * party, extras, add_ons),
            "currency": currency,
            "provider_id": provider_id,
            "service_id": service_id,
            "resource_id": resource_id,
            "user_id": holds_uid,
            "slot_ids": [slot["id"]],
            "change_history": [],
            **extras,
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
    for i, (uid, email, name) in enumerate(requesters):
        start = now + (4 + 3 * i) * day + timedelta(hours=2)
        slot = _slot_for_booking(db, service_id, resource_id, capacity, start, dur, used, tz)
        created = now - timedelta(hours=6 + i)
        extras, add_ons = _arrangement_extras(
            260 + i, _parse_utc(slot["starts_at"]).astimezone(ZoneInfo(tz)).date(),
            name, random.Random(260 + i),
        )
        booking = db.table("bookings").insert({
            "slot_id": slot["id"],
            "client_email": email,
            "client_id": uid,
            "status": "pending",
            "history": [{"status": "pending", "at": _iso(created)}],
            "metadata": {
                "party_size": party,
                "reference": booking_reference(),
                "price_minor_units": _arrangement_price(price * party, extras, add_ons),
                "currency": currency,
                "provider_id": provider_id,
                "service_id": service_id,
                "resource_id": resource_id,
                "user_id": uid,
                "slot_ids": [slot["id"]],
                "change_history": [],
                **extras,
            },
            "created_at": _iso(created),
        }).execute().data[0]
        db.table("booking_slots").insert(
            {"booking_id": booking["id"], "slot_id": slot["id"]}
        ).execute()
        made += 1
    return made


# --- the rest of the trade -------------------------------------------------
# Everything above seeds the *demonstration*: one family's lifecycle, two
# pending requests, three occupancy edge cases. What it does not seed is a
# business. A provider with ten bookings on one of its eleven services and
# a single conversation reads as a prototype no matter how good the copy is, so
# the seeders below fill the other four months of trade.


# How many arrangements land in each state. `completed` is by far the largest
# because it is the past — a home open eight weeks has buried far more people
# than it currently has on the books. `pending` is second: this deployment
# confirms by request (`timing.confirmation`), so an unanswered request is the
# normal resting state of a new arrangement, not an exception.
_DEMAND_PLAN = [
    ("completed", 46),   # stored 'confirmed' with an end in the past
    ("confirmed", 24),
    ("pending", 20),
    ("cancelled", 9),
    ("rejected", 7),
]

# Where in the calendar each state is plausible, as day offsets from today.
_DEMAND_WINDOW = {
    "completed": (-56, -2),
    "confirmed": (2, 56),
    "pending": (3, 56),
    "cancelled": (-40, 45),
    "rejected": (4, 56),
}

# `pricing.tiers[0]` charges 405 000 rather than the 285 000 base when the
# manner of death is the awkward one — a supplement of 1 200 EUR for handling
# nobody asks questions about. The base differs per service (a direct committal
# is not a full booking), so the seed applies the DIFFERENCE rather than the
# tier's absolute figure: what the tier actually expresses is the cost of
# discretion, and that cost does not depend on which arrangement it rides on.
_DISCREET_SURCHARGE = 120000
_DISCREET_MANNER = "Mysterious circumstances — no questions asked"


def _live_booking_block() -> dict:
    """`booking` from the loaded config — the add-on catalogue and the subject
    field list. Read at seed time rather than hard-coded, so a pivot that
    renames a field or re-prices an add-on reseeds correctly."""
    try:
        from app.config import get_config  # local: avoids a module-load cycle

        return get_config().get("booking") or {}
    except Exception:
        return {}


def _pick_options(block: dict, rng) -> tuple[list[dict], int]:
    """A plausible basket of add-ons, in the shape `rules.resolve_options`
    produces — `{key, label, choice, amountMinorUnits}` — because that is what
    `serialize_booking` echoes back and what the pricing breakdown adds up.

    Booleans are sparse (most families take none or one); the three selects
    (casket, music, makeup) are chosen more often, because a casket is not
    optional in the way a dove release is.
    """
    lines: list[dict] = []
    for option in block.get("options") or []:
        key, label = option.get("key"), option.get("label") or option.get("key")
        if not key:
            continue
        if option.get("type") == "select":
            choices = [c for c in (option.get("choices") or []) if c.get("key")]
            if not choices or rng.random() > 0.55:
                continue
            choice = rng.choice(choices)
            lines.append({
                "key": key,
                "label": f"{label} — {choice.get('label') or choice['key']}",
                "choice": choice["key"],
                "amountMinorUnits": int(choice.get("priceMinorUnits") or 0),
            })
        elif rng.random() < 0.22:
            lines.append({
                "key": key,
                "label": label,
                "choice": True,
                "amountMinorUnits": int(option.get("priceMinorUnits") or 0),
            })
    return lines, sum(line["amountMinorUnits"] for line in lines)


def _subject_for(block: dict, person: dict, service_date) -> dict:
    """One subject, filtered to the fields the config actually declares.

    The date of death is derived from the date of the service rather than
    stored, so the gap between the two stays days-not-years however far the
    seed places the booking. Filtering through the declared field list is what
    makes this survive a pivot: a config that drops `pacemaker_present` gets a
    subject without one instead of a stray key the UI never renders.
    """
    declared = [f.get("key") for f in ((block.get("subject") or {}).get("fields") or [])]
    died = service_date - timedelta(days=int(person.get("diedDaysBefore") or 5))
    full = {**person, "date_of_death": died.isoformat()}
    full.pop("diedDaysBefore", None)
    if not declared:
        return full
    return {k: v for k, v in full.items() if k in declared and v not in (None, "")}


def _arrangement_extras(index: int, service_date, payer_name: str, rng,
                        block: dict | None = None) -> tuple[dict, int]:
    """The domain half of a booking's metadata, and what the add-ons cost.

    Everything this vertical's config declares and the engine's own keys do not:
    the `subject` fields the config declares, the chosen `booking.options`,
    and the `metaFields.bookings` values. One helper because EVERY booking needs
    them: a booking with no subject on it renders as an empty intake panel, and
    the demo user's own bookings are the first ones anybody opens.

    `index` selects the subject and must be unique across all callers; the
    same person buried twice is the detail that gives a seeded demo away.
    """
    block = _live_booking_block() if block is None else block
    subject_for = getattr(seed_people, "subject", None) or (lambda i: {"full_name": f"Subject {i + 1}"})
    relationships = list(getattr(seed_people, "PAYER_RELATIONSHIPS", None) or ["Executor"])
    routes = list(getattr(seed_people, "PROCESSION_ROUTES", None) or [""])
    speakers = list(getattr(seed_people, "EULOGY_SPEAKERS", None) or [""])
    surplus = list(getattr(seed_people, "WILL_SURPLUS_NOTES", None) or [""])

    subject = _subject_for(block, subject_for(index), service_date)
    options, options_total = _pick_options(block, rng)
    extras = {
        "subject": subject,
        "options": options,
        # `metaFields.bookings`. The payer is never the subject, and that
        # separation is the premise of the whole pivot, so it is expressed as
        # data rather than assumed by the code that reads it.
        "payer_name": payer_name,
        "payer_relationship": relationships[index % len(relationships)],
        "estate_reference": f"EST-{service_date.year}-{1000 + index * 7 % 8999:04d}",
        "attendee_estimate": rng.choice([0, 6, 12, 18, 24, 30, 40, 55, 60, 80, 110, 160]),
        "procession_route": routes[index % len(routes)],
        "eulogy_speaker": speakers[index % len(speakers)],
        "will_surplus_note": surplus[index % len(surplus)],
    }
    return extras, options_total


class _SlotPool:
    """Every bookable date for the demo home, indexed by (resource, local date).

    This vertical books a whole day exclusively: `booking.party.max` is 1, every
    venue has capacity 1, and `enforce_slot_capacity` rejects a second confirmed
    booking on the same slot. So the pool hands each slot out exactly ONCE —
    including to pending/cancelled/rejected bookings, which hold no capacity but
    would still make a resource's calendar read as double-booked.

    The seeded grid runs a week back and two months forward; the demand reaches
    eight weeks in both directions. A date outside the grid gets a dedicated
    slot inserted at local midnight — the same lattice `_align_to_unit_grid`
    snaps to, so a made-up date abuts the grid instead of straddling it.
    """

    def __init__(self, db, tz: str, resource_ids: list[str]):
        self.db = db
        self.tz = tz
        self.by_resource: dict[str, dict[str, dict]] = {}
        self.used: set[str] = set()
        for row in _load_slots(db, resource_ids):
            date = _local_date_str(row["starts_at"], tz)
            self.by_resource.setdefault(row["resource_id"], {}).setdefault(date, row)
        # Whatever the edge cases and the lifecycle bookings already took. This
        # runs after them on purpose: reading occupancy is cheaper and far more
        # reliable than trying to predict it.
        for row in db.table("booking_slots").select("slot_id").execute().data or []:
            self.used.add(row["slot_id"])

    def take(self, service_id: str, resource_id: str, date) -> str | None:
        """Claim `date` on `resource_id`, or None when it is already spoken for
        (or blocked — the edge-case seeder sets a whole day to capacity 0)."""
        key = date.isoformat()
        dates = self.by_resource.setdefault(resource_id, {})
        slot = dates.get(key)
        if slot is None:
            start = _wall_to_utc(date.year, date.month, date.day, 0, 0, self.tz)
            try:
                slot = _insert_dedicated_slot(self.db, service_id, resource_id, 1, start, 1440)
            except Exception:
                return None
            dates[key] = slot
        if slot["id"] in self.used or int(slot.get("capacity") or 0) < 1:
            return None
        self.used.add(slot["id"])
        return slot["id"]


def _load_slots(db, resource_ids: list[str]) -> list[dict]:
    """Every slot for the given resources, paged. A single unbounded select
    would silently stop at PostgREST's row cap, and a pool missing its tail
    quietly starts inserting duplicate slots over the grid it failed to read."""
    rows: list[dict] = []
    for i in range(0, len(resource_ids), 40):
        chunk = resource_ids[i : i + 40]
        offset = 0
        while True:
            page = (
                db.table("slots").select("id,resource_id,starts_at,capacity")
                .in_("resource_id", chunk).order("starts_at")
                .range(offset, offset + 999).execute().data
                or []
            )
            rows += page
            if len(page) < 1000:
                break
            offset += 1000
    return rows


def _seed_demand(db, services: list[dict], provider_id: str, clients: list[dict],
                 currency: str, tz: str, pool: "_SlotPool | None" = None) -> dict:
    """The home's actual trade: ~80 arrangements across the whole catalogue.

    Every row carries what this vertical's config declares — a `subject` (the
    subject fields the config declares), the `metaFields.bookings` values (the
    payer, who is always somebody OTHER than the subject, plus the reference and the
    mourner estimate), and a basket of `booking.options` add-ons. That is the
    entire point of the pivot expressed in data rather than in a schema.

    Deterministic: one seeded RNG, so two reseeds produce the same demo and a
    screenshot taken on Monday still matches on Tuesday.

    Returns `{"count": n, "completed": [...]}`; the completed list is what the
    review seeders hang off, newest booking first.
    """
    if not services or not clients:
        return {"count": 0, "completed": []}
    rng = random.Random(0x0C0DA205)
    block = _live_booking_block()
    now = datetime.now(timezone.utc)
    today = datetime.now(ZoneInfo(tz)).date()
    if pool is None:
        pool = _SlotPool(db, tz, [r["id"] for s in services for r in s["resources"]])

    plan = [status for status, n in _DEMAND_PLAN for _ in range(n)]
    rng.shuffle(plan)

    rows: list[dict] = []
    links: list[tuple[str, str]] = []   # (reference, slot_id) — booking ids come back from the insert
    completed: list[dict] = []
    for i, status in enumerate(plan):
        service = services[i % len(services)]
        spec = service["spec"]
        client = clients[i % len(clients)]
        lo, hi = _DEMAND_WINDOW[status]

        # Try a few dates before giving up: with capacity 1 per venue-day a
        # collision is normal, not an error.
        slot_id = date = resource = None
        for _ in range(8):
            candidate = today + timedelta(days=rng.randint(lo, hi))
            resource = rng.choice(service["resources"])
            slot_id = pool.take(service["id"], resource["id"], candidate)
            if slot_id:
                date = candidate
                break
        if not slot_id:
            continue

        extras, add_ons = _arrangement_extras(i, date, client["name"], rng, block)
        total = _arrangement_price(spec["priceMinorUnits"], extras, add_ons)
        deposit = round(total * 0.30)
        reference = booking_reference()
        service_start = _wall_to_utc(date.year, date.month, date.day, 0, 0, tz)
        requested = service_start - timedelta(days=rng.randint(4, 20), hours=rng.randint(0, 20))
        decided = requested + timedelta(hours=rng.randint(3, 40))

        if status == "completed":
            stored, history = "confirmed", [
                {"status": "pending", "at": _iso(requested)},
                {"status": "confirmed", "at": _iso(decided)},
            ]
            paid = total
        elif status == "confirmed":
            stored, history = "confirmed", [
                {"status": "pending", "at": _iso(requested)},
                {"status": "confirmed", "at": _iso(decided)},
            ]
            paid = deposit
        elif status == "pending":
            stored, history, paid = "pending", [{"status": "pending", "at": _iso(requested)}], 0
        elif status == "rejected":
            stored, history, paid = "rejected", [
                {"status": "pending", "at": _iso(requested)},
                {"status": "rejected", "at": _iso(decided)},
            ], 0
        else:
            cancelled_at = min(decided + timedelta(days=rng.randint(1, 6)), now)
            stored, history, paid = "cancelled", [
                {"status": "pending", "at": _iso(requested)},
                {"status": "confirmed", "at": _iso(decided)},
                {"status": "cancelled", "at": _iso(cancelled_at)},
            ], 0

        md = {
            "party_size": 1,   # `booking.party.mode` is buyout: one family, one date
            "reference": reference,
            "price_minor_units": total,
            "deposit_minor_units": deposit,
            "amount_paid_minor_units": paid,
            "currency": currency,
            "provider_id": provider_id,
            "service_id": service["id"],
            "resource_id": resource["id"],
            "user_id": client["id"],
            "slot_ids": [slot_id],
            "change_history": [],
            **extras,
        }
        if stored == "cancelled":
            md["cancelled_at_utc"] = history[-1]["at"]
        rows.append({
            "slot_id": slot_id,
            "client_email": client["email"],
            "client_id": client["id"],
            "status": stored,
            "history": history,
            "metadata": md,
            "created_at": _iso(requested),
        })
        links.append((reference, slot_id))
        if status == "completed":
            completed.append({
                "reference": reference,
                "client_id": client["id"],
                "client_email": client["email"],
                "ended": service_start + timedelta(days=1),
            })

    if not rows:
        return {"count": 0, "completed": []}
    inserted = _chunked_insert(db, "bookings", rows)
    # Match on the reference rather than on insert order: PostgREST returns rows
    # in order today, but a booking linked to the wrong slot is silent damage.
    by_reference = {(r.get("metadata") or {}).get("reference"): r["id"] for r in inserted}
    _chunked_insert(db, "booking_slots", [
        {"booking_id": by_reference[ref], "slot_id": sid}
        for ref, sid in links if ref in by_reference
    ])
    for row in completed:
        row["id"] = by_reference.get(row["reference"])
    completed = [r for r in completed if r.get("id")]
    completed.sort(key=lambda r: r["ended"], reverse=True)
    return {"count": len(inserted), "completed": completed}


# Where each of the demo family's states sits relative to today. Wider than the
# trade's window: this is a family with a long history, and their bookings list
# is the screen a viewer scrolls furthest down.
_DEMO_WINDOW = {
    "completed": (-74, -3),
    "confirmed": (2, 55),
    "pending": (5, 58),
    "cancelled": (-30, 40),
    "rejected": (6, 50),
}


_PROVIDER_REVIEW_LINES = [
    (5, 0, "Exactly as described. Smooth from start to finish."),
    (4, 0, "Professional throughout, and everything arrived when they said it would."),
]


def _seed_provider_reviews(db, provider_id: str, completed: list[dict]) -> int:
    """Reviews the families left about the home, one per completed arrangement.

    `reviews.booking_id` is `not null`, so a review is only ever as real as the
    booking under it, which is also why these are seeded after the demand and
    not from a standalone list of dates. The written date is derived from the
    service (a day or three after it), never from the review's own `days_ago`:
    a five-star review dated before the booking it praises is the kind of detail
    that unravels a demo.
    """
    lines = list(getattr(seed_people, "PROVIDER_REVIEWS", None) or _PROVIDER_REVIEW_LINES)
    if not lines or not completed:
        return 0
    now = datetime.now(timezone.utc)
    rows = []
    for i, booking in enumerate(completed):
        if i >= len(lines):
            break
        rating, _days_ago, text = lines[i]
        written = min(booking["ended"] + timedelta(days=1 + (i % 3)), now - timedelta(hours=2))
        rows.append({
            "booking_id": booking["id"],
            "provider_id": provider_id,
            "rating": rating,
            "text": text,
            "created_at": _iso(written),
        })
    try:
        return len(_chunked_insert(db, "reviews", rows))
    except Exception:
        logger.exception("Could not seed provider reviews.")
        return 0


_CLIENT_REVIEW_LINES = [
    (5, "Punctual, friendly and left everything spotless. A pleasure to host."),
    (5, "Clear communicator and easy to work with — welcome back any time."),
    (4, "Respectful of our space and prompt with everything. Highly rated."),
]


def _seed_client_reviews(db, provider_id: str, completed: list[dict]) -> int:
    """Reviews the home left about the families → their reputation.

    One per family at most (`GET /me/reputation` reads a person, not a booking),
    and only against a completed arrangement, which is the same constraint
    `POST /bookings/{id}/client-review` enforces at runtime.
    """
    lines = list(getattr(seed_people, "CLIENT_REVIEWS", None) or _CLIENT_REVIEW_LINES)
    if not lines or not completed:
        return 0
    now = datetime.now(timezone.utc)
    rows, seen = [], set()
    for booking in completed:
        if len(rows) >= len(lines):
            break
        if booking["client_id"] in seen:
            continue
        seen.add(booking["client_id"])
        rating, text = lines[len(rows)]
        rows.append({
            "booking_id": booking["id"],
            "client_id": booking["client_id"],
            "provider_id": provider_id,
            "rating": rating,
            "text": text,
            "created_at": _iso(min(booking["ended"] + timedelta(days=2), now - timedelta(hours=1))),
        })
    try:
        return len(_chunked_insert(db, "client_reviews", rows))
    except Exception:
        # Table may not exist on an older DB — reputation just stays empty.
        logger.warning("Could not seed client reviews.")
        return 0


_FALLBACK_THREADS = [
    (None, 20, [
        (True, "Good afternoon — I would like to ask about availability next week."),
        (False, "Of course. I will come back to you this afternoon with a date."),
    ]),
]


def _seed_messages(db, provider_id, people: dict[str, dict], owner_uid) -> tuple[int, int]:
    """The home's inbox: one thread per family, a hundred-odd messages.

    `conversations` is unique on `(provider_id, client_id)`, so a family has
    exactly ONE thread with the home however many times they come back — the
    prose in `seed_people.THREADS` is therefore keyed by email and any later
    segment for the same family is appended to their existing thread rather than
    starting a second one that the database would refuse.

    Receipts are seeded deliberately: a family's last message is left unread in
    roughly half the threads, so the owner's inbox opens on a real unread badge
    rather than a tidy zero, and the demo user's own thread ends on an unread
    message from the home so the client side badges too.

    Best-effort throughout: an older DB without the messaging tables just skips.
    """
    rng = random.Random(0x11BE12)
    now = datetime.now(timezone.utc)
    minute = timedelta(minutes=1)

    # Group by family, oldest segment first, so a returning family's thread
    # reads in chronological order.
    raw = list(getattr(seed_people, "THREADS", None) or _FALLBACK_THREADS)
    grouped: dict[str, list[tuple[int, list]]] = {}
    order: list[str] = []
    for email, hours_ago, messages in raw:
        email = email or DEMO_EMAIL
        if email not in grouped:
            grouped[email] = []
            order.append(email)
        grouped[email].append((hours_ago, messages))

    conversations, sent = 0, 0
    for email in order:
        person = people.get(email)
        if not person:
            continue
        segments = sorted(grouped[email], key=lambda s: -s[0])
        try:
            conv = db.table("conversations").insert({
                "provider_id": provider_id,
                "client_id": person["id"],
                "owner_id": owner_uid,
            }).execute().data[0]
        except Exception:
            if conversations == 0:
                return 0, 0   # messaging tables absent (older DB) — skip cleanly
            logger.warning("Could not open a thread for %s", email)
            continue
        conversations += 1

        rows: list[dict] = []
        for hours_ago, messages in segments:
            anchor = now - timedelta(hours=hours_ago)
            # Spread the exchange over most of the time since it started, so a
            # thread opened two days ago does not fire eight messages in an hour
            # and a thread opened an hour ago does not finish in the future.
            span = max(minute * 4, (now - anchor) * 0.8)
            step = span / max(1, len(messages))
            at = anchor
            for index, (from_client, body) in enumerate(messages):
                last = index == len(messages) - 1 and hours_ago == segments[-1][0]
                # The tail of a thread is where an unread badge is legible; the
                # earlier traffic is all read, which is what a real inbox
                # looks like. The demo login's own thread is not left to chance:
                # it always ends on an unread message FROM the home, because the
                # unread badge is part of what the customer side is showing off.
                unread = last and (email == DEMO_EMAIL or rng.random() < 0.55)
                row = {
                    "conversation_id": conv["id"],
                    "sender_id": person["id"] if from_client else owner_uid,
                    "body": body,
                    "delivered_at": _iso(at),
                    "created_at": _iso(at),
                }
                if not unread:
                    row["read_at"] = _iso(min(at + timedelta(minutes=rng.randint(2, 90)), now))
                rows.append(row)
                at = min(at + step * (0.5 + rng.random()), now - minute)
        try:
            inserted = _chunked_insert(db, "messages", rows)
        except Exception:
            logger.exception("Could not seed messages for %s", email)
            continue
        sent += len(inserted)
        # One quoted reply, so the reply-chip rendering is exercised somewhere.
        if len(inserted) > 2 and conversations == 1:
            try:
                db.table("messages").update(
                    {"reply_to_id": inserted[-2]["id"]}
                ).eq("id", inserted[-1]["id"]).execute()
            except Exception:
                pass
        db.table("conversations").update({
            "last_message_preview": rows[-1]["body"],
            "last_message_at": rows[-1]["created_at"],
        }).eq("id", conv["id"]).execute()
    return conversations, sent


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
            _hold(db, s, service_id, provider_id, s["resource_id"], s["capacity"], holds_uid,
                  currency, price, index=holds, tz=tz)
            consumed.add(s["id"])
            holds += 1

    if partial_date not in (blocked_date, full_date):
        partial = next(
            (s for s in slots if _local_date_str(s["starts_at"], tz) == partial_date and s["capacity"] > 1),
            None,
        )
        if partial:
            _hold(db, partial, service_id, provider_id, partial["resource_id"],
                  partial["capacity"] - 1, holds_uid, currency, price, index=holds, tz=tz)
            consumed.add(partial["id"])
            holds += 1
    return holds, consumed


def _seed_bookings(db, primary, provider_id, demo_uid, demo_email, model, currency, tz,
                   demo_name: str = "The family",
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
        commit.n = getattr(commit, "n", 0) + 1
        extras, add_ons = _arrangement_extras(
            200 + commit.n, start.astimezone(ZoneInfo(tz)).date(), demo_name,
            random.Random(200 + commit.n),
        )
        md = {
            "party_size": party,
            **extras,
            "reference": booking_reference(),
            "price_minor_units": _arrangement_price(price * len(slots) * party, extras, add_ons),
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
    """Which vertical the current data was seeded from.

    Reads the seeder's own provenance stamp (`providers.metadata.seeded`) first:
    the row says what it was built from, so a vertical is nameable even when it
    shares a `booking_model` with another one. Only verticals that actually exist
    in `seed_data.VERTICALS` are trusted, which is what makes a config-derived
    seed (`seed_config` stamps `"config:<domain>"`) fall through rather than be
    echoed back as a vertical id that no caller can look up.

    Falls back to the old shape-based guess via `BOOKING_MODEL_TO_VERTICAL` for
    data seeded before the stamp existed, then to `DEFAULT_VERTICAL`. Never
    raises — callers treat it as best-effort provenance, not a source of truth.
    """
    try:
        rows = (
            get_supabase().table("providers").select("metadata").limit(5).execute().data or []
        )
        for row in rows:
            seeded = ((row.get("metadata") or {}).get("seeded")) or {}
            for key in ("verticalId", "source"):
                value = seeded.get(key)
                if isinstance(value, str) and value in VERTICALS:
                    return value
    except Exception:
        pass
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
