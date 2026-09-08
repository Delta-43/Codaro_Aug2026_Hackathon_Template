# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Aggregation helpers shared by the discovery routers (providers/services/
resources). Providers carry derived `rating`/`reviewCount` (from `reviews`) and
`serviceIds`; services carry `resourceIds`. At demo scale these are computed by
fetching the small tables and grouping in Python — no per-row round trips.
All reads use the service-key client (public discovery bypasses RLS)."""
from __future__ import annotations

from collections import defaultdict

from app.config import get_config
from app.db import fetch_all
from app.rules import effective_service_pricing
from app.serialize import serialize_provider, serialize_service


def review_aggregates(db) -> tuple[dict[str, float], dict[str, int]]:
    """Return (rating_sum_by_provider, count_by_provider) over real reviews.
    serialize_provider pools these with the seeded baseline in metadata."""
    rows = fetch_all(db.table("reviews").select("provider_id,rating"))
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        sums[r["provider_id"]] += float(r["rating"])
        counts[r["provider_id"]] += 1
    return dict(sums), dict(counts)


def service_ids_by_provider(db) -> dict[str, list[str]]:
    rows = fetch_all(db.table("services").select("id,provider_id"))
    by: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by[r["provider_id"]].append(r["id"])
    return by


# The columns `effective_service_pricing` needs to resolve one service's price:
# the legacy columns plus the `metadata.pricing` block that overrides them.
_PRICING_COLUMNS = "provider_id,price_minor_units,currency,metadata"


def _global_price_fallback() -> tuple[int, str]:
    """What `effective_service_pricing` resolves to for a service that declares
    no `metadata.pricing` and whose own columns are unset. Hoisted out of the
    row loop because it is the same for every row in a scan."""
    pricing = get_config().get("pricing") or {}
    return int((pricing.get("rate") or {}).get("amountMinorUnits") or 0), pricing.get("currency") or ""


def _resolved_price(row: dict, fallback: tuple[int, str]) -> tuple[int, str]:
    """(amount, currency) as the service is ACTUALLY quoted and advertised.

    Reading `price_minor_units` directly skipped `metadata.pricing`, so a service
    priced only through an override reported 0 here while `serialize_service`
    reported (and `quote()` charged) the real amount — the provider's
    `priceFromMinorUnits` and the whole `price` search facet were computed from a
    number nothing else in the engine used.

    Only rows that actually declare an override pay for the full resolve. Both
    callers scan the WHOLE services table, and `effective_service_pricing` merges
    the global block and re-validates every declared block, so doing it per row
    turned a column read into ~0.1 ms of work per overridden service on the
    provider-list, my-providers, update-provider, get-provider and /config paths.
    For a row with no `pricing` block the resolver provably returns the columns
    themselves — `price_minor_units` and `currency` are NOT NULL DEFAULT, and the
    fold-in below `_merge` copies them over the global block unconditionally — so
    the fast path is the same answer, not an approximation. An override that is
    INVALID still takes the slow path and is still dropped there, which is the
    behaviour that keeps a typo'd block priced from its own column."""
    if isinstance((row.get("metadata") or {}).get("pricing"), dict):
        pricing = effective_service_pricing(row)
        return (
            int((pricing.get("rate") or {}).get("amountMinorUnits") or 0),
            pricing.get("currency") or "",
        )
    amount, currency = fallback
    price = row.get("price_minor_units")
    return int(price if price is not None else amount), (row.get("currency") or currency)


def price_from_by_provider(db) -> dict[str, tuple[int, str]]:
    """(min_price_minor_units, currency) per provider — the cheapest of its
    services, so discovery can expose a provider-level `priceFromMinorUnits`
    for price ordering. Providers with no services are simply absent."""
    rows = fetch_all(db.table("services").select(_PRICING_COLUMNS))
    fallback = _global_price_fallback()
    by: dict[str, tuple[int, str]] = {}
    for r in rows:
        pid = r["provider_id"]
        price, cur = _resolved_price(r, fallback)
        if pid not in by or price < by[pid][0]:
            by[pid] = (price, cur)
    return by


def resource_ids_by_service(db) -> dict[str, list[str]]:
    rows = fetch_all(db.table("resources").select("id,metadata"))
    by: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        md = r.get("metadata") or {}
        sid = md.get("service_id")
        if sid and md.get("active", True):
            by[sid].append(r["id"])
    return by


def search_facets(db) -> dict[str, bool]:
    """Which search facets the current catalog actually supports — derived from
    the seeded data so the filter UI pivots automatically, with no hand-kept
    flags. A free niche seeds no priced services → `price` off; a remote niche
    seeds no real coordinates → `distance` off; those sliders/sort keys then
    never render. `rating` is always offered (every provider carries one)."""
    services = fetch_all(db.table("services").select(_PRICING_COLUMNS))
    fallback = _global_price_fallback()
    # `any` over a generator stops at the first priced service.
    has_price = any(_resolved_price(s, fallback)[0] > 0 for s in services)

    providers = fetch_all(db.table("providers").select("metadata"))

    def has_coords(row: dict) -> bool:
        loc = (row.get("metadata") or {}).get("location") or {}
        return bool(loc) and (float(loc.get("lat") or 0) != 0 or float(loc.get("lng") or 0) != 0)

    has_distance = any(has_coords(p) for p in providers)
    return {"price": has_price, "distance": has_distance, "rating": True}


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
