#!/usr/bin/env python3
"""Emit every pivot in `check_pivots.py` as a complete, drop-in `domain.config.json`.

The 100 pivots are stored as *fragments* — only the keys each business actually
changes — because that is what makes them readable as evidence. This script turns
each fragment into the whole file: merged over the tenancy base, run through the
engine's own `normalize()` (so every default is materialised) and `validate()`
(so nothing is written that the backend would refuse to boot on), then written to
`pivots/NNN-slug.json`.

    python3 scripts/generate_pivots.py            # write pivots/
    python3 scripts/generate_pivots.py --check    # verify on-disk files are current

Vocabulary the fragments do not carry (`domain`, `terms`, `copy`) is DERIVED here
from what the fragment does say — the business name and `booking.unitKind` — so
each file reads as that business rather than as "generic". Nothing derived can
change engine behaviour: `terms` and `copy` are the label layer.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(SCRIPTS))

from app.config_schema import normalize, validate  # noqa: E402
from seed_data import DEFAULT_VERTICAL, VERTICALS  # noqa: E402

from check_pivots import ALL, base, deep_merge  # noqa: E402

OUT_DIR = REPO_ROOT / "pivots"

# The harness bases every single-tenant pivot on a placeholder `providerCode`
# ("DEMO-0001"). That is fine there — it only ever validates the string's
# presence — but a drop-in config resolves *the* business through
# `GET /providers/by-code/{code}`, and a code no seed ever wrote 404s: single
# mode then renders "No business yet" on the owner dashboard and an empty
# customer view. So take the code from the seed itself. Index 0 is the provider
# the demo owner owns, which is what makes the owner dashboard populated.
SEEDED_PROVIDER_CODE = VERTICALS[DEFAULT_VERTICAL]["providers"][0]["publicCode"]

# --- derived vocabulary ----------------------------------------------------
# Keyed on `booking.unitKind`: the one field that already says what is being
# booked. Everything here is a label; none of it is read as behaviour.
UNIT_TERMS = {
    "time_slot":         ("Resource", "Resources", "Slot", "Slots", "Booking", "Bookings"),
    "staff":             ("Staff member", "Staff", "Appointment", "Appointments", "Appointment", "Appointments"),
    "asset":             ("Item", "Items", "Hire period", "Hire periods", "Hire", "Hires"),
    "seat":              ("Departure", "Departures", "Seat", "Seats", "Reservation", "Reservations"),
    "room":              ("Room", "Rooms", "Session", "Sessions", "Reservation", "Reservations"),
    "class_capacity":    ("Class", "Classes", "Session", "Sessions", "Place", "Places"),
    "stock_item":        ("Item", "Items", "Collection window", "Collection windows", "Order", "Orders"),
    "subscription_slot": ("Plan", "Plans", "Billing period", "Billing periods", "Subscription", "Subscriptions"),
    "project":           ("Project", "Projects", "Milestone", "Milestones", "Engagement", "Engagements"),
}
# The noun for a business and for what it sells. Left generic in the first pass,
# which is why a seeded marketplace came out as "Business 2" selling "Service";
# the seeder builds its provider and service names from these.
UNIT_BUSINESS = {
    "time_slot":         ("Business", "Businesses", "Service", "Services"),
    "staff":             ("Practice", "Practices", "Treatment", "Treatments"),
    "asset":             ("Hire shop", "Hire shops", "Hire", "Hires"),
    "seat":              ("Operator", "Operators", "Route", "Routes"),
    "room":              ("Venue", "Venues", "Room type", "Room types"),
    "class_capacity":    ("Studio", "Studios", "Class", "Classes"),
    "stock_item":        ("Shop", "Shops", "Product", "Products"),
    "subscription_slot": ("Provider", "Providers", "Plan", "Plans"),
    "project":           ("Studio", "Studios", "Engagement", "Engagements"),
}
PARTY_TERMS = {"individual": "Guests", "group": "Group", "buyout": "Whole group"}

# Cycled so neighbouring pivots are visually distinct when one is loaded.
PALETTE = ["#4f46e5", "#0d9488", "#b45309", "#be123c", "#7c3aed",
           "#0369a1", "#15803d", "#c2410c", "#a21caf", "#1f2937"]


# Letters NFKD leaves alone because they are letters in their own right, not an
# accented base — without these, "Kraków" slugs fine but "Floriańska" does not.
TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d",
                          "Đ": "D", "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe",
                          "Œ": "OE", "ı": "i", "&": " and "})


def slug(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name.translate(TRANSLIT))
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def vocabulary(pivot: dict, cfg: dict) -> dict:
    """Name, nouns and landing copy, derived from the fragment itself."""
    booking = cfg["booking"]
    resource, resources, slot_, slots, booking_n, bookings = UNIT_TERMS[booking["unitKind"]]
    provider, providers_, service, services_ = UNIT_BUSINESS[booking["unitKind"]]
    terms = dict(cfg["terms"])
    terms.update(resource=resource, resources=resources, slot=slot_, slots=slots,
                 booking=booking_n, bookings=bookings,
                 provider=provider, providers=providers_,
                 service=service, services=services_,
                 party=PARTY_TERMS[booking["party"]["mode"]])
    if booking["subject"]["enabled"]:
        terms["subject"] = booking["subject"]["noun"]
    if pivot["tenancy"] == "single":
        # One implicit business: the operator is "the studio/clinic/yard", not a
        # marketplace tenant, so the admin noun is the business's own name.
        terms["admin"] = terms["admins"] = pivot["name"]

    copy = dict(cfg["copy"])
    copy["landingTitle"] = pivot["name"]
    copy["landingSubtitle"] = f"{pivot['booked']} — {pivot['price'].lower()}."
    copy["emptyStateSlots"] = f"No {slots.lower()} available yet."
    copy["emptyStateBookings"] = f"You have no {bookings.lower()} yet."
    return {"terms": terms, "copy": copy}


def build(pivot: dict) -> dict:
    cfg = normalize(deep_merge(base(pivot["tenancy"]), pivot["config"]))
    if cfg["tenancy"]["mode"] == "single":
        cfg["tenancy"]["providerCode"] = SEEDED_PROVIDER_CODE
    cfg["domain"] = slug(pivot["name"])
    cfg.update(vocabulary(pivot, cfg))
    cfg["theme"] = dict(cfg["theme"], primaryColor=PALETTE[(pivot["n"] - 1) % len(PALETTE)])
    errors = validate(cfg)
    if errors:
        raise SystemExit(f"#{pivot['n']} {pivot['name']} does not validate:\n  " + "\n  ".join(errors))
    return cfg


def filename(pivot: dict) -> str:
    return f"{pivot['n']:03d}-{slug(pivot['name'])}.json"


def manifest_row(pivot: dict, cfg: dict) -> dict:
    return {
        "n": pivot["n"], "name": pivot["name"], "file": filename(pivot),
        "tenancy": pivot["tenancy"], "booked": pivot["booked"], "price": pivot["price"],
        "unitKind": cfg["booking"]["unitKind"], "pricingModel": cfg["pricing"]["model"],
        "currency": cfg["pricing"]["currency"], "timezone": cfg["location"]["timezone"],
        "capabilities": sorted(k for k, v in cfg["capabilities"].items() if v),
        "flags": pivot["flags"],
        "blocked": pivot.get("blocked"),
        "limitation": pivot.get("limitation"),
    }


AXIS_LABELS = {
    "U": "unit", "P": "pricing", "I": "inventory", "D": "duration", "L": "location",
    "Y": "party", "Q": "prerequisite", "T": "timing", "M": "money", "X": "probe",
}


def index_md(rows: list[dict]) -> str:
    single = sum(1 for r in rows if r["tenancy"] == "single")
    out = [
        "# Pivot library",
        "",
        f"{len(rows)} complete `domain.config.json` files — {single} single-tenant, "
        f"{len(rows) - single} marketplace — generated from the pivot definitions in",
        "`scripts/check_pivots.py` and `scripts/pivots_extended.py`.",
        "",
        "Regenerate with `python3 scripts/generate_pivots.py`. Load one with",
        "`python3 scripts/use_pivot.py <n>`. See [README.md](README.md).",
        "",
        "| # | Business | Tenancy | Bookable unit | Pricing | Currency | Capabilities on | Note |",
        "|---|----------|---------|---------------|---------|----------|-----------------|------|",
    ]
    for r in rows:
        caps = ", ".join(c for c in r["capabilities"] if c not in ("reviews", "follows")) or "—"
        note = ""
        if r["limitation"]:
            note = "schema gap"
        elif r["blocked"]:
            note = r["blocked"].split(" — ")[0]
        out.append(
            f"| {r['n']} | [{r['name']}]({r['file']}) | {r['tenancy']} | {r['unitKind']} | "
            f"{r['pricingModel']} | {r['currency']} | {caps} | {note} |"
        )
    out.append("")
    return "\n".join(out)


README = """# Pivot library

100 complete, validated `domain.config.json` files — one per business the engine
was designed to become. See [index.md](index.md) for the full table.

## Why they exist

`docs/PIVOT-SYSTEM.md` argues that a pivot is a config edit, not a rewrite, and
`docs/PIVOT-COVERAGE.md` proves it by running 100 businesses through the real
validator and pricing engine. But those 100 live in the harness as *fragments* —
only the keys each business changes. That is right for evidence and wrong for
use: you cannot drop a fragment into the repo and start the app.

This folder is the same 100 businesses as whole files. Each one boots.

## Using one

```bash
python3 scripts/use_pivot.py 3          # by number
python3 scripts/use_pivot.py escape     # by name substring
python3 scripts/use_pivot.py --list
python3 scripts/use_pivot.py --restore  # put the previous config back
```

`use_pivot.py` validates the file, backs up the current `domain.config.json` to
`domain.config.json.bak`, and copies the pivot into place. Then:

```bash
make reload    # drop the backend's cached config
make reseed    # rebuild the demo data
make checkseed # report where that data and the new config disagree
```

`make reseed` rebuilds the demo data **from the config** (via
`backend/seed_config.py`): currency, timezone, durations, prices, cutoffs, slot
capacity and the single-tenant provider code all come from the file you just
loaded, `pricing.tiers` become the catalogue, and `terms` supply the nouns.
`make checkseed` verifies it and names anything that still disagrees.

## How they are generated

`scripts/generate_pivots.py` merges each fragment over the tenancy base, runs the
engine's own `normalize()` (materialising every default, so the file is explicit
rather than relying on fill-in) and `validate()`, and writes the result. A pivot
that fails validation aborts the run — these files cannot drift from the schema.

Three things are **derived**, not taken from the fragment, because the fragments
never carried them:

- `domain` — a slug of the business name.
- `terms` — the resource/slot/booking nouns and the business/offering nouns,
  from `booking.unitKind`; the party noun from `booking.party.mode`; the subject
  noun from `booking.subject`. The seeder builds provider and service names out
  of these, so they are what makes reseeded demo data read as the right niche.
- `copy` — landing title/subtitle and the two empty states, from the name and the
  one-line description in the harness.

One value is **substituted**: single-tenant pivots get `tenancy.providerCode`
from the seed (`seed_data.VERTICALS[DEFAULT_VERTICAL].providers[0].publicCode`)
instead of the harness's `"DEMO-0001"` placeholder. Single mode resolves *the*
business through `GET /providers/by-code/{code}`; a code no seed ever wrote 404s,
and the app then shows "No business yet" on the owner dashboard and an empty
customer view. Reseed after switching (`make reseed`) so the code still resolves.

The rest are the label layer; none of them changes engine behaviour. Everything
that does — `capabilities`, `booking`, `pricing`, `payments`, `inventory`,
`location`, `prerequisites`, `timing`, `recurrence`, `entitlements`, `discovery`,
`tenancy` — comes from the pivot definition unchanged.

`theme.primaryColor` cycles through a ten-colour palette so two pivots loaded
back to back look different. It is cosmetic; the frontend does not read it yet.

## What these files do and do not prove

They prove the schema can **express** each business: every file here validates
against the same `app/config_schema.validate()` the backend boots on.

They do not prove the engine **enforces** every key in them. Enforcement is
narrower than the schema on purpose — `docs/PIVOT-SYSTEM.md` §6 lists what is
wired end to end, and the `blocked` / `limitation` columns in
[index.md](index.md) name, per business, what is still missing. A file marked
"schema gap" validates and quotes, but quotes the wrong model; the gap is
documented in `docs/PIVOT-COVERAGE.md`.

Regenerate after editing a pivot definition or adding a config key:

```bash
python3 scripts/generate_pivots.py
python3 scripts/generate_pivots.py --check   # CI-friendly: fails if stale
```
"""


def main() -> int:
    check = "--check" in sys.argv
    OUT_DIR.mkdir(exist_ok=True)

    rows, written, stale = [], [], []
    for pivot in ALL:
        cfg = build(pivot)
        rows.append(manifest_row(pivot, cfg))
        path = OUT_DIR / filename(pivot)
        body = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != body:
                stale.append(path.name)
        else:
            path.write_text(body, encoding="utf-8")
            written.append(path.name)

    extras = {
        "index.md": index_md(rows),
        "README.md": README,
        "manifest.json": json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
    }
    for name, body in extras.items():
        path = OUT_DIR / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != body:
                stale.append(name)
        else:
            path.write_text(body, encoding="utf-8")

    if check:
        if stale:
            print(f"stale ({len(stale)}): {', '.join(stale[:8])}"
                  f"{' ...' if len(stale) > 8 else ''}")
            print("run: python3 scripts/generate_pivots.py")
            return 1
        print(f"pivots/ is current — {len(rows)} configs, all validate")
        return 0

    orphans = [
        p for p in OUT_DIR.glob("*.json")
        if p.name != "manifest.json" and p.name not in written
    ]
    for p in orphans:
        p.unlink()
    print(f"wrote {len(written)} configs to {OUT_DIR.relative_to(REPO_ROOT)}/ "
          f"(+ index.md, README.md, manifest.json)"
          + (f"; removed {len(orphans)} stale file(s)" if orphans else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
