"""Real photography for the funeral-home seed — a thin, optional override layer.

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
half-populated media directory must never break a reseed — it can only make the
demo less pretty. Nothing in this module touches the filesystem or the network,
so it cannot fail either.

Paths mirror the directory layout under `frontend/public/media/`:

    /media/avatars/<slug>.jpg        people (directors and families)
    /media/homes/<slug>.jpg          a funeral home, square
    /media/homes/<slug>-cover.jpg    a funeral home, wide banner
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

# --- funeral homes (seed_data VERTICALS["funeral"]["providers"] names) -----

PROVIDERS: dict[str, str] = {
    "Wieczny Spokój": "wieczny-spokoj",
    "Kaplica Lipowa": "kaplica-lipowa",
    "Dom Żałoby Bursztyn": "dom-zaloby-bursztyn",
    "Odra Pamięć": "odra-pamiec",
    "Cichy Dom": "cichy-dom",
    "Ostatnia Granica": "ostatnia-granica",
}

# --- service + resource tiles ----------------------------------------------
# `seed.py` asks for a tile twice per row: once with the service name and once
# with the resource name, so both kinds of key live in one dict.

TILES: dict[str, str] = {
    # services
    "Traditional Funeral Service": "traditional-funeral",
    "Cremation": "cremation",
    "Burial": "burial",
    "Memorial Gathering": "memorial-gathering",
    "Direct Committal": "direct-committal",
    "Pre-Need Arrangement": "pre-need-arrangement",
    "Cryogenic Suspension": "cryogenic-suspension",
    "Orbital Committal": "orbital-committal",
    "Nocturnal Aftercare Programme": "nocturnal-aftercare",
    "Discreet Arrangement": "discreet-arrangement",
    "Adjacent Plot Reservation": "adjacent-plot",
    # the fallback service the non-demo homes get
    "Funeral Arrangement": "traditional-funeral",
    # resources
    "Chapel of Rest A": "chapel-a",
    "Chapel of Rest B": "chapel-b",
    "Chapel of Rest": "chapel-a",
    "Hearse — Mercedes S-Class": "hearse-mercedes",
    "Hearse — Rolls-Royce Phantom": "hearse-rolls-royce",
    "Hearse — Horse-Drawn": "hearse-horse-drawn",
    "Retort 1": "retort-1",
    "Retort 2": "retort-2",
    "Preparation Suite": "preparation-suite",
    "Cryo-Vault Bay 3": "cryo-vault",
    "Launch Pad 4": "launch-pad",
}


def person_avatar(name: str) -> str | None:
    """Portrait for a seeded person, or None → caller uses `avatar_uri`."""
    slug = PEOPLE.get(name)
    return f"/media/avatars/{slug}.jpg" if slug else None


def provider_avatar(name: str) -> str | None:
    """Square image for a funeral home, or None → caller uses `avatar_uri`."""
    slug = PROVIDERS.get(name)
    return f"/media/homes/{slug}.jpg" if slug else None


def provider_cover(name: str) -> str | None:
    """Wide banner for a funeral home, or None → caller uses `cover_uri`."""
    slug = PROVIDERS.get(name)
    return f"/media/homes/{slug}-cover.jpg" if slug else None


def tile(name: str) -> str | None:
    """Card image for a service or a resource, or None → caller uses `tile_uri`."""
    slug = TILES.get(name)
    return f"/media/arrangements/{slug}.jpg" if slug else None
