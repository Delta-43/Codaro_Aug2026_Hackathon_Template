# Shared setup, sourced (not executed) by run.sh / run-k6.sh / run-playwright.sh:
# brings up the app stack, waits for it to be healthy, computes this run's
# results/<run-name>/ folder, and (re)provisions the bench customer account.
# Kept in one place so the three entry scripts can't drift on this logic.

APP_COMPOSE=(docker compose -f ../docker-compose.yml --project-directory ..)

wait_for() {
  local url="$1" name="$2" tries=30
  echo -n "==> Waiting for $name ($url)..."
  until curl -sf "$url" >/dev/null 2>&1; do
    tries=$((tries - 1))
    if [ "$tries" -le 0 ]; then
      echo " timed out."
      echo "    $name never came up at $url — check \`make logs\`."
      exit 1
    fi
    echo -n "."
    sleep 2
  done
  echo " up."
}

start_stack() {
  echo "==> Making sure the app stack is up..."
  "${APP_COMPOSE[@]}" up -d
  wait_for "http://localhost:8000/config" "backend"
  wait_for "http://localhost:3000/login" "frontend"
}

# Idempotent, and safe to call multiple times in one run (k6's booking_write
# scenario erases this account via DELETE /me at teardown, see
# k6/api-load-test.js) — call it again before anything that needs to log in.
ensure_bench_user() {
  echo "==> Ensuring the benchmark customer account exists..."
  "${APP_COMPOSE[@]}" exec backend python /workspace/benchmark/create_bench_users.py
}

# Computes and creates this run's results/<run-name>/ folder, exporting
# RUN_NAME so docker-compose.yml's volume mounts (./results/${RUN_NAME}) pick
# it up. Each entry script calls this once, at the top — a k6-only or
# Playwright-only run gets its own folder/seq number, same as a combined run.
new_run_dir() {
  mkdir -p results
  RUN_NAME=$(python3 report/run_context.py results)
  export RUN_NAME
  # The k6 and Playwright images run as non-root, host-UID-agnostic users, so
  # make this disposable, gitignored output dir writable by anyone.
  chmod 777 "results/$RUN_NAME"
  echo "==> Run folder: results/$RUN_NAME"
}
