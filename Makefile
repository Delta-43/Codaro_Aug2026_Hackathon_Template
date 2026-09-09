.PHONY: help start stop logs reload reset reseed demoseed checkseed fetchmedia

help:
	@echo "make start   - build (if needed) and start frontend :3000 + backend :8000"
	@echo "make stop    - stop containers"
	@echo "make logs    - tail logs from both containers"
	@echo "make reload  - restart backend only (drops the domain.config.json cache)"
	@echo "make reset   - stop and remove local node_modules/.next volumes, then start fresh"
	@echo "make reseed  - wipe + rebuild demo data from the current domain.config.json"
	@echo "make checkseed - report where the seeded data and domain.config.json disagree"
	@echo "make demoseed   - DESTRUCTIVE: wipe + seed the hand-written demo vertical (VERTICAL=funeral)"
	@echo "make fetchmedia - download demo imagery into frontend/public/media (skips cached files)"

start:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

# Restarting the backend kills a `make reseed` running inside it, leaving a
# half-built dataset and no error. Refuse rather than corrupt; RELOAD_FORCE=1
# overrides for the case where the lock is stale.
reload:
	@if [ "$(RELOAD_FORCE)" != "1" ] && docker compose exec -T backend python /workspace/scripts/seed_in_progress.py; then \
		echo "A seed is in progress, restarting now would kill it and leave partial data."; \
		echo "Wait for it to finish, or override with: make reload RELOAD_FORCE=1"; \
		exit 1; \
	fi
	docker compose restart backend

reset:
	docker compose down -v
	docker compose up -d --build

reseed:
	docker compose exec backend python reseed.py

# DESTRUCTIVE, wipes and reseeds the hand-written demo dataset for one
# vertical (rich catalogue + real photography), rather than the generic rows
# `reseed` derives from domain.config.json. Override with VERTICAL=<id>.
VERTICAL ?= funeral
demoseed:
	docker compose exec backend python -c "import seed; seed.seed_vertical('$(VERTICAL)')"

checkseed:
	docker compose exec backend python /workspace/scripts/check_seed.py $(ARGS)




# Download the demo photography into frontend/public/media. Runs on the HOST
# (plain python3 + urllib, no deps) because the target directory is the
# frontend bind mount. Already-present files are skipped, and a failed fetch is
# reported but never fatal, seeding falls back to generated SVG gradients for
# anything missing.
fetchmedia:
	python3 backend/seed_media_fetch.py
