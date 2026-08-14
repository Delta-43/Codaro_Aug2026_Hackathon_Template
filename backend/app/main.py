import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import clear_config_cache, get_config
from app.routers import bookings, resources, slots
from app.schema_setup import create_tables_if_configured
from seed import seed_if_empty

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Referenced through their module-level names so tests can monkeypatch
    # `main.create_tables_if_configured` / `main.seed_if_empty` to no-ops.
    create_tables_if_configured()
    seed_if_empty()
    yield


app = FastAPI(title="Codaro Booking Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict once frontend origin is fixed
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resources.router)
app.include_router(slots.router)
app.include_router(bookings.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return get_config()


@app.post("/config/reload")
def reload_config():
    """Instant pivot: drop the cached config and return the fresh file."""
    clear_config_cache()
    return get_config()
