"""Aggregation helpers shared by the discovery routers (providers/services/
resources). Providers carry derived `rating`/`reviewCount` (from `reviews`) and
`serviceIds`; services carry `resourceIds`. At demo scale these are computed by
fetching the small tables and grouping in Python — no per-row round trips.
All reads use the service-key client (public discovery bypasses RLS)."""
from __future__ import annotations

from collections import defaultdict

from app.serialize import serialize_provider, serialize_resource, serialize_service


def review_aggregates(db) -> tuple[dict[str, float], dict[str, int]]:
    """Return (rating_sum_by_provider, count_by_provider) over real reviews.
    serialize_provider pools these with the seeded baseline in metadata."""
    rows = db.table("reviews").select("provider_id,rating").execute().data or []
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        sums[r["provider_id"]] += float(r["rating"])
        counts[r["provider_id"]] += 1
    return dict(sums), dict(counts)


def service_ids_by_provider(db) -> dict[str, list[str]]:
    rows = db.table("services").select("id,provider_id").execute().data or []
    by: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by[r["provider_id"]].append(r["id"])
    return by


def price_from_by_provider(db) -> dict[str, tuple[int, str]]:
    """(min_price_minor_units, currency) per provider — the cheapest of its
    services, so discovery can expose a provider-level `priceFromMinorUnits`
    for price ordering. Providers with no services are simply absent."""
    rows = db.table("services").select("provider_id,price_minor_units,currency").execute().data or []
    by: dict[str, tuple[int, str]] = {}
    for r in rows:
        pid = r["provider_id"]
        price = int(r.get("price_minor_units") or 0)
        cur = r.get("currency") or ""
        if pid not in by or price < by[pid][0]:
            by[pid] = (price, cur)
    return by


def resource_ids_by_service(db) -> dict[str, list[str]]:
    rows = db.table("resources").select("id,metadata").execute().data or []
    by: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        md = r.get("metadata") or {}
        sid = md.get("service_id")
        if sid and md.get("active", True):
            by[sid].append(r["id"])
    return by


def build_provider(row, *, svc_by_prov, sums, counts, price_by_prov=None) -> dict:
    price_from, currency = (price_by_prov or {}).get(row["id"], (None, ""))
    return serialize_provider(
        row,
        service_ids=svc_by_prov.get(row["id"], []),
        review_sum=sums.get(row["id"], 0.0),
        review_count=counts.get(row["id"], 0),
        price_from=price_from,
        currency=currency,
    )


def build_service(row, *, res_by_svc) -> dict:
    return serialize_service(row, resource_ids=res_by_svc.get(row["id"], []))
