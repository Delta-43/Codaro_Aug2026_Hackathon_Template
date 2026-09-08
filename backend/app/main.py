# Arbor — a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import discovery
from app.auth import AuthUser, require_owner
from app.config import clear_config_cache, get_config, load_config
from app.config_schema import ConfigError
from app.db import get_supabase
from app.errors import VALIDATION_ERROR, api_error
from app.routers import (
    availability,
    bookings,
    me,
    messages,
    owner,
    providers,
    resources,
    services,
    slots,
    waitlist,
)
from app.schema_setup import create_tables_if_configured
from seed import active_vertical

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Referenced through its module-level name so tests can monkeypatch
    # `main.create_tables_if_configured` to a no-op. No demo seeding runs on
    # startup — the app serves only real Supabase data; seed manually if needed.
    create_tables_if_configured()
    yield


app = FastAPI(title="Arbor", lifespan=lifespan)

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
# After `slots`: both mount /slots, and the waitlist adds sub-paths only.
app.include_router(waitlist.router)
app.include_router(bookings.router)
app.include_router(me.router)
app.include_router(messages.router)
app.include_router(owner.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/vertical")
def vertical():
    """The currently-seeded vertical, inferred from the catalog. The frontend
    reads it at boot to pick the base vocabulary for whichever vertical the
    config seeded."""
    return {"verticalId": active_vertical()}


def _config_with_facets() -> dict:
    """The pivot config plus a resolved `search.facets` map (which filter/sort
    dimensions the search UI offers). Derivation from live catalog data decides
    what's *possible* (a free niche → no price, a remote niche → no distance), so
    any pivot's seed auto-configures the filter UI. `domain.config.json`'s
    `search.facets` is an optional override that can force a facet **off**
    (`"distance": false`) — you can't conjure a dimension the data lacks, so a
    declared `true` just defers to derivation. Best-effort: if the catalog read
    fails, fall back to all-on rather than break config delivery."""
    cfg = get_config()
    try:
        derived = discovery.search_facets(get_supabase())
    except Exception:
        derived = {"price": True, "distance": True, "rating": True}
    existing = cfg.get("discovery") if isinstance(cfg.get("discovery"), dict) else {}
    declared = existing.get("facets") if isinstance(existing.get("facets"), dict) else {}
    # A hand-edited config could set a facet to any value; coerce to a bool so a
    # typo can't 500 /config. Only an explicit `false` forces a facet off.
    resolved = {
        key: bool(value) and declared.get(key, True) is not False
        for key, value in derived.items()
    }
    # `discovery.facets` carries the v2 set (it also declares `availability` and
    # `unitKind`, which derivation has no opinion on); `search.facets` keeps the
    # three-key v1 shape so an older client never sees a facet it can't render.
    return {
        **cfg,
        "discovery": {**existing, "facets": {**declared, **resolved}},
        "search": {**(cfg.get("search") or {}), "facets": resolved},
    }


@app.get("/config")
def config():
    return _config_with_facets()


@app.post("/config/reload")
def reload_config(owner: AuthUser = Depends(require_owner)):
    """Instant pivot: drop the cached config and return the fresh file.

    Two changes from v1. It is **owner-gated** — this is a control-plane endpoint
    that re-reads a file off disk, and it was open to anyone. And the fresh file
    is parsed and validated *before* the good cache is dropped, so a typo made
    mid-pivot returns a 422 listing every problem instead of swapping a broken
    config into a running app.
    """
    try:
        load_config()
    except ConfigError as e:
        raise api_error(VALIDATION_ERROR, str(e), status=422)
    clear_config_cache()
    return _config_with_facets()
