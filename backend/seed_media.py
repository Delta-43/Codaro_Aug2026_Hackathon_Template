# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Real photography for the seed, as a thin, optional override layer.

`seed.py` builds every image itself: `avatar_uri`, `cover_uri` and `tile_uri`
render deterministic inline-SVG gradients from a hash of the row's name, so a
seed always produces *something* to look at. This module sits in front of those
generators and, for names it recognises, returns a root-relative URL to a real
photograph under `frontend/public/media/` instead.

**Every lookup here is allowed to return `None`, and `None` is not an error.**
It means "no photo for this name" and the caller falls back to the generated
gradient:

    md = seed_media.provider_avatar(p["name"]) or avatar_uri(p["name"], p["name"])

That fallback is the whole design. The files are downloaded on demand by
`seed_media_fetch.py` (`make fetchmedia`) from Wikimedia Commons, they are not
committed as a hard dependency of seeding, and a dead CDN, a skipped fetch or a
half-populated media directory must never break a reseed, it can only make the
demo less pretty. Nothing in this module touches the filesystem or the network,
so it cannot fail either.

Paths mirror the directory layout under `frontend/public/media/`:

    /media/avatars/<slug>.jpg        people (directors and families)
    /media/homes/<slug>.jpg          a business, square
    /media/homes/<slug>-cover.jpg    a business, wide banner
    /media/arrangements/<slug>.jpg   a service or a resource tile

Keys are the **seed display names** exactly as they appear in `seed_data.py` and
`seed_people.py`, so a rename there is a miss here (a gradient), never a crash.
"""
from __future__ import annotations

# --- people (seed_people.CAST display names) -------------------------------

PEOPLE: dict[str, str] = {
    # staff of the demo home
    "Henryk Walczak": "henryk-walczak",
    "Dorota Sadowska": "dorota-sadowska",
    "Krzysztof Malinowski": "krzysztof-malinowski",
    # the two demo logins
    "Mara Lindqvist": "mara-lindqvist",
    "Tomasz Wiśniewski": "tomasz-wisniewski",
    # families
    "Agnieszka Nowak": "agnieszka-nowak",
    "Elżbieta Kamińska": "elzbieta-kaminska",
    "Jan Dąbrowski": "jan-dabrowski",
    "Piotr Zieliński": "piotr-zielinski",
    "Katarzyna Lewandowska": "katarzyna-lewandowska",
    "Marek Kowalczyk": "marek-kowalczyk",
    "Beata Szymańska": "beata-szymanska",
    "Lukas Behrend": "lukas-behrend",
    "Zofia Adamska": "zofia-adamska",
    "Paweł Górski": "pawel-gorski",
    "Irena Wójcik": "irena-wojcik",
    "Michał Sikora": "michal-sikora",
    "Halina Baran": "halina-baran",
    "Robert Mazur": "robert-mazur",
    "Ewa Duda": "ewa-duda",
    "Andrzej Stępień": "andrzej-stepien",
    "Natalia Krawczyk": "natalia-krawczyk",
}

# --- businesses (seed_data VERTICALS[...]["providers"] names) --------------

# Empty by default: the shipped verticals ship no photography, so `_media()`
# misses and the seeder falls back to its generated SVG tiles. Add slugs here
# alongside files in `frontend/public/media/homes/` to use real images.
PROVIDERS: dict[str, str] = {}

# --- service + resource tiles ----------------------------------------------
# `seed.py` asks for a tile twice per row: once with the service name and once
# with the resource name, so both kinds of key live in one dict.

# Same: empty until a deployment adds its own tiles under
# `frontend/public/media/arrangements/`.
TILES: dict[str, str] = {}


def person_avatar(name: str) -> str | None:
    """Portrait for a seeded person, or None → caller uses `avatar_uri`."""
    slug = PEOPLE.get(name)
    return f"/media/avatars/{slug}.jpg" if slug else None


def provider_avatar(name: str) -> str | None:
    """Square image for a business, or None → caller uses `avatar_uri`."""
    slug = PROVIDERS.get(name)
    return f"/media/homes/{slug}.jpg" if slug else None


def provider_cover(name: str) -> str | None:
    """Wide banner for a business, or None → caller uses `cover_uri`."""
    slug = PROVIDERS.get(name)
    return f"/media/homes/{slug}-cover.jpg" if slug else None


def tile(name: str) -> str | None:
    """Card image for a service or a resource, or None → caller uses `tile_uri`."""
    slug = TILES.get(name)
    return f"/media/arrangements/{slug}.jpg" if slug else None
