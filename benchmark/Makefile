# Self-contained: every target here works from *inside* this folder and
# never touches the root Makefile/docker-compose.yml, so this directory can
# be worked on without merge conflicts against the rest of the repo.
#
# `--project-directory ..` is the key: it points Compose at the parent repo's
# .env/relative paths while keeping the SAME Compose project ("codarohackathon",
# derived from the repo root's dirname) that `make start` (root Makefile) uses
# — so `start` here manages the exact same frontend/backend containers, never
# a second parallel stack.
APP_COMPOSE = docker compose -f ../docker-compose.yml --project-directory ..

.PHONY: help start benchmark benchmark-k6 benchmark-playwright

help:
	@echo "make start                 - build (if needed) and start frontend :3000 + backend :8000"
	@echo "                             (same containers the root Makefile's 'make start' manages)"
	@echo "make benchmark             - run BOTH the k6 load test + Playwright matrix into one"
	@echo "                             results/<commit-date>-<branch>-<sha>/combined.html."
	@echo "make benchmark-k6          - run ONLY the k6 backend load test, writing its own"
	@echo "                             results/<...>/k6.html."
	@echo "make benchmark-playwright  - run ONLY the Playwright frontend matrix, writing its own"
	@echo "                             results/<...>/playwright.html."
	@echo "                             All three run in the foreground — Ctrl+C stops them. See CLAUDE.md."

start:
	$(APP_COMPOSE) up -d --build

benchmark: start
	./run.sh

benchmark-k6: start
	./run-k6.sh

benchmark-playwright: start
	./run-playwright.sh
