#!/usr/bin/env bash
# Orchestrates `make benchmark-playwright`: runs ONLY the Playwright
# device/network matrix, into its own results/<run-name>/ folder — separate
# from a combined `make benchmark` run, so it never mixes with or overwrites
# k6 results. The resulting report (generate_report.py) shows just the
# frontend section, since no k6-events.jsonl exists in this folder. Run
# `make benchmark` instead for a combined backend+frontend run/report.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

new_run_dir
start_stack
ensure_bench_user

echo "==> Building the Playwright benchmark image (first run only)..."
docker compose build playwright-bench

echo "==> Running Playwright device/network matrix..."
docker compose run --rm playwright-bench

echo "==> Generating report..."
python3 report/generate_report.py "results/$RUN_NAME"

echo
echo "Done: $(pwd)/results/$RUN_NAME/playwright.html"
