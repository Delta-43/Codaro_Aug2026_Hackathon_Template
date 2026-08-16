FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Production default: bind the platform-provided $PORT (Railway injects it),
# no --reload. WEB_CONCURRENCY defaults to 1 because schema-setup + seeding run
# in the app lifespan, i.e. once per worker — see DEPLOY.md before raising it.
# Local dev keeps hot-reload via the `command:` override in docker-compose.yml.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
