# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""One pivot's live probe — read the API, book-quote a real selection, capture.

Split out of `check_pivot_live.sh` so the assertions are readable and the shell
stays a loop. Writes one JSON line per pivot to `$OUT` for the frontend-contract
pass to consume.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

B = "http://localhost:8000"
N, RETRY, OUT = os.environ["N"], os.environ.get("RETRY", ""), os.environ["OUT"]


def get(path: str):
    with urllib.request.urlopen(B + path, timeout=60) as r:
        return json.load(r)


def token() -> str:
    raw = open("/tmp/tok2.txt").read().strip()
    return json.loads(raw)["DEMO"] if raw.startswith("{") else raw


def parse(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


problems: list[str] = []
try:
    cfg, provs, svcs = get("/config"), get("/providers"), get("/services")
except Exception as exc:  # noqa: BLE001 - any failure here is the finding
    print(f"  #{N:>3} FAIL  (API unreadable: {exc})")
    sys.exit(0)

single = (cfg.get("tenancy") or {}).get("mode") == "single"
if not provs:
    problems.append("no providers seeded")
elif single and cfg["tenancy"].get("providerCode") not in {p["publicCode"] for p in provs}:
    problems.append("tenancy.providerCode resolves to no seeded provider")
if not svcs:
    problems.append("no services seeded")

quote = None
svc = svcs[0] if svcs else None
if svc:
    # The frontend's Service type requires every one of these; a missing key is
    # a runtime crash in the client, not a cosmetic gap.
    for key in ("pricingModel", "rateUnit", "paymentFlow", "billingCycle",
                "prerequisites", "recurrence", "waitlist", "capabilities"):
        if key not in svc:
            problems.append(f"service payload missing {key}")

    slots = get(f"/slots?service_id={svc['id']}")
    # `capacity` is the raw column; a slot can have capacity and still be full.
    # Availability comes from the occupancy view, same as the engine's.
    occ = {o["slot_id"]: o for o in get(f"/slots/occupancy?service_id={svc['id']}")}
    now = datetime.now(timezone.utc)
    by_resource: dict[str, list] = {}
    for s in slots:
        if parse(s["starts_at"]) > now and occ.get(s["id"], {}).get("available_count", 0) > 0:
            by_resource.setdefault(s["resource_id"], []).append(s)

    if not by_resource:
        problems.append("no bookable future slots")
    else:
        rid, rows = max(by_resource.items(), key=lambda kv: len(kv[1]))
        rows.sort(key=lambda r: r["starts_at"])
        need = max(1, svc["minSlotsPerBooking"])
        span = [rows[0]]
        for r in rows[1:]:
            if len(span) >= need:
                break
            span = span + [r] if r["starts_at"] == span[-1]["ends_at"] else [r]
        if len(span) < need:
            problems.append(f"no contiguous run of {need} slots")
        else:
            body = json.dumps({"serviceId": svc["id"], "resourceId": rid,
                               "slotIds": [x["id"] for x in span], "partySize": 1}).encode()
            req = urllib.request.Request(
                B + "/bookings/quote", data=body,
                headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    quote = json.load(r)
            except urllib.error.HTTPError as exc:
                problems.append("quote rejected: " + exc.read().decode()[:90])

with open(OUT, "a") as fh:
    fh.write(json.dumps({"n": N, "domain": cfg["domain"], "config": cfg,
                         "service": svc, "quote": quote,
                         "providerCount": len(provs), "problems": problems}) + "\n")

money = f"{quote['amountMinorUnits']}{quote['currency']}/{quote['paymentFlow']}" if quote else "-"
tag = "ok  " if not problems else "FAIL"
print(f"  #{N:>3} {tag} {cfg['domain'][:30]:32s} slot={cfg['timing']['slotDurationMinutes']:>5}m "
      f"{'single' if single else 'multi ':6s} quote={money:20s}{RETRY}")
for p in problems:
    print(f"         - {p}")
