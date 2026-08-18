"""Loads, normalizes, validates and caches the domain pivot file.

v1 loaded `domain.config.json` with a bare `json.load` and handed the raw dict
to every caller. That made a typo in the pivot file a 500 on whichever request
first read the bad key — the worst possible time to find out, given this file is
meant to be hand-edited live during a pivot.

Now the load path is: read -> `config_schema.normalize()` (defaults + v1
aliasing) -> `config_schema.validate()` -> cache. A bad file raises `ConfigError`
with every problem listed at once, so the edit fails, not the next booking.

`get_config()` returns the NORMALIZED tree, so every reader can assume every key
exists. `get_raw_config()` returns the file as written, for tooling that needs to
show the operator what they actually typed.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from app.config_schema import ConfigError, normalize, validate

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "domain.config.json"


def _config_path() -> Path:
    return Path(os.environ.get("DOMAIN_CONFIG_PATH", DEFAULT_CONFIG_PATH))


def load_config(path: Path | None = None) -> dict:
    """Read + normalize + validate. Raises ConfigError on anything that would
    break the engine. Not cached — call `get_config()` for the hot path."""
    path = path or _config_path()
    try:
        with path.open() as f:
            raw = json.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"{path} does not exist — the pivot file must be present.") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a JSON object at the top level.")

    config = normalize(raw)
    errors = validate(config)
    if errors:
        listed = "\n  - ".join(errors)
        raise ConfigError(
            f"{path} is not a usable domain config:\n  - {listed}\n"
            "This is the file a pivot edits — fix the keys above."
        )
    return config


@lru_cache
def get_config() -> dict:
    """The normalized, validated pivot config. Every v2 key is guaranteed present."""
    return load_config()


@lru_cache
def get_raw_config() -> dict:
    """The pivot file exactly as written, with no defaults applied."""
    with _config_path().open() as f:
        return json.load(f)


def clear_config_cache() -> None:
    get_config.cache_clear()
    get_raw_config.cache_clear()
