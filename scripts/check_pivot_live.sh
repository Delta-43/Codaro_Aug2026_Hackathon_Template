#!/usr/bin/env bash
#
# Live end-to-end smoke across pivots.
#
# The third leg of the pivot verification story:
#   check_pivot_states.py    backend, offline  — all 100, load -> serve
#   check_pivot_frontend.mts frontend, offline — all 100, parse -> vocabulary
#   this                     BOTH, live        — seed -> book, against real data
#
# Offline checks prove shape; only this proves a pivot actually seeds a
# bookable catalogue and prices a real selection through the engine. It also
# CAPTURES each pivot's live payloads to `capture.jsonl`, so
# `check_pivot_live_frontend.mts` can then validate the client contract against
# data the backend really produced rather than against fixtures.
#
# *** DESTRUCTIVE ***  Each pivot swaps `domain.config.json` and runs
# `make reseed`, which WIPES the demo dataset. It leaves the last pivot loaded —
# restore with `git checkout domain.config.json && make reload && make reseed`.
# Never point it at a database you care about.
#
#   scripts/check_pivot_live.sh 3 7 11 25     # by pivot number
#   scripts/check_pivot_live.sh all           # every pivot (slow: ~1 min each)
#   make checklive ARGS="3 7 11 25"
#
# Requires a token at /tmp/tok2.txt (a raw JWT, or {"DEMO": "..."}).
set -u
cd "$(dirname "$0")/.."
OUT="${CAPTURE:-/tmp/pivot-capture.jsonl}"

ARGS="$*"
if [ "$ARGS" = "all" ]; then
  ARGS=$(ls pivots/[0-9]*.json | sed 's|.*/||; s|-.*||' | sed 's|^0*||')
  : > "$OUT"   # fresh capture for a full run
fi

for N in $ARGS; do
  python3 scripts/use_pivot.py "$N" >/dev/null 2>&1 || { echo "  #$N  use_pivot failed"; continue; }
  timeout 180 make reload >/dev/null 2>&1
  # Reseed is flaky against hosted Supabase (a PostgREST schema-cache race on
  # the wipe); one retry clears it every time it has been seen.
  RETRY=""
  if ! timeout 420 make reseed 2>&1 | grep -q "Seeded vertical"; then
    RETRY=" (retried)"
    timeout 420 make reseed >/dev/null 2>&1
  fi
  # `make reload` restarts the backend; probing before it is listening yields
  # a connection reset that looks like a pivot failure but is the harness
  # racing the container.
  for _ in $(seq 1 30); do curl -s -m 2 localhost:8000/health >/dev/null && break; sleep 1; done
  N="$N" RETRY="$RETRY" OUT="$OUT" python3 scripts/_live_probe.py
done
