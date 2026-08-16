FROM python:3.12-slim

# IMPORTANT: this image is built with the REPO ROOT as the build context
# (docker build -f backend/Dockerfile .), because the backend reads two files
# that live at the repo root and are resolved via parents[2] of backend/app/*:
#   - domain.config.json      (app/config.py)
#   - supabase/schema.sql     (app/schema_setup.py)
# The repo layout (<root>/backend/app/...) is preserved so those paths resolve.
WORKDIR /workspace

# Dependencies first for layer caching.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend code + the repo-root files it reads at runtime.
COPY backend/ backend/
COPY supabase/ supabase/
COPY domain.config.json domain.config.json

WORKDIR /workspace/backend

# Production default: bind the platform-provided $PORT (Railway injects it),
# no --reload. WEB_CONCURRENCY defaults to 1 because schema-setup + seeding run
# in the app lifespan, i.e. once per worker — see DEPLOY.md before raising it.
# Local dev keeps hot-reload via the `command:` override in docker-compose.yml.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
