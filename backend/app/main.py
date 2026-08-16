import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import clear_config_cache, get_config
from app.routers import (
    availability,
    bookings,
    demo,
    me,
    providers,
    resources,
    services,
    slots,
)
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

# CORS origins come from the environment so prod can lock the API to the
# deployed frontend while local dev stays open. `CORS_ORIGINS` is a
# comma-separated list of origins (e.g. "https://app.vercel.app"); the "*"
# default keeps localhost working out of the box. Auth rides on the
# Authorization header (not cookies), so credentialed CORS isn't needed.
_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
_allow_origins = (
    ["*"]
    if _cors_origins == "*"
    else [o.strip() for o in _cors_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(providers.router)
app.include_router(services.router)
app.include_router(resources.router)
app.include_router(slots.router)
app.include_router(availability.router)
app.include_router(bookings.router)
app.include_router(me.router)
app.include_router(demo.router)


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
