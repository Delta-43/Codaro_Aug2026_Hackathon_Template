#!/usr/bin/env bash
# Orchestrates `make benchmark-k6`: runs ONLY the k6 backend API load test,
# into its own results/<run-name>/ folder — separate from a combined
# `make benchmark` run, so it never mixes with or overwrites Playwright
# results. The resulting report (generate_report.py) shows just the backend
# section, since no playwright-results.json exists in this folder. Run
# `make benchmark` instead for a combined backend+frontend run/report.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

new_run_dir
start_stack
ensure_bench_user

echo "==> Running k6 API load test..."
docker compose run --rm k6

echo "==> Re-provisioning the benchmark customer account (k6's booking_write"
echo "    scenario erases it via DELETE /me at teardown, see k6/api-load-test.js)..."
ensure_bench_user

echo "==> Generating report..."
python3 report/generate_report.py "results/$RUN_NAME"

echo
echo "Done: $(pwd)/results/$RUN_NAME/k6.html"
