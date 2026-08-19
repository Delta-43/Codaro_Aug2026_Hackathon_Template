#!/usr/bin/env bash
#
# Live end-to-end smoke across a spread of pivots.
#
# The third leg of the pivot verification story:
#   check_pivot_states.py    backend, offline  — all 100, load -> serve
#   check_pivot_frontend.mts frontend, offline — all 100, parse -> vocabulary
#   this                     BOTH, live        — a sample, seed -> quote
#
# Offline checks prove shape; only this proves a pivot actually seeds a
# bookable catalogue and prices a real selection through the engine.
#
# *** DESTRUCTIVE ***  Each pivot swaps `domain.config.json` and runs
# `make reseed`, which WIPES the demo dataset. It leaves the last pivot loaded —
# restore with `git checkout domain.config.json && make reload && make reseed`.
# Never point it at a database you care about.
#
#   scripts/check_pivot_live.sh 3 7 11 25     # by pivot number
#   make checklive ARGS="3 7 11 25"
#
# Requires a token at /tmp/tok2.txt (a raw JWT, or {"DEMO": "..."}).
set -u
cd /home/kaveo/CodaroHackathon
PIVOTS="$*"
for N in $PIVOTS; do
  python3 scripts/use_pivot.py "$N" >/dev/null 2>&1
  timeout 120 make reload >/dev/null 2>&1
  # Reseed is flaky against hosted Supabase (PostgREST cache race); retry once.
  OUT=$(timeout 300 make reseed 2>&1 | grep -c "Seeded vertical")
  if [ "$OUT" = "0" ]; then OUT=$(timeout 300 make reseed 2>&1 | grep -c "Seeded vertical"); RETRY=" (retried)"; else RETRY=""; fi
  python3 - "$N" "$RETRY" <<'PY'
import json, sys, urllib.request, urllib.error
n, retry = sys.argv[1], sys.argv[2]
B = "http://localhost:8000"
def get(p):
    with urllib.request.urlopen(B + p, timeout=30) as r: return json.load(r)
tok = open('/tmp/tok2.txt').read()
tok = json.loads(tok)['DEMO'] if tok.strip().startswith('{') else tok.strip()
try:
    cfg = get("/config"); provs = get("/providers"); svcs = get("/services")
except Exception as e:
    print(f"  #{n:>3}  FAILED to read API: {e}"); sys.exit()
problems = []
single = (cfg.get("tenancy") or {}).get("mode") == "single"
if not provs: problems.append("no providers seeded")
if single and (cfg["tenancy"].get("providerCode") not in {p["publicCode"] for p in provs}):
    problems.append("providerCode resolves to nothing")
if not svcs: problems.append("no services seeded")
quoted = "-"
if svcs:
    s = svcs[0]
    for k in ("pricingModel","paymentFlow","recurrence","waitlist","prerequisites","rateUnit"):
        if k not in s: problems.append(f"service payload missing {k}")
    slots = get(f"/slots?service_id={s['id']}")
    # `capacity` is the raw column; a slot can have capacity and still be fully
    # booked. Availability comes from the occupancy view, same as the engine's.
    occ = {o["slot_id"]: o for o in get(f"/slots/occupancy?service_id={s['id']}")}
    from datetime import datetime, timezone
    P = lambda t: datetime.fromisoformat(t.replace("Z","+00:00"))
    now = datetime.now(timezone.utc)
    by = {}
    for x in slots:
        if P(x["starts_at"]) > now and occ.get(x["id"], {}).get("available_count", 0) > 0:
            by.setdefault(x["resource_id"], []).append(x)
    if not by: problems.append("no bookable future slots")
    else:
        rid, rows = max(by.items(), key=lambda kv: len(kv[1]))
        rows.sort(key=lambda r: r["starts_at"])
        need = max(1, s["minSlotsPerBooking"])
        span = [rows[0]]
        for r in rows[1:]:
            if len(span) >= need: break
            if r["starts_at"] == span[-1]["ends_at"]: span.append(r)
            else: span = [r]
        if len(span) < need: problems.append(f"no contiguous run of {need}")
        else:
            body = json.dumps({"serviceId": s["id"], "resourceId": rid,
                               "slotIds": [x["id"] for x in span], "partySize": 1}).encode()
            rq = urllib.request.Request(B + "/bookings/quote", data=body,
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(rq, timeout=30) as r: q = json.load(r)
                quoted = f"{q['amountMinorUnits']}{q['currency']}/{q['paymentFlow']}"
            except urllib.error.HTTPError as e:
                problems.append("quote " + e.read().decode()[:70])
sd = cfg["timing"]["slotDurationMinutes"]
tag = "ok " if not problems else "FAIL"
print(f"  #{n:>3} {tag} {cfg['domain'][:30]:32s} slot={sd:>5}m {'single' if single else 'multi ':6s} quote={quoted:16s}{retry}")
for p in problems: print(f"         - {p}")
PY
done
