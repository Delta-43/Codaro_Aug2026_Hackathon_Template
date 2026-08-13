"""Loads and caches the domain pivot file (domain.config.json)."""
import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "domain.config.json"


@lru_cache
def get_config() -> dict:
    path = Path(os.environ.get("DOMAIN_CONFIG_PATH", DEFAULT_CONFIG_PATH))
    with path.open() as f:
        return json.load(f)


def clear_config_cache() -> None:
    get_config.cache_clear()
