#!/usr/bin/env python3
"""Run every `pivots/*.json` through the real load -> seed-spec -> serve path.

`check_pivots.py` asks whether a pivot is *expressible* (validator + pricing).
This asks the next question: does the engine still produce a coherent booking
product once that config is loaded? It exercises the same functions the app
does -- `app.config.get_config`, `seed_config.spec_from_config`,
`rules.effective_service_*`, `serialize.serialize_service` -- once per pivot.

It also guards the failure that motivated it: every pivot resolved to a flat
30-minute slot regardless of `booking.granularity`, so a hotel declaring
`night` and a storage unit declaring `month` both seeded half-hour slots. A
per-pivot check could not see it -- each config was internally consistent. Only
looking ACROSS pivots showed one distinct duration for a hundred businesses,
which is why the invariants below are partly about variety.

    python3 scripts/check_pivot_states.py        # from the repo root
    make checkstates                             # or via the Makefile
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.config as appconfig  # noqa: E402
from app.config_schema import GRANULARITY_SLOT_MINUTES  # noqa: E402
from seed_config import spec_from_config  # noqa: E402

PIVOTS = REPO_ROOT / "pivots"


def services_of(spec: dict) -> list[dict]:
    """Every service the seeder would build from this spec."""
    out = list(spec.get("demoServices") or [])
    if spec.get("simpleService"):
        out.append(spec["simpleService"])
    return out


def service_row(spec: dict, svc: dict) -> dict:
    """The DB row `seed.add_service` would insert, so the resolver and the
    serializer see exactly the shape they see in production."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "provider_id": "00000000-0000-0000-0000-000000000002",
        "name": svc["name"],
        "description": svc["description"],
        "booking_model": spec["bookingModel"],
        "slot_duration_minutes": svc["slotDurationMinutes"],
        "min_slots_per_booking": svc["minSlotsPerBooking"],
        "max_slots_per_booking": svc["maxSlotsPerBooking"],
        "price_minor_units": svc["priceMinorUnits"],
        "currency": spec["currency"],
        "cancellation_cutoff_hours": svc["cancellationCutoffHours"],
        "metadata": {**(svc.get("metaFields", {}).get("service") or {}), "auto_approve": True},
    }


def check_one(path: Path) -> tuple[list[str], dict]:
    """Returns (failures, facts). `facts` feeds the cross-pivot invariants."""
    fails: list[str] = []
    os.environ["DOMAIN_CONFIG_PATH"] = str(path)
    appconfig.clear_config_cache()
    cfg = appconfig.get_config()          # normalize + validate, as the app does
    spec = spec_from_config(cfg)

    # Imported here: they read the config through get_config() at call time, so
    # the swap above is what they see.
    from app.rules import (capability, effective_auto_approve,  # noqa: PLC0415
                           effective_service_config, effective_service_rules)
    from app.serialize import serialize_service  # noqa: PLC0415

    granularity = cfg["booking"]["granularity"]
    facts = {"domain": cfg["domain"], "granularity": granularity, "durations": set()}

    svcs = services_of(spec)
    if not svcs:
        return [f"{path.name}: spec produced no services"], facts

    # Single-tenant: the configured code must name a provider the seed creates,
    # or the deployment resolves no business and every screen renders empty.
    tenancy = cfg.get("tenancy") or {}
    if tenancy.get("mode") == "single" and tenancy.get("providerCode"):
        codes = {p["publicCode"] for p in spec["providers"]}
        if tenancy["providerCode"] not in codes:
            fails.append(
                f"{path.name}: tenancy.providerCode {tenancy['providerCode']!r} "
                f"matches no seeded provider {sorted(codes)}"
            )

    for svc in svcs:
        row = service_row(spec, svc)
        effective_service_rules(row)
        effective_service_config(row)
        effective_auto_approve(row)
        capability("reviews", row)
        out = serialize_service(row, resource_ids=["00000000-0000-0000-0000-000000000003"])
        facts["durations"].add(out["slotDurationMinutes"])

        name = f"{path.name}:{svc['name']}"
        if out["slotDurationMinutes"] <= 0:
            fails.append(f"{name}: slotDurationMinutes {out['slotDurationMinutes']}")
        if out["minSlotsPerBooking"] < 1:
            fails.append(f"{name}: minSlotsPerBooking {out['minSlotsPerBooking']}")
        if out["maxSlotsPerBooking"] < out["minSlotsPerBooking"]:
            fails.append(
                f"{name}: maxSlotsPerBooking {out['maxSlotsPerBooking']} "
                f"< minSlotsPerBooking {out['minSlotsPerBooking']}"
            )
        if not out["currency"]:
            fails.append(f"{name}: empty currency")
        if out["priceMinorUnits"] < 0:
            fails.append(f"{name}: negative price {out['priceMinorUnits']}")
        if out["cancellationCutoffHours"] < 0:
            fails.append(f"{name}: negative cutoff {out['cancellationCutoffHours']}")
        if not isinstance(out["capabilities"], dict) or not out["capabilities"]:
            fails.append(f"{name}: no resolved capabilities")
        # The unit the config SAYS it sells has to be the unit the calendar
        # lays down, or the pivot renders a business it does not describe.
        expected = GRANULARITY_SLOT_MINUTES.get(granularity)
        if expected is not None and out["slotDurationMinutes"] != expected:
            fails.append(
                f"{name}: granularity {granularity!r} implies {expected} min, "
                f"got {out['slotDurationMinutes']}"
            )
    return fails, facts


def main() -> int:
    paths = sorted(PIVOTS.glob("[0-9]*.json"))
    if not paths:
        print("no pivots found — run: python3 scripts/generate_pivots.py")
        return 1

    all_fails: list[str] = []
    by_granularity: dict[str, set[int]] = {}
    durations: Counter[int] = Counter()
    for path in paths:
        try:
            fails, facts = check_one(path)
        except Exception as exc:  # a crash IS the failure — report, keep going
            all_fails.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        all_fails += fails
        by_granularity.setdefault(facts["granularity"], set()).update(facts["durations"])
        durations.update(facts["durations"])

    print(f"pivots checked                  : {len(paths)}")
    print(f"load -> spec -> rules -> serialize : {len(paths) - len({f.split(':')[0] for f in all_fails})} ok")
    print("\nslot length per granularity:")
    for gran in sorted(by_granularity):
        got = sorted(by_granularity[gran])
        want = GRANULARITY_SLOT_MINUTES.get(gran)
        flag = "" if want is None or got == [want] else f"   <-- expected [{want}]"
        print(f"  {gran:8s} -> {got}{flag}")

    # The invariant that would have caught the original bug: a hundred different
    # businesses cannot all run the same calendar.
    if len(durations) < 2:
        all_fails.append(
            f"every pivot resolved to the same slot length {sorted(durations)} — "
            "booking.granularity is not reaching timing.slotDurationMinutes"
        )

    if all_fails:
        print(f"\nFAILURES ({len(all_fails)}):")
        for f in all_fails[:40]:
            print(f"  {f}")
        if len(all_fails) > 40:
            print(f"  ... and {len(all_fails) - 40} more")
        return 1
    print("\nall pivot states OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
