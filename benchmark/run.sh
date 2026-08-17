#!/usr/bin/env bash
# Orchestrates `make benchmark`: runs BOTH the k6 API load test and the
# Playwright device/network matrix into ONE shared results/<run-name>/
# folder, so the combined report shows backend + frontend for the same run.
# Run `make benchmark-k6` / `make benchmark-playwright` (run-k6.sh /
# run-playwright.sh) instead if you only want to refresh one half — each
# writes into its own results folder with a backend-only or frontend-only
# report. Everything here is relative to this folder, not the repo root —
# see the `--project-directory` note atop ./Makefile.
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

echo "==> Building the Playwright benchmark image (first run only)..."
docker compose build playwright-bench

echo "==> Running Playwright device/network matrix..."
docker compose run --rm playwright-bench

echo "==> Generating report..."
python3 report/generate_report.py "results/$RUN_NAME"

echo
echo "Done: $(pwd)/results/$RUN_NAME/combined.html"
