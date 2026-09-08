# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generate the static catalogue the `/showcase` page falls back to.

`/showcase` normally calls `GET /services` and `GET /providers`. A deployment
with no backend (the frontend published on its own, as a portfolio piece) has
nothing to call, so the page would show an error where its catalogue belongs.

This writes that catalogue out ahead of time. It builds the same rows
`backend/seed.py` inserts, from the same `seed_data.VERTICALS` specs, then runs
them through the backend's own `serialize_provider` / `serialize_service`. The
output is therefore shaped by the real serializer rather than by a hand-written
guess that would drift the first time a field is added.

Images come out as the seeder's deterministic SVG data URIs, so the snapshot
needs no media host either.

    python3 scripts/gen_showcase_snapshot.py
    python3 scripts/gen_showcase_snapshot.py --check   # CI: fails if stale
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

import seed_data  # noqa: E402
from seed import avatar_uri, cover_uri, tile_uri  # noqa: E402
from app.serialize import serialize_provider, serialize_service  # noqa: E402

OUT_PATH = REPO_ROOT / "frontend" / "src" / "showcase-catalogue.generated.json"
VERTICAL = "funeral"

# A fixed namespace keeps ids stable between runs, so regenerating produces no
# diff unless the underlying seed data actually changed.
NS = uuid.UUID("a7b0c1d2-e3f4-5a6b-8c9d-0e1f2a3b4c5d")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


def build() -> dict:
    cfg = seed_data.VERTICALS[VERTICAL]
    currency, model = cfg["currency"], cfg["bookingModel"]
    providers, services = [], []

    for i, p in enumerate(cfg["providers"]):
        pid = _id("provider", p["name"])
        # Mirrors the provider row seed.py inserts, minus the `seeded` block,
        # which only exists so the running backend can identify the vertical.
        row = {
            "id": pid,
            "name": p["name"],
            "public_code": p["publicCode"],
            "category_id": p["categoryId"],
            "metadata": {
                "avatar_url": avatar_uri(p["name"], p["name"]),
                "cover_url": cover_uri(p["name"]),
                "tagline": p["tagline"],
                "bio": p["bio"],
                "location": {"city": p["city"], "country": p["country"],
                             "lat": p["lat"], "lng": p["lng"]},
                "links": p.get("links") or [],
                "rating": p["rating"],
                "review_count": p["reviewCount"],
            },
        }

        # Provider 0 is the demo provider and carries the whole demoServices
        # catalogue; every other provider carries one headline service. Same
        # split as seed.py, so the snapshot lists what the seeded app lists.
        specs = cfg["demoServices"] if i == 0 else [p.get("service") or cfg["simpleService"]]
        own_ids = []
        for si, spec in enumerate(specs):
            sid = _id("service", p["name"], spec["name"], str(si))
            own_ids.append(sid)
            resources = spec.get("resources") or (
                [spec["resource"]] if spec.get("resource") else []
            )
            resource_ids = [_id("resource", sid, r["name"]) for r in resources]
            services.append(serialize_service({
                "id": sid,
                "provider_id": pid,
                "name": spec["name"],
                "description": spec["description"],
                "booking_model": model,
                "slot_duration_minutes": spec["slotDurationMinutes"],
                "min_slots_per_booking": spec["minSlotsPerBooking"],
                "max_slots_per_booking": spec["maxSlotsPerBooking"],
                "price_minor_units": spec["priceMinorUnits"],
                "currency": currency,
                "cancellation_cutoff_hours": spec["cancellationCutoffHours"],
                "metadata": {
                    **(spec.get("metaFields", {}).get("service") or {}),
                    "image_url": tile_uri(spec["name"], spec["name"]),
                    "auto_approve": (si != 0) if i == 0 else True,
                },
            }, resource_ids=resource_ids))

        prices = [s["priceMinorUnits"] for s in services if s["providerId"] == pid]
        providers.append(serialize_provider(
            row,
            service_ids=own_ids,
            price_from=min(prices) if prices else None,
            currency=currency if prices else "",
        ))

    # Project onto only what `/showcase` renders. A faithful mirror of the API
    # response is 200 KB, and 95% of that is resolved config blocks (`options`,
    # `subject`, `prerequisites`) that this page never reads, plus SVG data URIs
    # for artwork it never draws — `ServicePanel` uses the animation instead.
    # The fields survive `serialize_*` first so their NAMES come from the real
    # serializer (`providerId`, not `provider_id`) rather than from a guess here.
    return {
        "services": [
            {k: s[k] for k in ("id", "providerId", "name", "description",
                               # read by `formatOffer` for the price line
                               "priceMinorUnits", "currency", "pricingModel", "rateUnit")}
            for s in services
        ],
        "providers": [{k: p[k] for k in ("id", "name")} for p in providers],
    }


def main() -> int:
    body = json.dumps(build(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT_PATH.exists():
            print(f"{OUT_PATH.name} is missing — run: python3 scripts/gen_showcase_snapshot.py")
            return 1
        if OUT_PATH.read_text(encoding="utf-8") != body:
            print(f"{OUT_PATH.name} is stale — the seed data changed.\n"
                  "Run: python3 scripts/gen_showcase_snapshot.py")
            return 1
        print(f"{OUT_PATH.name} is current")
        return 0
    OUT_PATH.write_text(body, encoding="utf-8")
    d = json.loads(body)
    print(f"wrote {OUT_PATH.name} — {len(d['services'])} services, "
          f"{len(d['providers'])} providers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
