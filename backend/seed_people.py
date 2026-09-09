"""The cast for the demo seed: the people who appear in it, and the
prose that passes between them.

Pure data + tiny helpers, no DB, no config, no imports from `seed.py`. The
assembler in `seed.py` turns these into Supabase auth users, `profiles` rows,
bookings, reviews and message threads.

Three logins are contractual and must not change; the demo script, the
frontend's one-tap sign-in buttons and the README all name them:

    demo@codaro.app      the established bereaved family (owns the seed bookings)
    owner@codaro.app     the business owner (owns the demo provider)
    prospect@codaro.app  a fresh family whose request waits in the Requests tab

Every name in `CAST` is also a key in `seed_media.PEOPLE`, which maps it to a
real portrait under `frontend/public/media/avatars/`. **Adding a name here that
is not in that map gives that person a generated initials gradient instead of a
face**, harmless, but the demo is poorer for it. Keep the two lists together.

Tone note for anyone editing the strings below: the copy is written straight.
These are real bereavements handled by professionals, and the funnier the
service being arranged, the more sincere the sentence about it should be.
Nobody in this file is ever in on the joke.
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

# Everyone in the cast who is a bereaved family rather than the home's own
# people. Seeded bookings, reviews, follows and message threads draw from here.
ALL_CLIENTS = [p for p in CAST if p["role"] == "client"]

STAFF = [p for p in CAST if p["role"] == "staff"]


def client_by_email(email: str) -> dict | None:
    return next((p for p in CAST if p["email"] == email), None)
# --- booking prose ----------------------------------------------------------
# The values for `metaFields.bookings`. The payer is never the subject, that
# separation is the entire premise of this pivot, so it is expressed in data
# rather than assumed by the code.

# --- prose: reviews families left about the home ----------------------------
# (rating, days_ago, text). Attached by `seed.py` to completed bookings, one
# each, so a review always has a booking behind it.

# --- prose: reviews the DEMO family left ------------------------------------
# `demo@codaro.app` is the account the demonstration is given from, so its own
# completed arrangements carry reviews written in its own voice, a customer
# whose history shows "no review" on every past booking has no reputation and
# nothing for the account page to render. Same (rating, days_ago, text) shape as
# `PROVIDER_REVIEWS`; the seeder derives the real date from the booking.

# --- prose: reviews the home left about a family ----------------------------
# (rating, text). These become the customer's reputation on the owner side.

# --- prose: what the home thinks of the DEMO family -------------------------
# The demonstration account's own reputation. `GET /me/reputation` averages
# every `client_reviews` row for a person, so the account page needs several
# against different arrangements rather than one against one, a single review
# renders as "5.0 (1)", which reads as an empty profile with a number on it.

# --- prose: the inbox -------------------------------------------------------
# (client_email, hours_ago, [(from_client, body), ...]).
# `from_client=True` means the family wrote it; False means the home did.
# `hours_ago` anchors the FIRST message; the rest follow at plausible gaps.
#
# Thread 0 deliberately ENDS on the home assigning a date. The demo's core
# mechanic, the business picks the date, the family confirms, must be legible
# from the inbox before anyone clicks anything. Two later threads carry the same
# announcement, so the inbox reads that way wherever you land in it.

# --- more of the dead -------------------------------------------------------
# A home this size buries more people in four months than anyone wants to write
# by hand, and the same name appearing on two bookings is the one detail that
# makes a demo read as fake. Past the hand-written entries above, the seeder
# draws a fresh name from these pools and dresses it in an earlier entry's
# circumstances, the prose stays real, the roll of the dead stays distinct.

_EXTRA_FIRST = [
    "Wacław", "Bożena", "Ryszarda", "Ludwik", "Jolanta", "Sławomir", "Grażyna",
    "Bogusław", "Aleksandra", "Kazimiera", "Jerzy", "Wiesława", "Zenon", "Iwona",
    "Mirosław", "Krystian", "Longin", "Emilia", "Tadeusza", "Olgierd", "Janina",
    "Alfred", "Melania", "Sylwester", "Regina", "Konrad", "Otylia", "Rafał",
]

_EXTRA_LAST = [
    "Borowiec", "Jastrzębski", "Głowacka", "Tomczyk", "Wilk", "Sowa", "Baranowski",
    "Czerwińska", "Wesołowski", "Poniatowska", "Sikorski", "Lewicka", "Brzeziński",
    "Nawrocka", "Stasiak", "Wieczorek", "Domagała", "Kołodziej", "Trojanowska",
    "Zielonka", "Piechota", "Rybak", "Śliwińska", "Antczak", "Górniak", "Owczarek",
]

