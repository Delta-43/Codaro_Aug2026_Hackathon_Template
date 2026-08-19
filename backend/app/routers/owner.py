"""Owner (business) dashboard API — powers the 5 business-mode tabs.

This is the aggregation seam for the provider-facing app (Dashboard / Services /
Requests / Calendar / Profile). Everything here is owner-gated and scoped to the
providers the caller owns (`providers.owner_id == auth.uid()`); the client-facing
Profile a prospect browses is still served by the public `/providers/{id}`.

Reads use the service key (system aggregation over the owner's own small tables,
mirroring `discovery.py` / `resources` analytics). Booking mutations (approve /
reject) live in `bookings.py`, not here — this router is read-only.

Shapes are additive and owner-only: standard camelCase entities (`Provider`,
`Service`, `Booking`) plus aggregate envelopes (`stats`, `glance`, `client`).
Time windows are computed in UTC; the frontend localizes from the `*Utc` fields.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from app import discovery
from app.auth import AuthUser, require_owner
from app.db import chunked, fetch_all, get_supabase
from app.routers.bookings import _enrich
from app.serialize import iso_utc
from app.clock import now_utc, tz_or_utc

router = APIRouter(prefix="/owner", tags=["owner"])


# --- time windows ----------------------------------------------------------


def _month_bounds(ref: datetime, tz) -> tuple[datetime, datetime, datetime]:
    """(last-month-start, this-month-start, next-month-start) as UTC instants,
    with the month boundaries taken in `tz` — so this month is
    [this_start, next_start) and last month is [last_start, this_start)."""
    local = ref.astimezone(tz)
    this_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_local = (this_local - timedelta(days=1)).replace(day=1)
    next_local = (this_local + timedelta(days=32)).replace(day=1)
    to_utc = lambda dt: dt.astimezone(timezone.utc)
    return to_utc(last_local), to_utc(this_local), to_utc(next_local)


def _week_bounds(ref: datetime, tz) -> tuple[datetime, datetime]:
    """Monday 00:00 (in `tz`) of the current week → the following Monday
    (exclusive), returned as UTC instants."""
    local = ref.astimezone(tz)
    start = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)


def _in_window(iso: str | None, lo: str, hi: str) -> bool:
    """ISO-Z timestamps share one fixed format, so lexicographic compare == time
    compare. `lo` inclusive, `hi` exclusive."""
    return bool(iso and lo <= iso < hi)


# --- owner scope -----------------------------------------------------------


class _Scope:
    """The owner's providers/services/resources/bookings, gathered once."""

    def __init__(self, db, owner: AuthUser):
        self.db = db
        self.providers = (
            db.table("providers").select("*").eq("owner_id", owner.id).execute().data or []
        )
        self.provider_ids = [p["id"] for p in self.providers]

        self.services = (
            fetch_all(db.table("services").select("*").in_("provider_id", self.provider_ids))
            if self.provider_ids
            else []
        )
        self.service_ids = {s["id"] for s in self.services}

        # Filter server-side on the jsonb path (PostgREST accepts arrow paths
        # in filter columns) — fetching the whole table paged every tenant's
        # rows per owner request. The Python filter stays as belt-and-braces.
        all_resources = []
        # Chunked like _screening_data: hundreds of ids in one `.in_` request
        # line 414 outright, where the pre-filter code merely paged slowly.
        for chunk in chunked(sorted(self.service_ids)):
            all_resources += fetch_all(
                db.table("resources").select("*")
                .in_("metadata->>service_id", chunk)
            )
        self.resources = [
            r for r in all_resources
            if (r.get("metadata") or {}).get("service_id") in self.service_ids
        ]

        # Bookings for the owner's providers — filtered in Python from the small
        # demo tables (booking.provider_id lives in metadata jsonb; no column to
        # PostgREST-filter on). Enriched with span/slot ids + the client email.
        # Scoped server-side on metadata->>provider_id, then paged: the service
        # key sees EVERY booking platform-wide, so an unfiltered fetch paged
        # all tenants' rows per owner request (and the old raw select silently
        # truncated at 1000).
        prov_set = set(self.provider_ids)
        raw = []
        for chunk in chunked(self.provider_ids):
            raw += fetch_all(
                db.table("bookings").select("*")
                .in_("metadata->>provider_id", chunk)
            )
        raw = [b for b in raw if (b.get("metadata") or {}).get("provider_id") in prov_set]
        self.bookings = _enrich(db, db, raw, include_client=True)

    def primary_provider(self) -> dict | None:
        return self.providers[0] if self.providers else None

    def serialized_providers(self) -> list[dict]:
        sums, counts = discovery.review_aggregates(self.db)
        svc = discovery.service_ids_by_provider(self.db)
        return [
            discovery.build_provider(p, svc_by_prov=svc, sums=sums, counts=counts)
            for p in self.providers
        ]

    def service_name(self, service_id: str) -> str:
        for s in self.services:
            if s["id"] == service_id:
                return s["name"]
        return ""

    def provider_name(self, provider_id: str) -> str:
        for p in self.providers:
            if p["id"] == provider_id:
                return p["name"]
        return ""


def _service_currency(scope: _Scope) -> str:
    for s in scope.services:
        if s.get("currency"):
            return s["currency"]
    return "EUR"


# --- reviews grouped per service (reviews are keyed by booking) -------------


def _ratings_by_service(scope: _Scope) -> dict[str, list[int]]:
    """Map service_id → the ratings of reviews on that service's bookings.
    `reviews` carries booking_id + provider_id, so we resolve the service via the
    booking. Reuses the bookings `_Scope` already loaded (a review on one of the
    owner's services is always on a booking for one of the owner's providers), so
    no second scan of the bookings table."""
    booking_service = {b["id"]: b["serviceId"] for b in scope.bookings}
    out: dict[str, list[int]] = defaultdict(list)
    # reviews carries a real, indexed provider_id column — no full-table scan.
    rows = fetch_all(
        scope.db.table("reviews").select("id,booking_id,rating")
        .in_("provider_id", scope.provider_ids)
    ) if scope.provider_ids else []
    for r in rows:
        sid = booking_service.get(r["booking_id"])
        if sid in scope.service_ids:
            out[sid].append(int(r["rating"]))
    return out


# --- client screening ------------------------------------------------------


def _screening_data(
    db, client_ids: set[str]
) -> tuple[dict[str, list[dict]], dict[str, list[int]]]:
    """Batch the two per-client screening reads — booking history and the
    ratings businesses left each client — into one query each for the whole set
    of pending clients, grouped by client_id. Replaces the previous 2×N per-card
    round trips with 2 total. Both use `.in_` on the real `client_id` column."""
    ids = [c for c in client_ids if c]
    bookings_by: dict[str, list[dict]] = defaultdict(list)
    ratings_by: dict[str, list[int]] = defaultdict(list)
    if not ids:
        return bookings_by, ratings_by

    # Chunked: pending requests never expire, so the distinct-client list is
    # unbounded and one giant `.in_` overflows the request line (414).
    for chunk in chunked(ids):
        for r in fetch_all(
            db.table("bookings").select("id,client_id,status,metadata").in_("client_id", chunk)
        ):
            bookings_by[r["client_id"]].append(r)

    # Degrades to no ratings if the table isn't present (e.g. offline fake).
    try:
        for chunk in chunked(ids):
            for r in fetch_all(
                db.table("client_reviews").select("id,client_id,rating").in_("client_id", chunk)
            ):
                ratings_by[r["client_id"]].append(int(r["rating"]))
    except Exception:
        pass
    return bookings_by, ratings_by


def _client_profile(
    db,
    client_id: str,
    email: str,
    provider_ids: set[str],
    booking_rows: list[dict],
    ratings: list[int],
) -> dict:
    """Screening card for the Requests tab: how long they've been a member, how
    much history they have with us, and any red-flag counts. Booking history and
    ratings are pre-batched by `_screening_data`; only the auth user's
    created_at/profile still needs a per-client admin lookup."""
    member_since = None
    display_name = (email or "").split("@")[0]
    avatar_url = ""
    try:
        resp = db.auth.admin.get_user_by_id(client_id)
        u = getattr(resp, "user", None) or resp
        member_since = iso_utc(getattr(u, "created_at", None))
        md = getattr(u, "user_metadata", None) or {}
        display_name = md.get("display_name") or md.get("displayName") or display_name
        avatar_url = md.get("avatar_url") or md.get("avatarUrl") or ""
    except Exception:
        pass  # admin API unavailable — degrade to what we can derive

    total = len(booking_rows)
    with_us = [r for r in booking_rows if (r.get("metadata") or {}).get("provider_id") in provider_ids]
    cancelled = sum(1 for r in with_us if r["status"] == "cancelled")

    return {
        "id": client_id,
        "displayName": display_name,
        "email": email,
        "avatarUrl": avatar_url,
        "memberSinceUtc": member_since,
        "totalBookings": total,
        "bookingsWithProvider": len(with_us),
        "cancelledWithProvider": cancelled,
        "rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "reviewCount": len(ratings),
    }


def _request_cards(scope: _Scope, *, limit: int | None = None) -> list[dict]:
    """Pending requests across the owner's providers, each enriched with the
    client screening card + service/provider names. Newest request first."""
    pending = [b for b in scope.bookings if b["status"] == "pending"]
    pending.sort(key=lambda b: b.get("createdAtUtc") or "", reverse=True)
    if limit is not None:
        pending = pending[:limit]

    prov_set = set(scope.provider_ids)
    bookings_by, ratings_by = _screening_data(
        scope.db, {b.get("userId") or "" for b in pending}
    )
    cache: dict[str, dict] = {}
    out = []
    for b in pending:
        cid = b.get("userId") or ""
        if cid not in cache:
            cache[cid] = _client_profile(
                scope.db,
                cid,
                b.get("clientEmail") or "",
                prov_set,
                bookings_by.get(cid, []),
                ratings_by.get(cid, []),
            )
        # b already carries providerName/serviceName (embedded by serialize_booking
        # via _enrich), so only the screening card needs adding here.
        out.append({**b, "client": cache[cid]})
    return out


# --- endpoints -------------------------------------------------------------


@router.get("/dashboard")
def owner_dashboard(owner: AuthUser = Depends(require_owner)):
    """Tab 1 — the at-a-glance overview: badge (primary provider), the three
    glanceable numbers, this week's bookings, and the top pending requests."""
    db = get_supabase()
    scope = _Scope(db, owner)
    now = now_utc()
    now_iso = iso_utc(now)
    tz = tz_or_utc((owner.claims.get("user_metadata") or {}).get("timezone"))
    last_start, month_start, next_start = _month_bounds(now, tz)
    ls_iso, ms_iso, ns_iso = iso_utc(last_start), iso_utc(month_start), iso_utc(next_start)
    week_lo, week_hi = _week_bounds(now, tz)
    wl_iso, wh_iso = iso_utc(week_lo), iso_utc(week_hi)
    horizon_iso = iso_utc(now + timedelta(days=30))  # rolling window, not a calendar boundary

    active = [b for b in scope.bookings if b["status"] in ("confirmed", "completed")]

    # Upcoming confirmed bookings in the next 30 days, grouped by service.
    upcoming = [
        b for b in scope.bookings
        if b["status"] == "confirmed" and _in_window(b["startUtc"], now_iso, horizon_iso)
    ]
    by_service_counts: dict[str, int] = defaultdict(int)
    for b in upcoming:
        by_service_counts[b["serviceId"]] += 1
    by_service = [
        {"serviceId": sid, "serviceName": scope.service_name(sid), "count": n}
        for sid, n in sorted(by_service_counts.items(), key=lambda kv: -kv[1])
    ]

    # Revenue this calendar month, broken out per currency (a single sum across
    # currencies would be meaningless), + month-over-month popularity delta.
    month_active = [b for b in active if _in_window(b["startUtc"], ms_iso, ns_iso)]
    rev_by_currency: dict[str, int] = defaultdict(int)
    for b in month_active:
        rev_by_currency[b["currency"]] += b["priceMinorUnits"]
    by_currency = sorted(
        ({"currency": c, "minorUnits": m} for c, m in rev_by_currency.items()),
        key=lambda e: -e["minorUnits"],
    )
    # Headline number is the dominant currency's own total (never a cross-currency
    # sum); single-currency owners are unchanged.
    headline_currency = by_currency[0]["currency"] if by_currency else _service_currency(scope)
    headline_revenue = by_currency[0]["minorUnits"] if by_currency else 0
    this_month = len(month_active)
    last_month = sum(1 for b in active if _in_window(b["startUtc"], ls_iso, ms_iso))
    if last_month:
        delta_pct = round((this_month - last_month) / last_month * 100)
    else:
        delta_pct = 100 if this_month else 0

    serialized_providers = scope.serialized_providers()
    primary_serialized = serialized_providers[0] if serialized_providers else None

    # Satisfaction pools reviews across ALL the owner's providers (revenue and
    # upcoming already span them), weighting each provider's rating by its count.
    total_reviews = sum(p["reviewCount"] for p in serialized_providers)
    if total_reviews:
        pooled_rating = round(
            sum(p["rating"] * p["reviewCount"] for p in serialized_providers) / total_reviews, 1
        )
    else:
        pooled_rating = 0.0

    week_bookings = sorted(
        [b for b in active if _in_window(b["startUtc"], wl_iso, wh_iso)],
        key=lambda b: b["startUtc"] or "",
    )
    pending_count = sum(1 for b in scope.bookings if b["status"] == "pending")

    return {
        "provider": primary_serialized,
        "providers": serialized_providers,
        "glance": {
            "upcomingBookings": {"total": len(upcoming), "byService": by_service},
            "clientSatisfaction": {
                "currentRating": pooled_rating,
                "reviewCount": total_reviews,
                "deltaPct": delta_pct,
                "basis": "bookings_month_over_month",
            },
            "revenue": {
                "minorUnits": headline_revenue,
                "currency": headline_currency,
                "byCurrency": by_currency,
                "bookingCount": this_month,
                "period": now.astimezone(tz).strftime("%Y-%m"),
            },
        },
        "weekBookings": week_bookings,
        "requests": _request_cards(scope, limit=5),
        "pendingCount": pending_count,
    }


@router.get("/services")
def owner_services(owner: AuthUser = Depends(require_owner)):
    """Tab 2 — each of the owner's services with glanceable stats (price,
    upcoming/past bookings, revenue, rating, pending requests)."""
    db = get_supabase()
    scope = _Scope(db, owner)
    now_iso = iso_utc(now_utc())
    res_by_svc = discovery.resource_ids_by_service(db)
    ratings = _ratings_by_service(scope)

    # Pre-bucket bookings by service so each service is one pass, not a scan.
    by_service: dict[str, list[dict]] = defaultdict(list)
    for b in scope.bookings:
        by_service[b["serviceId"]].append(b)

    out = []
    for s in scope.services:
        svc = discovery.build_service(s, res_by_svc=res_by_svc)
        bookings = by_service.get(s["id"], [])
        upcoming = sum(
            1 for b in bookings if b["status"] == "confirmed" and (b["startUtc"] or "") >= now_iso
        )
        past = sum(1 for b in bookings if b["status"] == "completed")
        pending = sum(1 for b in bookings if b["status"] == "pending")
        revenue = sum(
            b["priceMinorUnits"] for b in bookings if b["status"] in ("confirmed", "completed")
        )
        svc_ratings = ratings.get(s["id"], [])
        avg_rating = round(sum(svc_ratings) / len(svc_ratings), 1) if svc_ratings else 0.0
        out.append(
            {
                **svc,
                "providerName": scope.provider_name(s["provider_id"]),
                "stats": {
                    "upcomingBookings": upcoming,
                    "pastBookings": past,
                    "totalBookings": upcoming + past,
                    "pendingRequests": pending,
                    "revenueMinorUnits": revenue,
                    "currency": svc["currency"],
                    "avgRating": avg_rating,
                    "reviewCount": len(svc_ratings),
                },
            }
        )
    return out


@router.get("/requests")
def owner_requests(owner: AuthUser = Depends(require_owner)):
    """Tab 3 — every pending request across the owner's providers, each with the
    requesting client's screening card. Approve/reject via /bookings/{id}/*."""
    db = get_supabase()
    scope = _Scope(db, owner)
    return _request_cards(scope)


@router.get("/calendar")
def owner_calendar(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    owner: AuthUser = Depends(require_owner),
):
    """Tab 4 — approved (confirmed/completed) bookings across the owner's
    resources within a window (defaults to the current calendar month), sorted
    by start. Query params: `from` / `to` (ISO-Z)."""
    db = get_supabase()
    scope = _Scope(db, owner)
    now = now_utc()
    tz = tz_or_utc((owner.claims.get("user_metadata") or {}).get("timezone"))
    _, month_start, next_start = _month_bounds(now, tz)
    lo = from_ or iso_utc(month_start)
    hi = to or iso_utc(next_start)

    rows = [
        b for b in scope.bookings
        if b["status"] in ("confirmed", "completed") and _in_window(b["startUtc"], lo, hi)
    ]
    rows.sort(key=lambda b: b["startUtc"] or "")
    return rows
