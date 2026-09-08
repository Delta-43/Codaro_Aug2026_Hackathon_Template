#!/usr/bin/env python3
# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Does the seeded database actually match the loaded `domain.config.json`?

    docker compose exec backend python /workspace/scripts/check_seed.py
    docker compose exec backend python /workspace/scripts/check_seed.py -v

Swapping the pivot file changes what the ENGINE believes. It does not change
what is in the DB. This script reports, per dimension, whether the two agree —
so "I pivoted and nothing looks different" becomes a list of specific
mismatches instead of a guess.

Two things it deliberately keeps apart:

  RESET  — did the wipe leave a clean, consistent dataset?
           (`seed_vertical()` truncates and rebuilds; this checks the result.)
  MATCH  — does that dataset correspond to the config now loaded?

RESET failures are bugs. MATCH failures mostly are not: `seed.py` seeds from
`seed_data.VERTICALS`, never from the config, and a seeded service COLUMN
outranks the config default by design (`rules._SERVICE_RULE_MAP`). So a fresh
pivot is EXPECTED to report match failures until the seed learns to read the
config. Naming them is the point.

Exit code: non-zero if any RESET check fails, or with --strict if any check does.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_config  # noqa: E402
from app.db import get_supabase  # noqa: E402
from app.rules import _SERVICE_RULE_MAP  # noqa: E402
from seed import _EXTENDED_TABLES, BOOKING_MODEL_TO_VERTICAL, active_vertical  # noqa: E402
from seed_data import VERTICALS  # noqa: E402

# THIS SCRIPT'S OWN heuristic, not the engine's — no mapping between
# `booking.unitKind` and `services.booking_model` exists anywhere in the code.
# Only clear contradictions are flagged; an unlisted unitKind is not judged.
UNIT_KIND_TO_MODEL = {
    "staff": "one_to_one",
    "class_capacity": "shared_capacity",
    "seat": "shared_capacity",
    "asset": "unit_selection",
    "room": "unit_selection",
    "stock_item": "unit_selection",
}

VERBOSE = "-v" in sys.argv
STRICT = "--strict" in sys.argv

RESET, MATCH = "RESET", "MATCH"
results: list[tuple[str, str, str, str]] = []  # (kind, status, title, detail)


def record(kind: str, ok: bool, title: str, detail: str = "") -> None:
    results.append((kind, "ok" if ok else "FAIL", title, detail))


def rows(db, table: str, select: str = "*", limit: int = 5000) -> list[dict]:
    try:
        return db.table(table).select(select).limit(limit).execute().data or []
    except Exception as exc:  # a table the deployment does not have
        record(RESET, False, f"read {table}", str(exc)[:120])
        return []


# --- RESET: is the dataset internally consistent after the wipe? ------------
def check_reset(db) -> dict:
    counts, data = {}, {}
    for table in _EXTENDED_TABLES:
        try:
            res = db.table(table).select("id" if table not in ("booking_slots", "follows") else "*",
                                         count="exact").limit(1).execute()
            counts[table] = res.count
        except Exception as exc:
            counts[table] = None
            record(RESET, False, f"count {table}", str(exc)[:120])

    record(RESET, bool(counts.get("providers")), "providers present",
           f"{counts.get('providers')} rows — a wipe that did not rebuild leaves 0")
    record(RESET, bool(counts.get("slots")), "slots present", f"{counts.get('slots')} rows")

    # Referential integrity: the truncate is `cascade`, so a survivor pointing at
    # a deleted parent means the rebuild, not the wipe, went wrong.
    data["providers"] = rows(db, "providers", "id,public_code,name,owner_id,metadata")
    data["services"] = rows(db, "services", "id,provider_id,booking_model,slot_duration_minutes,"
                                            "min_slots_per_booking,max_slots_per_booking,"
                                            "price_minor_units,currency,cancellation_cutoff_hours,metadata")
    data["resources"] = rows(db, "resources", "id,metadata")
    data["slots"] = rows(db, "slots", "id,resource_id,starts_at,ends_at,capacity,metadata")

    provider_ids = {p["id"] for p in data["providers"]}
    service_ids = {s["id"] for s in data["services"]}
    resource_ids = {r["id"] for r in data["resources"]}

    orphan_svc = [s["id"] for s in data["services"] if s["provider_id"] not in provider_ids]
    record(RESET, not orphan_svc, "every service has a provider", f"{len(orphan_svc)} orphaned")

    orphan_res = [r["id"] for r in data["resources"]
                  if (r.get("metadata") or {}).get("service_id") not in service_ids]
    record(RESET, not orphan_res, "every resource has a service", f"{len(orphan_res)} orphaned")

    orphan_slot = [s["id"] for s in data["slots"] if s["resource_id"] not in resource_ids]
    record(RESET, not orphan_slot, "every slot has a resource", f"{len(orphan_slot)} orphaned")

    # `metadata.attributes` is free-form jsonb but has a published shape
    # ([{label,value}]); a dict there rendered the provider page unmountable.
    bad_attrs = [
        r["id"] for r in data["resources"]
        if not isinstance((r.get("metadata") or {}).get("attributes", []), list)
    ]
    record(RESET, not bad_attrs, "resource attributes are [{label,value}] lists",
           f"{len(bad_attrs)} resource(s) carry a non-list — the provider page maps over this")

    dupes = [c for c, n in Counter(p["public_code"] for p in data["providers"]).items() if n > 1]
    record(RESET, not dupes, "provider codes unique", f"duplicated: {dupes}" if dupes else "")

    owned = [p for p in data["providers"] if p.get("owner_id")]
    record(RESET, bool(owned), "a provider is owned by the demo owner",
           f"{len(owned)} owned — without one the owner dashboard is empty")

    try:
        n = db.table("profiles").select("id", count="exact").limit(1).execute().count
        record(RESET, bool(n), "profiles survived the wipe", f"{n} rows (auth users are not truncated)")
    except Exception as exc:
        record(RESET, False, "profiles readable", str(exc)[:120])

    data["counts"] = counts
    return data


# --- MATCH: does that dataset correspond to the loaded config? --------------
def check_match(cfg: dict, data: dict) -> None:
    tenancy = cfg["tenancy"]
    if tenancy["mode"] == "single":
        code = tenancy.get("providerCode")
        hit = [p for p in data["providers"] if p["public_code"] == code]
        record(MATCH, bool(hit), "tenancy.providerCode resolves to a seeded provider",
               f"{code!r} -> {hit[0]['name'] if hit else 'NO SUCH PROVIDER'}"
               + ("" if hit else "; single mode shows 'No business yet'"))
    else:
        record(MATCH, True, "tenancy is multi — no sole provider to resolve", "")

    # The seven scalars the engine resolves per service. A service COLUMN wins
    # over the config default, so a mismatch here is exactly "the pivot changed
    # the default and the seeded rows still carry the old value".
    # `pricing.tiers` is a catalogue of prices, not a single default: a seed that
    # gives each tier its own service is CORRECT even though the rows then differ
    # from `pricing.rate`. Accept the base rate or any declared tier amount.
    tier_amounts = {int(t["amountMinorUnits"]) for t in cfg["pricing"].get("tiers") or []}

    for name, (col, path, _default) in _SERVICE_RULE_MAP.items():
        if path is None:  # bookingModel has no config path; handled below
            continue
        node = cfg
        for part in path.split("."):
            node = node.get(part, {}) if isinstance(node, dict) else None
        want = node
        allowed = {want} | (tier_amounts if col == "price_minor_units" else set())
        seen = Counter(s.get(col) for s in data["services"])
        agree = all(v in allowed for v in seen)
        record(MATCH, agree, f"services.{col} == {path}",
               f"config says {want!r}"
               + (f" (or a tier: {sorted(tier_amounts)})" if col == "price_minor_units" and tier_amounts else "")
               + "; rows have " + ", ".join(f"{v!r}x{n}" for v, n in seen.most_common()))

    # booking.unitKind vs the seeded booking_model, through the seed's own map.
    models = {s.get("booking_model") for s in data["services"]}
    verticals = {BOOKING_MODEL_TO_VERTICAL.get(m, "?") for m in models}
    unit_kind = cfg["booking"]["unitKind"]
    want_model = UNIT_KIND_TO_MODEL.get(unit_kind)
    ok = len(models) == 1 and (want_model is None or models == {want_model})
    record(MATCH, ok, f"booking.unitKind {unit_kind!r} suits the seeded booking model",
           f"rows are {sorted(models)} (vertical {sorted(verticals)}); "
           + (f"{unit_kind!r} wants {want_model!r}" if want_model
              else f"no expectation recorded for {unit_kind!r}"))

    # Slot capacity vs the party rules.
    party = cfg["booking"]["party"]
    # `_inject_edge_cases` blocks a day by setting capacity 0 on purpose; those
    # are demo fixtures, not slots the party rules are meant to fit.
    caps = Counter(s.get("capacity") for s in data["slots"] if s.get("capacity"))
    blocked = sum(1 for s in data["slots"] if not s.get("capacity"))
    want_max, want_min = party.get("max"), party.get("min") or 1
    if want_max is not None:
        over = [c for c in caps if isinstance(c, int) and c > want_max]
        record(MATCH, not over, "slot capacity within booking.party.max",
               f"party.max={want_max}; capacities {dict(caps)}")
    # The one that actually catches a stale seed: a group/buyout config, or a
    # party.min above 1, cannot be served by capacity-1 slots — every booking
    # would be refused for want of room.
    needs_room = party["mode"] != "individual" or party.get("matchResourceCapacity") or want_min > 1
    too_small = [c for c in caps if isinstance(c, int) and c < want_min] or (
        needs_room and list(caps) == [1])
    record(MATCH, not too_small,
           f"slot capacity can seat booking.party (mode={party['mode']}, min={want_min})",
           f"capacities {dict(caps)} ({blocked} blocked slots ignored)"
           + ("; capacity-1 slots cannot hold a group booking" if too_small else ""))

    # Slot grid vs the business timezone. Checking only that local starts are
    # whole hours is not enough — a grid laid in Europe/Warsaw and read as UTC
    # is still on the hour, just at the wrong hour. The seed lays its grid in the
    # vertical's `baseTz`, so compare that directly, and show the local times so
    # a wrong zone is visible as an implausible trading day.
    config_tz = cfg["location"]["timezone"]
    stamped = [(p.get("metadata") or {}).get("seeded") for p in data["providers"]]
    stamped_tz = {s["tz"] for s in stamped if isinstance(s, dict) and s.get("tz")}
    # Fall back to the canned vertical's zone for data seeded before provenance
    # was recorded (or by `POST /demo/vertical`).
    seed_tz = stamped_tz.pop() if len(stamped_tz) == 1 else VERTICALS[active_vertical()]["baseTz"]
    tz = ZoneInfo(config_tz)
    starts = Counter()
    for s in data["slots"][:2000]:
        try:
            dt = datetime.fromisoformat(s["starts_at"].replace("Z", "+00:00")).astimezone(tz)
            starts[f"{dt.hour:02d}:{dt.minute:02d}"] += 1
        except Exception:
            continue
    record(MATCH, config_tz == seed_tz,
           "location.timezone == the zone the slot grid was laid in",
           f"config says {config_tz}, the seed laid its grid in {seed_tz}; "
           f"slot starts read in {config_tz}: {sorted(starts)[:6]}"
           + (" ..." if len(starts) > 6 else ""))

    # Declared metaFields vs what the rows actually carry.
    for entity, table_key in (("services", "services"), ("resources", "resources"), ("slots", "slots")):
        declared = {f["key"] for f in cfg["metaFields"].get(entity, [])}
        if not declared:
            continue
        present = set()
        for r in data.get(table_key, []):
            present |= set((r.get("metadata") or {}).keys())
        missing = declared - present
        record(MATCH, not missing, f"metaFields.{entity} keys present in the rows",
               f"declared {sorted(declared)}; missing from every row: {sorted(missing)}")

    # A disabled capability that still has rows behind it.
    db = get_supabase()
    for cap, table in (("reviews", "reviews"), ("follows", "follows")):
        if cfg["capabilities"].get(cap):
            continue
        try:
            n = db.table(table).select("*", count="exact").limit(1).execute().count
        except Exception:
            continue
        record(MATCH, not n, f"capabilities.{cap} is off, so {table} should be empty", f"{n} rows")


def main() -> int:
    cfg = get_config()
    db = get_supabase()
    print(f"config : {cfg['domain']}  ({cfg['copy']['landingTitle']})")
    print(f"tenancy: {cfg['tenancy']['mode']}"
          + (f" / {cfg['tenancy']['providerCode']}" if cfg["tenancy"]["mode"] == "single" else ""))
    print()

    data = check_reset(db)
    check_match(cfg, data)

    for kind in (RESET, MATCH):
        group = [r for r in results if r[0] == kind]
        failed = [r for r in group if r[1] == "FAIL"]
        head = "did the wipe leave a clean dataset?" if kind == RESET \
            else "does that dataset match the config now loaded?"
        print(f"{kind}  — {head}")
        for _k, status, title, detail in group:
            if status == "FAIL" or VERBOSE:
                mark = "  ok  " if status == "ok" else "  FAIL"
                print(f"{mark} {title}")
                if detail:
                    print(f"         {detail}")
        print(f"       {len(group) - len(failed)}/{len(group)} ok\n")

    reset_failed = [r for r in results if r[0] == RESET and r[1] == "FAIL"]
    match_failed = [r for r in results if r[0] == MATCH and r[1] == "FAIL"]

    if match_failed and not reset_failed:
        print("The wipe is clean; the data just does not describe this config.")
        print("`make reseed` rebuilds from domain.config.json (seed_config.py), so this")
        print("usually means the data predates the current config — reseed and re-check.")
        print("Data loaded by `POST /demo/vertical` comes from seed_data.VERTICALS")
        print("instead and will not match any pivot.")
    if reset_failed:
        print("RESET failures are real bugs — the rebuild left inconsistent data.")

    return 1 if reset_failed or (STRICT and match_failed) else 0


if __name__ == "__main__":
    sys.exit(main())
