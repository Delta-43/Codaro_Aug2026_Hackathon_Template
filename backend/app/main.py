import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_config
from app.routers import bookings, resources, slots
from app.schema_setup import create_tables_if_configured
from seed import seed_if_empty

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Codaro Booking Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict once frontend origin is fixed
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resources.router)
app.include_router(slots.router)
app.include_router(bookings.router)


@app.on_event("startup")
def on_startup() -> None:
    create_tables_if_configured()
    seed_if_empty()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return get_config()
