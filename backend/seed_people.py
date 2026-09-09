# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""The cast for the demo seed: the people who appear in it, and the
people who appear in it.

Pure data + tiny helpers, no DB, no config, no imports from `seed.py`. The
assembler in `seed.py` turns these into Supabase auth users, `profiles` rows,
bookings, reviews and message threads.

Three logins are contractual and must not change; the demo script and the
frontend's one-tap sign-in buttons both name them:

    demo@codaro.app      the established customer (owns the seed bookings)
    owner@codaro.app     the business owner (owns the demo provider)
    prospect@codaro.app  a fresh customer whose request waits in the Requests tab

Every name in `CAST` is also a key in `seed_media.PEOPLE`, which maps it to a
real portrait under `frontend/public/media/avatars/`. **Adding a name here that
is not in that map gives that person a generated initials gradient instead of a
face**, harmless, but the demo is poorer for it. Keep the two lists together.
"""
from __future__ import annotations

import secrets

# --- logins (mirrored by seed.py's *_EMAIL constants) ----------------------

DEMO_EMAIL = "demo@codaro.app"
OWNER_EMAIL = "owner@codaro.app"
PROSPECT_EMAIL = "prospect@codaro.app"


def throwaway_password() -> str:
    """A password for a seeded account nobody is meant to log into (the cast and
    the 'holds' user that owns the already-taken capacity). Never printed."""
    return "Cd-" + secrets.token_urlsafe(21) + "-9"


def _person(name: str, email: str, *, role: str = "client", verified: bool = True,
            title: str = "") -> dict:
    """One seeded person. `role` is the config-driven owner/client split; the
    backend re-derives it from the `profiles` row, so this is seed input only.
    `title` is prose only, a staff job description, never a permission."""
    parts = [p for p in name.split() if p]
    return {
        "name": name,
        "email": email,
        "role": role,
        "verified": verified,
        "title": title,
        "firstName": parts[0] if parts else name,
        "lastName": parts[-1] if len(parts) > 1 else "",
        "initials": ((parts[0][:1] if parts else "?") + (parts[-1][:1] if len(parts) > 1 else "")).upper(),
    }


# --- the three fixed logins ------------------------------------------------

# The business owner, who owns the demo provider.
OWNER = _person("Henryk Walczak", OWNER_EMAIL, role="owner", title="Owner")

# The established family, has arranged with the home before, so their history,
# reviews and reputation are populated.
DEMO = _person("Mara Lindqvist", DEMO_EMAIL)

# The new family, one pending request, no history. The counterpart to DEMO.
PROSPECT = _person("Tomasz Wiśniewski", PROSPECT_EMAIL, verified=False)


# --- the cast ---------------------------------------------------------------
# APPEND rather than reorder: `seed_media.PEOPLE` is keyed by display name and
# the message threads below are keyed by email, so neither cares about order,
# but a reader diffing two seeds does.

CAST = [
    DEMO,
    PROSPECT,
    _person("Agnieszka Nowak", "a.nowak@example.com"),
    _person("Elżbieta Kamińska", "e.kaminska@example.com"),
    _person("Jan Dąbrowski", "j.dabrowski@example.com"),
    _person("Piotr Zieliński", "p.zielinski@example.com"),
    _person("Katarzyna Lewandowska", "k.lewandowska@example.com"),
    _person("Marek Kowalczyk", "m.kowalczyk@example.com"),
    _person("Beata Szymańska", "b.szymanska@example.com"),
    _person("Lukas Behrend", "l.behrend@example.com"),
    _person("Zofia Adamska", "z.adamska@example.com"),
    _person("Paweł Górski", "p.gorski@example.com"),
    _person("Irena Wójcik", "i.wojcik@example.com", verified=False),
    _person("Michał Sikora", "m.sikora@example.com"),
    _person("Halina Baran", "h.baran@example.com"),
    _person("Robert Mazur", "r.mazur@example.com"),
    _person("Ewa Duda", "e.duda@example.com"),
    _person("Andrzej Stępień", "a.stepien@example.com", verified=False),
    _person("Natalia Krawczyk", "n.krawczyk@example.com"),
    # Staff. Seeded as real users so their portraits exist and the director can
    # name them in a thread ("Dorota will telephone you"), but they arrange no
    # bookings of their own, so `ALL_CLIENTS` leaves them out.
    _person("Dorota Sadowska", "d.sadowska@wieczny-spokoj.example.com",
            role="staff", title="Arrangements coordinator"),
    _person("Krzysztof Malinowski", "k.malinowski@wieczny-spokoj.example.com",
            role="staff", title="Mortician"),
    OWNER,
]

# Everyone in the cast who is a customer rather than the business's own
# people. Seeded bookings, reviews, follows and message threads draw from here.
ALL_CLIENTS = [p for p in CAST if p["role"] == "client"]

# --- booking prose ----------------------------------------------------------
# The values for `metaFields.bookings`. The payer is never the subject, that
# separation is the entire premise of this pivot, so it is expressed in data
# rather than assumed by the code.
