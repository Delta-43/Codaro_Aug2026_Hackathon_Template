.PHONY: help start stop logs reload reset reseed checkseed checkstates checkfront checklive

help:
	@echo "make start   - build (if needed) and start frontend :3000 + backend :8000"
	@echo "make stop    - stop containers"
	@echo "make logs    - tail logs from both containers"
	@echo "make reload  - restart backend only (drops the domain.config.json cache)"
	@echo "make reset   - stop and remove local node_modules/.next volumes, then start fresh"
	@echo "make reseed  - wipe + rebuild demo data from the current domain.config.json"
	@echo "make checkseed - report where the seeded data and domain.config.json disagree"
	@echo "make checkstates - run every pivots/*.json through load -> spec -> rules -> serialize"
	@echo "make checkfront  - run every pivots/*.json through the frontend's own parsers"
	@echo "make checklive   - DESTRUCTIVE: seed+book a sample of pivots for real (ARGS=\"3 7 11\")"

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
		echo "A seed is in progress — restarting now would kill it and leave partial data."; \
		echo "Wait for it to finish, or override with: make reload RELOAD_FORCE=1"; \
		exit 1; \
	fi
	docker compose restart backend

reset:
	docker compose down -v
	docker compose up -d --build

reseed:
	docker compose exec backend python reseed.py

checkseed:
	docker compose exec backend python /workspace/scripts/check_seed.py $(ARGS)

checkstates:
	docker compose exec backend python /workspace/scripts/check_pivot_states.py $(ARGS)

checkfront:
	cd frontend && npx tsx ../scripts/check_pivot_frontend.mts $(ARGS)

# DESTRUCTIVE — wipes and reseeds the demo dataset once per pivot.
checklive:
	./scripts/check_pivot_live.sh $(ARGS)
