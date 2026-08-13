.PHONY: help start stop logs reload reset reseed

help:
	@echo "make start   - build (if needed) and start frontend :3000 + backend :8000"
	@echo "make stop    - stop containers"
	@echo "make logs    - tail logs from both containers"
	@echo "make reload  - restart backend only (drops the domain.config.json cache)"
	@echo "make reset   - stop and remove local node_modules/.next volumes, then start fresh"
	@echo "make reseed  - wipe + reseed demo data to match the current domain.config.json"

start:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

reload:
	docker compose restart backend

reset:
	docker compose down -v
	docker compose up -d --build

reseed:
	docker compose exec backend python reseed.py
