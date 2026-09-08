"""The cast for the funeral-home demo seed: people, the dead they bury, and the
prose that passes between them.

Pure data + tiny helpers — no DB, no config, no imports from `seed.py`. The
assembler in `seed.py` turns these into Supabase auth users, `profiles` rows,
bookings, reviews and message threads.

Three logins are contractual and must not change; the demo script, the
frontend's one-tap sign-in buttons and the README all name them:

    demo@codaro.app      the established bereaved family (owns the seed bookings)
    owner@codaro.app     the funeral director (owns the demo provider)
    prospect@codaro.app  a fresh family whose request waits in the Requests tab

Every name in `CAST` is also a key in `seed_media.PEOPLE`, which maps it to a
real portrait under `frontend/public/media/avatars/`. **Adding a name here that
is not in that map gives that person a generated initials gradient instead of a
face** — harmless, but the demo is poorer for it. Keep the two lists together.

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
    `title` is prose only — a staff job description, never a permission."""
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

# The funeral director. Third generation; signs every arrangement personally.
OWNER = _person("Henryk Walczak", OWNER_EMAIL, role="owner", title="Funeral director")

# The established family — has arranged with the home before, so their history,
# reviews and reputation are populated.
DEMO = _person("Mara Lindqvist", DEMO_EMAIL)

# The new family — one pending request, no history. The counterpart to DEMO.
PROSPECT = _person("Tomasz Wiśniewski", PROSPECT_EMAIL, verified=False)


# --- the cast ---------------------------------------------------------------
# APPEND rather than reorder: `seed_media.PEOPLE` is keyed by display name and
# the message threads below are keyed by email, so neither cares about order —
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
    # funerals of their own, so `ALL_CLIENTS` leaves them out.
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


# --- the deceased -----------------------------------------------------------
# `booking.subject` in domain.config.json declares nine fields; each entry below
# fills them. `diedDaysBefore` is relative to the date of the service, so the
# arithmetic stays plausible however far in the past or future the seed places
# the booking — a body is buried days after the death, not on a fixed date.
#
# `manner` must be one of the config's four select options. Four of the entries
# below say "Mysterious circumstances — no questions asked", which is what
# triggers the discreet-handling tier in `pricing.tiers`. That is deliberate: a
# tier nothing exercises is a tier nobody believes.

_MYSTERY = "Mysterious circumstances — no questions asked"


def _dead(name, born, died_before, pronouns, rite, manner, height, pacemaker, attire) -> dict:
    return {
        "full_name": name,
        "date_of_birth": born,
        "diedDaysBefore": died_before,
        "pronouns": pronouns,
        "faith_or_rite": rite,
        "manner_of_death": manner,
        "height_cm": height,
        "pacemaker_present": pacemaker,
        "preferred_attire": attire,
    }


DECEASED = [
    _dead("Ingrid Lindqvist", "1938-04-11", 9, "she/her", "Protestant", "Natural causes",
          162, False, "The navy wool suit and the amber brooch."),
    _dead("Stanisław Wiśniewski", "1941-09-02", 6, "he/him", "Catholic", "Natural causes",
          174, True, "Dark grey suit. No tie — he never wore one."),
    _dead("Halina Nowak", "1947-01-23", 11, "she/her", "Catholic", "Natural causes",
          158, False, "The green dress from the cupboard in the hall."),
    _dead("Ryszard Kamiński", "1950-06-30", 5, "he/him", "Secular", "Accident",
          181, False, "His work jacket. The family is certain about this."),
    _dead("Wanda Dąbrowska", "1935-11-08", 14, "she/her", "Catholic", "Natural causes",
          155, True, "Black, plain, with the rosary in her hands."),
    _dead("Józef Zieliński", "1944-03-17", 8, "he/him", "Catholic", "Natural causes",
          176, False, "The brown suit he was married in."),
    _dead("Krystyna Lewandowska", "1952-08-05", 7, "she/her", "Orthodox", "Natural causes",
          164, False, "The cream blouse and the long skirt."),
    _dead("Bogdan Kowalczyk", "1939-12-19", 10, "he/him", "Secular", "Natural causes",
          170, True, "No preference recorded. Please advise."),
    _dead("Marianna Szymańska", "1933-05-27", 13, "she/her", "Catholic", "Natural causes",
          151, False, "The lilac two-piece. She chose it herself in March."),
    _dead("Günter Behrend", "1946-02-14", 6, "he/him", "Protestant", "Natural causes",
          179, False, "Grey flannel. His spectacles, please, in the breast pocket."),
    _dead("Alicja Adamska", "1955-07-09", 4, "she/her", "Humanist", "Accident",
          167, False, "The red coat. She was very clear about the red coat."),
    _dead("Tadeusz Górski", "1937-10-01", 12, "he/him", "Catholic", _MYSTERY,
          172, False, "Closed casket. Attire at the home's discretion."),
    _dead("Zofia Wójcik", "1943-04-25", 9, "she/her", "Catholic", "Natural causes",
          159, True, "The dark blue dress with the white collar."),
    _dead("Antoni Sikora", "1958-01-12", 5, "he/him", "Secular", "Natural causes",
          183, False, "Jeans and the fisherman's jumper. He was not a formal man."),
    _dead("Genowefa Baran", "1930-09-14", 16, "she/her", "Catholic", "Natural causes",
          148, False, "Whatever is in the wardrobe. She kept one good dress."),
    _dead("Wiesław Mazur", "1948-06-06", 8, "he/him", "Orthodox", "Natural causes",
          177, True, "Black suit, white shirt, no cufflinks."),
    _dead("Barbara Duda", "1951-03-03", 7, "she/her", "Secular", "Undisclosed",
          161, False, "The grey trouser suit."),
    _dead("Mieczysław Stępień", "1940-11-21", 11, "he/him", "Catholic", "Natural causes",
          173, False, "His uniform. The medals are in the tin, and the tin is with us."),
    _dead("Danuta Krawczyk", "1949-08-30", 6, "she/her", "Catholic", "Natural causes",
          163, False, "The pale blue dress and her wedding ring, which stays on."),
    _dead("Leszek Pawlak", "1953-05-16", 9, "he/him", "Secular", "Accident",
          178, False, "The corduroy jacket. Nothing underneath it matters."),
    _dead("Urszula Michalska", "1942-12-04", 10, "she/her", "Catholic", "Natural causes",
          156, True, "Black. Her sister will bring it on the Tuesday."),
    _dead("Kazimierz Olszewski", "1936-07-22", 15, "he/him", "Catholic", _MYSTERY,
          169, False, "Closed casket. The family will not be viewing."),
    _dead("Renata Sobczak", "1960-02-08", 4, "she/her", "Humanist", "Natural causes",
          166, False, "The concert dress — she played the cello for forty years."),
    _dead("Edward Jankowski", "1945-10-11", 12, "he/him", "Protestant", "Natural causes",
          175, False, "Tweed. The good tweed, not the everyday one."),
    _dead("Stefania Woźniak", "1934-06-18", 13, "she/her", "Catholic", "Natural causes",
          150, False, "The dark green dress. She had it altered last year."),
    _dead("Marek Chmielewski", "1957-09-27", 5, "he/him", "Secular", "Natural causes",
          182, True, "Football shirt over the shirt and tie. Both, please."),
    _dead("Jadwiga Rutkowska", "1931-01-05", 17, "she/her", "Catholic", "Natural causes",
          147, False, "Whatever is cleanest. She would have said the same."),
    _dead("Zbigniew Kaczmarek", "1954-04-14", 7, "he/him", "Secular", "Undisclosed",
          180, False, "No attire. Direct committal."),
    _dead("Teresa Piotrowska", "1946-11-29", 9, "she/her", "Catholic", "Natural causes",
          160, False, "The coat with the fur collar and the pearl earrings."),
    _dead("Henryk Grabowski", "1938-08-08", 11, "he/him", "Catholic", "Natural causes",
          171, True, "Dark suit. The pacemaker has been noted and must come out."),
    _dead("Lidia Nowicka", "1963-03-31", 3, "she/her", "Humanist", "Accident",
          168, False, "The linen suit. She hated black and said so often."),
    _dead("Czesław Wróbel", "1932-05-09", 14, "he/him", "Catholic", "Natural causes",
          165, False, "The suit in the plastic cover. It has not been worn since 1994."),
    _dead("Maria Lis", "1944-02-26", 8, "she/her", "Orthodox", "Natural causes",
          157, False, "The embroidered blouse her mother made."),
    _dead("Roman Szewczyk", "1959-07-13", 6, "he/him", "Secular", _MYSTERY,
          184, False, "Closed casket. No mourners. No questions."),
    _dead("Elżbieta Bąk", "1950-10-20", 10, "she/her", "Catholic", "Natural causes",
          162, True, "The burgundy dress. Hair as she wore it, not set."),
    _dead("Witold Cieślak", "1947-12-15", 12, "he/him", "Protestant", "Natural causes",
          176, False, "Grey suit, and the reading glasses on the chain."),
    _dead("Anna Sadowska", "1966-06-02", 4, "she/her", "Secular", "Natural causes",
          170, False, "Running kit. She was buried in it at her own instruction."),
    _dead("Bronisław Zawadzki", "1929-04-07", 18, "he/him", "Catholic", "Natural causes",
          167, False, "The dark suit and the war veteran's ribbon."),
    _dead("Sabina Marciniak", "1961-09-19", 5, "she/her", "Jewish", "Natural causes",
          164, False, "Plain white shroud, per the rite. Nothing else."),
    _dead("Feliks Ostrowski", "1941-01-30", 13, "he/him", "Catholic", _MYSTERY,
          173, False, "Closed casket. The estate has instructed discretion throughout."),
    _dead("Wiktoria Dudek", "1937-03-12", 15, "she/her", "Catholic", "Natural causes",
          153, True, "The navy dress with the small buttons."),
    _dead("Norbert Kwiatkowski", "1956-08-24", 7, "he/him", "Secular", "Undisclosed",
          179, False, "The suit he kept for court appearances."),
]


# --- the demo family's own dead --------------------------------------------
# `demo@codaro.app` is the account the demonstration is given from, so its
# bookings list is the most-looked-at screen in the product. A customer with
# four arrangements reads as a test fixture; a customer with thirty reads as a
# family that has been burying people for years — which is exactly what a
# funeral home's returning client is.
#
# Every entry is (deceased, the payer's relationship to them). Mara Lindqvist
# pays every time and is never the deceased, so the relationship is what makes
# the list legible: her mother, then her husband's father, then an aunt, then
# the friend who named her executor. The names appear nowhere else in the seed
# — the same person buried twice is the detail that gives a demo away.
#
# Two entries carry the awkward manner of death, so the €1,200 discreet-handling
# tier is visible in the demo account's OWN history rather than only in the
# anonymous trade behind it.

DEMO_ARRANGEMENTS: list[tuple[dict, str]] = [
    # Her mother. The thread in the inbox is about this one.
    (DECEASED[0], "Child"),
    (_dead("Sven Lindqvist", "1936-02-19", 7, "he/him", "Protestant", "Natural causes",
           178, True, "The grey suit. He is not to be buried in the cardigan."), "Child"),
    (_dead("Aleksander Falk", "1944-08-03", 5, "he/him", "Secular", "Natural causes",
           171, False, "Open collar, no tie. He retired from ties in 1998."), "Spouse"),
    (_dead("Ingeborg Falk", "1947-11-27", 10, "she/her", "Protestant", "Natural causes",
           160, False, "The blue dress and her mother's crucifix, which stays on."), "Other"),
    (_dead("Ottilia Hedlund", "1931-05-14", 12, "she/her", "Protestant", "Natural causes",
           154, True, "The good coat. She wore it to everything for thirty years."), "Other"),
    (_dead("Nils Hedlund", "1929-09-08", 15, "he/him", "Secular", "Natural causes",
           175, False, "His fishing jumper over the shirt. Both, please, in that order."), "Other"),
    (_dead("Wiktor Kruszewski", "1952-03-21", 6, "he/him", "Catholic", "Natural causes",
           180, False, "Dark suit. The union pin on the left lapel."), "Sibling"),
    (_dead("Marta Kruszewska", "1955-07-02", 4, "she/her", "Catholic", "Accident",
           163, False, "The green coat she was wearing. It has been cleaned."), "Sibling"),
    (_dead("Bogumił Podgórny", "1940-12-11", 9, "he/him", "Catholic", _MYSTERY,
           169, False, "Closed casket. The estate has asked for no further detail."), "Executor"),
    (_dead("Cecylia Radomska", "1938-06-25", 11, "she/her", "Catholic", "Natural causes",
           157, True, "The lilac blouse. Hair as she wore it, not set."), "Other"),
    (_dead("Emil Nyström", "1961-01-16", 3, "he/him", "Humanist", "Accident",
           184, False, "Cycling kit. He was very specific and put it in writing."), "Friend"),
    (_dead("Solveig Nyström", "1963-04-09", 8, "she/her", "Humanist", "Natural causes",
           166, False, "The linen suit. No black anywhere, at her instruction."), "Friend"),
    (_dead("Kazimiera Turek", "1934-10-30", 13, "she/her", "Catholic", "Natural causes",
           149, False, "The dress in the brown suitcase. She labelled it herself."), "Other"),
    (_dead("Zenon Turek", "1932-02-07", 16, "he/him", "Catholic", "Natural causes",
           167, True, "The suit from the wedding. It still fits and she checked."), "Other"),
    (_dead("Agata Bielawska", "1957-09-12", 5, "she/her", "Secular", "Undisclosed",
           170, False, "The concert black. She conducted in it for twenty years."), "Friend"),
    (_dead("Ryszard Modrzejewski", "1949-05-04", 7, "he/him", "Catholic", "Natural causes",
           176, False, "Grey suit, and the reading glasses folded in the pocket."), "Other"),
    (_dead("Halina Modrzejewska", "1951-08-18", 6, "she/her", "Catholic", "Natural causes",
           161, False, "The navy two-piece. The brooch is with her sister."), "Other"),
    (_dead("Torvald Ekström", "1942-11-03", 14, "he/him", "Protestant", "Natural causes",
           182, False, "Tweed and the walking boots. He asked for the boots twice."), "Other"),
    (_dead("Gunilla Ekström", "1945-03-28", 9, "she/her", "Protestant", "Natural causes",
           158, True, "The dark red dress. She thought black was self-pitying."), "Other"),
    (_dead("Jarosław Zaremba", "1953-12-01", 4, "he/him", "Secular", _MYSTERY,
           173, False, "Closed casket. No viewing, no notice in the paper, no questions."), "Executor"),
    (_dead("Wanda Zaremba", "1959-06-14", 10, "she/her", "Secular", "Natural causes",
           164, False, "The trouser suit. She never once wore a skirt and will not start."), "Executor"),
    (_dead("Leon Jelinek", "1937-04-22", 12, "he/him", "Jewish", "Natural causes",
           168, False, "Plain white shroud, per the rite. Nothing else, and nothing added."), "Friend"),
    (_dead("Estera Jelinek", "1941-07-31", 11, "she/her", "Jewish", "Natural causes",
           155, False, "Plain white shroud. The rite is to be followed exactly."), "Friend"),
    (_dead("Anneli Halvorsen", "1966-02-11", 3, "she/her", "Humanist", "Accident",
           172, False, "The red coat, and the walking stick beside her."), "Sibling"),
    (_dead("Krystian Podgórny", "1946-09-06", 8, "he/him", "Catholic", "Natural causes",
           174, True, "Dark suit. The pacemaker is noted and must be removed first."), "Executor"),
    (_dead("Mirosława Kruszewska", "1943-01-19", 13, "she/her", "Catholic", "Natural causes",
           152, False, "The dress with the small white collar, pressed and hanging."), "Parent"),
    (_dead("Bengt Falk", "1958-10-25", 6, "he/him", "Secular", "Natural causes",
           179, False, "The corduroy jacket. He owned one and wore it to everything."), "Spouse"),
    (_dead("Rozalia Bielawska", "1930-08-13", 17, "she/her", "Orthodox", "Natural causes",
           146, False, "The embroidered blouse. Her mother made it and it is to go with her."), "Other"),
    (_dead("Fredrik Hedlund", "1968-05-07", 4, "he/him", "Humanist", "Undisclosed",
           181, False, "Whatever is at the front of the wardrobe. He would not have minded."), "Friend"),
    (_dead("Danuta Modrzejewska", "1935-11-16", 15, "she/her", "Catholic", "Natural causes",
           150, True, "Black, plain, and the rosary from the drawer in the kitchen."), "Other"),
]


# --- booking prose ----------------------------------------------------------
# The values for `metaFields.bookings`. The payer is never the deceased — that
# separation is the entire premise of this pivot, so it is expressed in data
# rather than assumed by the code.

PAYER_RELATIONSHIPS = ["Spouse", "Child", "Sibling", "Parent", "Executor", "Friend", "Other"]

PROCESSION_ROUTES = [
    "Powązkowska to the north gate. Walking pace to the corner, then drive.",
    "Direct to the cemetery. No cortège requested.",
    "Past the house on Mickiewicza, once, slowly, then the crematorium.",
    "Chapel to the graveside on foot. Ninety metres; bearers throughout.",
    "Via the harbour road, at the family's request. Adds eleven minutes.",
    "No route — the committal is unattended.",
    "Church of St Karol first, then the cemetery office, then the plot.",
    "Around the market square. The stallholders have been told.",
]

EULOGY_SPEAKERS = [
    "The eldest son.", "Her sister, who will need the lectern lowered.",
    "The celebrant will read it; the family cannot.",
    "A colleague of forty years. Eight minutes, timed.",
    "His granddaughter, aged eleven. Please be patient with her.",
    "No eulogy requested.", "The parish priest, then two readings from the family.",
    "Written by the AI storyteller, read aloud by the celebrant.",
    "Her former student. He asked; the family agreed.",
    "The executor, briefly, on the estate's behalf.",
]

WILL_SURPLUS_NOTES = [
    "", "", "", "", "",
    "The estate is larger than expected. The family would like it spent well.",
    "He left instructions to spare no expense and we intend to honour them.",
    "There is a surplus. We are told he would have found this funny.",
    "The will names a figure for the funeral and it is more than we would have chosen.",
    "No surplus. Please keep to the estimate.",
]


# --- prose: reviews families left about the home ----------------------------
# (rating, days_ago, text). Attached by `seed.py` to completed bookings, one
# each, so a review always has a funeral behind it.

PROVIDER_REVIEWS = [
    (5, 2, "Punctual. Discreet. Five stars."),
    (5, 4, "They handled every document with the registry office so we did not have to. "
           "At no point were we asked to make a decision we were not ready to make."),
    (5, 6, "My mother asked for the horse-drawn hearse. They sourced it, walked the route "
           "the week before to check the surface, and did not once suggest an alternative."),
    (4, 8, "Faultless on the day. The only note is that the initial estimate arrived by post "
           "rather than email, which cost us two days."),
    (5, 9, "We chose the nocturnal programme because of my brother's condition. The chapel was "
           "opened at 23:00 exactly as agreed and the staff were entirely matter-of-fact about it. "
           "That mattered more than I can explain."),
    (5, 11, "Direct committal, no ceremony, as my father instructed. They did not try to sell us "
            "anything. The ashes were returned in eleven days."),
    (4, 13, "Professional throughout. Parking at the chapel is limited — arrive early."),
    (5, 14, "We pre-arranged in the morning and left with a fixed price and a signed folder. "
            "Nobody in this industry has ever been that clear with us before."),
    (5, 16, "The suspension paperwork ran to forty pages and they went through every one of them "
            "with my grandfather, who is 91 and asked a great many questions."),
    (5, 18, "Everything they said would happen, happened, at the time they said it would."),
    (5, 19, "The director carried the casket himself when one of the bearers was taken ill. "
            "He did not mention it afterwards and we only learned of it from a cousin."),
    (4, 21, "Good service, fair price. The livestream link went out twelve minutes late and "
            "my aunt in Chicago missed the first reading."),
    (5, 23, "They found the plot deed from 1971 in the cemetery office archive. It took them "
            "three days and they did not charge us for the time."),
    (3, 24, "The arrangement itself was handled properly. Communication in the first week was "
            "slow — three of my calls were returned the following day rather than the same one."),
    (5, 26, "My wife wanted the string quartet and I thought it excessive. It was not. "
            "I am glad I was overruled."),
    (5, 28, "Twelve doves, exactly as described, at exactly the right moment. "
            "I have no idea how that is arranged and I did not ask."),
    (4, 30, "Everything correct. The order of service had one spelling error in a middle name, "
            "corrected and reprinted within the hour once we pointed it out."),
    (5, 32, "We came in at nine in the morning having decided nothing. We left at eleven with "
            "everything decided. That is what we needed."),
    (5, 34, "The memorial ring arrived in nine weeks as promised. It is heavier than I expected "
            "and I wear it every day."),
    (5, 36, "They dealt with my brother, who was difficult, with more patience than I managed."),
    (4, 38, "Clear pricing, no surprises on the final invoice. The chapel was colder than "
            "we would have liked in February."),
    (5, 40, "The eternal flowers were my mother's idea and I was against it. Two years on "
            "they are still on the grave and still perfect. She was right."),
    (5, 42, "Second time we have used them, ten years apart, and the standard has not moved."),
    (5, 44, "A star was named for my daughter. The certificate is framed in the hall. "
            "It is not what I would have chosen for myself but it is what she asked for."),
    (4, 46, "Thorough and calm. One small thing: nobody told us the retort cycle takes "
            "ninety minutes, so we waited in the car park not knowing whether to leave."),
    (5, 48, "The professional mourners were in the will. They arrived, they were excellent, "
            "and nobody outside the family knew they were not family."),
    (5, 51, "They collected my husband at two in the morning and were at the house within "
            "forty minutes. The person who came in was kind and said very little, which was right."),
    (5, 54, "Not one thing went wrong. I keep looking for something to mention and there isn't one."),
    (3, 57, "The service was fine. We felt the upsell conversation about the casket came "
            "too early, on the same morning we registered the death."),
    (5, 60, "The AI storyteller drafted a life for my father from three photographs and an "
            "hour of talking. It was accurate. Several people cried who had not intended to."),
    (5, 63, "Cremation, no ceremony, ashes in eleven days. Exactly the arrangement he wanted "
            "and exactly the price quoted."),
    (4, 66, "Reliable and unfussy. The invoice arrived a fortnight later than we expected."),
    (5, 70, "The adjacent plot was reserved the same afternoon and the deed came through in "
            "six weeks. My mother now knows where she is going and it has settled her."),
    (5, 74, "They did not once refer to my son as 'the deceased' in front of me. "
            "They used his name. It sounds like nothing. It is not nothing."),
    (5, 79, "Everything was in writing before anything was signed."),
    (4, 84, "Good, careful people. The cortège set off nine minutes late because of a road "
            "closure they could not have known about."),
    (5, 88, "The bearers were the same four men as last time. It should not matter and it did."),
    (5, 92, "We asked for no ceremony and got no ceremony. Nobody tried to talk us into one."),
    (4, 96, "Correct and courteous. The order of service went to print before we had approved "
            "the final draft; they reprinted it without argument."),
    (5, 100, "My father's arrangement was paid for in 1997 and they honoured every line of it "
             "at 1997 prices. I did not expect that and I want it recorded."),
    (5, 104, "The chapel was opened an hour early so my grandmother could sit with him alone. "
             "No one hurried her and nothing was charged for it."),
    (4, 108, "Efficient. The estimate and the invoice matched to the euro."),
    (5, 112, "They telephoned the week after to ask how we were. It was not a sales call."),
    (5, 118, "Twenty-two years we have used this home. Four funerals. Never a complaint."),
    (5, 124, "The launch slipped by nine months and they wrote to us every quarter exactly as "
             "they said they would. When it went up they sent the tracking data unprompted."),
    (4, 130, "Everything handled properly. Parking is genuinely difficult on a Saturday."),
    (5, 136, "They talked my brother out of a casket he could not afford and into one that was "
             "better made. That conversation cost them money and they had it anyway."),
    (5, 142, "The horse was late. The director walked the last two hundred metres with the "
             "coffin rather than let us stand there, and nobody watching knew anything was wrong."),
    (5, 148, "Quiet, competent, unhurried. There is nothing else to say about it."),
    (4, 155, "A good service at a fair price. The livestream quality was poorer than promised."),
]


# --- prose: reviews the DEMO family left ------------------------------------
# `demo@codaro.app` is the account the demonstration is given from, so its own
# completed arrangements carry reviews written in its own voice — a customer
# whose history shows "no review" on every past funeral has no reputation and
# nothing for the account page to render. Same (rating, days_ago, text) shape as
# `PROVIDER_REVIEWS`; the seeder derives the real date from the funeral.

DEMO_REVIEWS = [
    (5, 3, "My mother's was the fourth funeral this home has arranged for our family and it "
           "was the fourth one I have had no note to make about."),
    (5, 6, "They assigned the date within a day of the certificate arriving and it did not move "
           "once. Everything after that was somebody else's problem, which is what I was paying for."),
    (5, 9, "The discreet arrangement was handled with no conversation whatsoever, which is what "
           "the estate had instructed and what I had dreaded having to ask for."),
    (4, 12, "Faultless on the day. The invoice reached me before the thank-you cards did, "
            "which felt brisk."),
    (5, 15, "My aunt wanted the horse-drawn hearse and the family thought it a vanity. "
            "It was not. Half the street came out."),
    (5, 19, "Second cremation we have arranged here in eighteen months. Same people, same care, "
            "same eleven days for the ashes."),
    (5, 23, "The nocturnal programme, again, without a single question asked about why. "
            "That is worth more to this family than anything else on the invoice."),
    (4, 27, "Everything correct. I would have liked the plot deed reference in writing sooner."),
    (5, 31, "They found my father-in-law's pre-need folder from 2004 in an afternoon."),
    (5, 36, "The memorial gathering ran forty minutes over and nobody so much as looked at a watch."),
    (5, 41, "I have now arranged eleven funerals through this home. I have never once been "
            "upsold and I have never once been late."),
    (4, 47, "Straightforward and kind. The cortège route we asked for had to be changed on the "
            "morning because of roadworks; we were told at the house rather than at the chapel."),
]


# --- prose: reviews the home left about a family ----------------------------
# (rating, text). These become the customer's reputation on the owner side.

CLIENT_REVIEWS = [
    (5, "Clear about their wishes from the first meeting and reachable throughout. "
        "Every document came back signed the same day."),
    (5, "Considerate of our staff and of the other families using the chapel that morning. "
        "We would be glad to serve them again."),
    (5, "Settled the account in full before the service without being asked. "
        "A straightforward and dignified arrangement."),
    (4, "Arrangements were changed twice, both times with ample notice. No difficulty at all."),
    (5, "Brought the garments on the Tuesday as agreed, pressed and labelled. "
        "It is a small thing and it makes the whole week easier."),
    (5, "Decided quickly and did not revisit decisions. The service ran to the minute."),
    (4, "One late change to the order of service, handled politely. Balance settled on the day."),
    (5, "The family briefed us properly on who should not be seated together. "
        "That briefing prevented an incident and we are grateful for it."),
    (5, "Executor was precise, prompt and had the estate reference to hand at every call."),
    (3, "The arrangement was completed properly. Two invoices required a reminder."),
    (5, "Kind to our bearers in poor weather. Insisted they come inside for tea afterwards."),
    (4, "Straightforward throughout. The final headcount arrived later than we prefer."),
    (5, "A difficult week for them and they were courteous at every point of it."),
    (5, "Returned the chapel key the same afternoon and left the family room as they found it."),
    (5, "Gave us the mourner numbers eight days out and they were accurate to three. "
        "Nobody ever does that."),
    (4, "Pleasant to deal with. One deposit arrived after the reminder rather than before it."),
    (5, "Took our advice on the casket and thanked us for it afterwards, which is rarer "
        "than it sounds."),
    (5, "Handled a difficult relative at the graveside themselves and did not ask us to."),
    (4, "Everything in order. The garments came on the morning rather than the day before, "
        "which is tighter than we like but was manageable."),
    (5, "Three arrangements with this family now. Clear every time, prompt every time."),
    (5, "Sent the photographs Krzysztof asked for within the hour and answered every follow-up "
        "question about them without being pressed."),
    (5, "Wrote afterwards to thank the bearers by name. We have put the letter on the wall."),
]


# --- prose: what the home thinks of the DEMO family -------------------------
# The demonstration account's own reputation. `GET /me/reputation` averages
# every `client_reviews` row for a person, so the account page needs several
# against different arrangements rather than one against one — a single review
# renders as "5.0 (1)", which reads as an empty profile with a number on it.

DEMO_CLIENT_REVIEWS = [
    (5, "A family we have served for many years and never once had to chase. "
        "Decisions arrive quickly, documents arrive signed, and the account is settled early."),
    (5, "Briefed us properly on who should not be seated together, as they always do. "
        "The service ran to the minute."),
    (5, "Handled the discreet arrangement with complete composure and asked us for nothing "
        "we could not give. An exemplary executor."),
    (4, "Straightforward throughout. One late change to the order of service, notified "
        "with ample time and handled without difficulty."),
    (5, "Kind to our bearers in appalling weather and insisted they come in for tea. "
        "We would be glad to serve this family again, and expect that we will."),
]


# --- prose: the inbox -------------------------------------------------------
# (client_email, hours_ago, [(from_client, body), ...]).
# `from_client=True` means the family wrote it; False means the home did.
# `hours_ago` anchors the FIRST message; the rest follow at plausible gaps.
#
# Thread 0 deliberately ENDS on the home assigning a date. The demo's core
# mechanic — the business picks the date, the family confirms — must be legible
# from the inbox before anyone clicks anything. Two later threads carry the same
# announcement, so the inbox reads that way wherever you land in it.

THREADS = [
    # --- the demonstration account's own thread ------------------------------
    # `conversations` is unique on (provider_id, client_id), so `demo@codaro.app`
    # has exactly ONE thread with the home for all time. It is therefore the
    # single most-read screen on the customer side and has to carry the whole
    # arc by itself: first contact, the documents, THE DATE BEING ASSIGNED,
    # the add-ons, the thanks. Three segments so the timestamps run over weeks
    # rather than over an afternoon; `seed.py` merges them into one thread and
    # leaves the last message unread, so the badge is lit at sign-in.
    (DEMO_EMAIL, 1180, [
        (True, "Good evening. My mother, Ingrid Lindqvist, died at the hospice on Powsińska "
               "this afternoon. I have used you before — twice — and I would like to again."),
        (False, "I am very sorry. I have your family's file open and I recognise the name. "
                "Nothing has to be decided tonight."),
        (False, "Two practical things and then I will leave you alone. The hospice will issue "
                "the medical certificate; it usually takes them two working days. And we can "
                "collect her whenever you are ready — there is no hurry from our side."),
        (True, "Tomorrow morning, if that is possible. I do not want her there over the weekend."),
        (False, "Two of our people will be with the hospice at eight. They will not ask you "
                "anything except to confirm who they are collecting."),
        (False, "She is with us and in the care of Krzysztof. I will write again when the "
                "certificate reaches me."),
    ]),
    (DEMO_EMAIL, 470, [
        (True, "It has been four days and the hospice has still not sent anything. "
               "Am I supposed to be chasing them?"),
        (False, "You are not. I chased them this morning and again at two. The delay is a "
                "locum signature, not a problem with the paperwork itself."),
        (False, "It has arrived. The registry entry is filed and the burial permit is issued — "
                "you do not need to attend the registry office in person."),
        (True, "That is a relief. What do you need from me now?"),
        (False, "Three things, and none of them urgent: the garments, a photograph or two for "
                "Krzysztof to work from, and your text for the order of service."),
        (True, "The navy wool suit and the amber brooch. I will bring them Tuesday. "
               "The photographs I can send tonight."),
        (False, "Tuesday is fine. Send the photographs whenever — the informal ones are more "
                "use to him than a formal portrait."),
        (True, "Sent. The one on the balcony is the one she would have chosen."),
        (False, "It is a good photograph and he has said so. "
                "I will have a date for you once the chapel schedule for the 14th is fixed."),
        (False, "Your date has been set: Thursday the 14th, 11:00, Chapel of Rest A. "
                "The Mercedes S-Class hearse is assigned and will collect from the family "
                "address at 10:15. Please confirm in the app and the slot is held."),
        (True, "Confirming now. Is there time for a reading before the committal?"),
        (False, "There is. We allow eighteen minutes at the lectern; anything longer and the "
                "next family waits. I have noted one reading against the order of service."),
        (True, "Thank you. My brother will read."),
        (False, "Noted. Dorota will telephone him on Wednesday to walk through the running order."),
    ]),
    (DEMO_EMAIL, 30, [
        (True, "Two questions about the extras, if you have a moment. "
               "Is the string quartet the same one as for my father-in-law in 2023?"),
        (False, "The same four players, yes. They have the chapel's acoustics by heart "
                "and they do not need a rehearsal."),
        (True, "Then please book them. And the doves — my mother would have called it "
               "a vanity, but my brother has asked."),
        (False, "Twelve doves, released as the cortège leaves the chapel. "
                "They are added to the estimate at €640 and I have sent the revised copy."),
        (False, "One more thing you have not asked about: the eternal flowers. "
                "Your father took them in 2019 and they are still on his grave. "
                "I mention it only because the grave is being reopened and it is easier now."),
        (True, "Add them. She would have wanted to match him."),
        (False, "Added. Nothing further is needed from you before Thursday."),
        (True, "Thank you — genuinely. This is the third time this family has been through "
               "this with you and it has never once been made harder than it had to be."),
        (False, "That is the whole job. Dorota will be at the door from 10:30 on Thursday and "
                "I will be there myself for the committal."),
        (False, "One last practical note, and then I will leave you to the week: the memorial "
                "ring your brother asked about takes nine weeks from the day we send the "
                "impression. If you want it for the anniversary, tell me on Thursday and "
                "I will start it that afternoon."),
    ]),
    (PROSPECT_EMAIL, 7, [
        (True, "Hello — I submitted a request for a direct committal yesterday. "
               "Is there anything else you need from me before it can be approved?"),
        (False, "Nothing further. I have your request open now and will assign a date this "
                "afternoon once the retort schedule for next week is fixed."),
    ]),
    ("a.nowak@example.com", 51, [
        (True, "I would like to ask about the nocturnal programme. My son cannot be outdoors "
               "in daylight — this is a medical matter and I would rather not explain it twice."),
        (False, "You will not have to. The programme exists for exactly this reason. "
                "The chapel is opened after sunset, the west windows are shuttered, and the "
                "cortège route is planned to avoid the eastern approach at dawn. "
                "We do not record the reason on the file."),
        (True, "Thank you. That is the first sensible answer I have had from anyone."),
        (False, "Your date has been set: Saturday the 23rd, 22:30, Chapel of Rest B. "
                "The shutters go up at 21:00. Please confirm and I will hold it."),
        (True, "Confirmed. We will be there from nine."),
    ]),
    ("e.kaminska@example.com", 96, [
        (True, "Regarding the adjacent plot — can we see who is already interred either side "
               "before we commit? My husband was particular about company."),
        (False, "Yes. The cemetery register is public and I can print the two neighbouring "
                "entries for you. Section 12 currently has a retired harbour pilot to the north "
                "and an unoccupied reservation to the south."),
        (True, "A harbour pilot would suit him. Please reserve it."),
        (False, "Reserved. The deed takes about six weeks to come through from the cemetery office; "
                "the reservation holds from today regardless."),
    ]),
    ("j.dabrowski@example.com", 140, [
        (True, "The estimate mentions a Cryo-Vault bay. My father put this in his will and "
               "I confess I assumed it was a joke."),
        (False, "It was not. Bay 3 is held in his name, cooling is maintained at −196 °C, and "
                "the standing order is paid annually each January. "
                "I will send you the maintenance schedule and the escrow terms."),
        (True, "Please do."),
        (False, "Sent. The escrow is with the same firm that holds our pre-need accounts; "
                "there is a clause covering what happens if the company ceases to trade."),
        (True, "That was the clause I was going to ask about. Thank you for anticipating it."),
    ]),
    ("p.zielinski@example.com", 20, [
        (True, "We are still waiting on the death certificate from the hospital. "
               "Does that stop the request going through?"),
        (False, "It does not stop the request, only the registry filing. Send it whenever it "
                "arrives; a photograph of it is sufficient to begin."),
        (True, "It came this morning. Attaching now."),
        (False, "Received and legible. The registry entry will be filed before noon tomorrow."),
        (True, "Thank you."),
    ]),
    ("k.lewandowska@example.com", 5, [
        (True, "Is the string quartet still available for the 19th? My sister has changed her mind "
               "about the cellist."),
        (False, "The quartet is free that morning. I will move the booking across; "
                "the difference is €430 and it will show on the revised estimate."),
        (True, "That is fine. Please go ahead."),
    ]),
    ("m.kowalczyk@example.com", 74, [
        (True, "Good evening. My father died at home about an hour ago. I do not know what to do next."),
        (False, "I am sorry. Nothing needs deciding tonight. A doctor has to attend and certify "
                "before we can collect — if one has not been called, call the out-of-hours number now."),
        (True, "The doctor has been and gone."),
        (False, "Then we can collect whenever you are ready. We have a vehicle out until 23:00 and "
                "another available immediately after. There is no hurry from our side."),
        (True, "Immediately after, please."),
        (False, "Two of our people will be with you by 23:40. They will not ask you anything "
                "except where he is."),
        (True, "Thank you."),
    ]),
    ("b.szymanska@example.com", 130, [
        (True, "Could you confirm what is included in the €780 memorial gathering? "
               "The website says catering for forty and I want to be sure that is not extra."),
        (False, "Catering for forty is included, as is the lectern time, the chapel laid out for a "
                "gathering, and the printed cards. Anything above forty covers is €14 a head."),
        (True, "We are expecting fifty-five."),
        (False, "Then the addition is €210. I have put it on the estimate rather than leave it "
                "to be discovered on the invoice."),
    ]),
    ("l.behrend@example.com", 200, [
        (True, "Guten Tag. I am arranging from Hamburg. Can everything be done remotely?"),
        (False, "All of it except the identification, which must be done in person by someone "
                "named on the form. If you cannot travel, you may nominate anyone in Warsaw."),
        (True, "My cousin lives in Praga. I will nominate her."),
        (False, "Send me her full name and identity document number and I will add her to the form."),
        (True, "Sent this morning."),
        (False, "Added. She can come any weekday between 08:00 and 18:00; no appointment needed."),
    ]),
    ("z.adamska@example.com", 12, [
        (True, "The eternal flowers — are they genuinely permanent? "
               "My mother has been sold 'permanent' things before."),
        (False, "They are 3D-printed in a UV-stable polymer. They do not wilt and they do not fade. "
                "The grounds staff wash them twice a year at no charge."),
        (True, "Then we will take them."),
    ]),
    ("p.gorski@example.com", 44, [
        (True, "I would like to cancel the arrangement for the 6th. Circumstances have changed."),
        (False, "Cancelled. You are outside the 48-hour window, so nothing is charged and the "
                "deposit is returned in full within five working days."),
        (True, "That is a relief. Thank you for being straightforward about it."),
    ]),
    ("i.wojcik@example.com", 3, [
        (True, "Hello. I have sent the request but I cannot see it anywhere in the app."),
        (False, "It is with me — requests sit with the home until a date is assigned, which is "
                "why it does not yet appear on your calendar. I will assign one this afternoon."),
    ]),
    ("m.sikora@example.com", 160, [
        (True, "My uncle wanted an orbital committal. I have read the page four times and I still "
               "do not understand what actually happens."),
        (False, "A sealed capsule containing a portion of the ashes is placed on a rideshare launch. "
                "It reaches low orbit, circles for between eighteen months and four years, and then "
                "re-enters and burns up entirely. The remainder of the ashes stay with you."),
        (True, "And if the launch is delayed?"),
        (False, "It usually is. The capsule is stored here, in his name, until a slot comes up. "
                "There is no additional charge for the wait and we write to you each quarter."),
        (True, "He would have enjoyed that answer."),
        (False, "Most families say something similar."),
    ]),
    ("h.baran@example.com", 90, [
        (True, "Is there a problem with the 11th? It has been showing as unavailable all week."),
        (False, "The 11th is closed — the chapel floor is being relaid and both rooms are out. "
                "The 10th and the 12th are both open."),
        (True, "The 12th, then."),
        (False, "Your date has been set: Wednesday the 12th, 13:00, Chapel of Rest A. "
                "Please confirm in the app and the slot is held for you."),
        (True, "Confirmed."),
    ]),
    ("r.mazur@example.com", 260, [
        (True, "Please could you send the final invoice to the executor rather than to me. "
               "I am not the one paying and I would rather not keep receiving it."),
        (False, "Understood and changed. All billing now goes to the estate reference on the file; "
                "you will still receive the arrangements correspondence."),
        (True, "Perfect. Thank you."),
    ]),
    ("e.duda@example.com", 36, [
        (True, "The mortician preparation — will she look like herself? "
               "That is the only thing I actually care about."),
        (False, "That is the whole point of it. Krzysztof works from photographs, so bring two or "
                "three from the last few years rather than a formal portrait. He will not proceed "
                "until you have seen her and said yes."),
        (True, "I will bring the ones from the summer."),
        (False, "Those are the right kind. Come at eleven on Thursday; there is no need to hurry away."),
        (True, "Thank you. That is the first thing this week that has made me feel better."),
    ]),
    ("a.stepien@example.com", 8, [
        (True, "How long do I have to decide about the casket? I do not want to be rushed into it."),
        (False, "Until 48 hours before the service. Nothing about the casket is fixed until then, "
                "and the pine is the default if you decide nothing at all."),
    ]),
    ("n.krawczyk@example.com", 110, [
        (True, "We are eleven people and four of them cannot travel. Is the livestream private?"),
        (False, "It is a single link, unlisted, and it expires seven days after the service. "
                "Nobody without the link can find it and the recording is not kept unless you ask."),
        (True, "Please keep the recording."),
        (False, "Noted on the file. It will be sent to you as a download rather than a link."),
        (True, "Thank you."),
    ]),
    ("k.lewandowska@example.com", 400, [
        (True, "Following up on last year's arrangement for my mother — the headstone permission "
               "came through and I wanted to say thank you for chasing the cemetery office."),
        (False, "That is good to hear. The mason has the dimensions on file if you would like "
                "us to pass them on."),
        (True, "Please do."),
    ]),
    # A second segment for a family who has written before. `seed.py` merges
    # every segment for one email into that family's single conversation —
    # `conversations` is unique on (provider_id, client_id), so a family has one
    # thread with the home no matter how many times they come back.
    ("m.kowalczyk@example.com", 620, [
        (True, "This is about my mother, not my father — a separate arrangement, "
               "eighteen months ago. Do you still hold the file?"),
        (False, "We hold every file indefinitely. Hers is here, including the order of "
                "service and the plot deed reference."),
        (True, "Could you send the plot reference? We are placing him with her."),
        (False, "Section 12, row F, plot 41. There is room and the deed permits a second "
                "interment. I have written to the cemetery office to confirm the depth."),
        (True, "Thank you. That is what he wanted and I could not find the paperwork."),
        (False, "It was in the 2024 folder. I have posted you a copy as well."),
    ]),
    ("e.kaminska@example.com", 700, [
        (True, "One more question about the reservation, if you do not mind. "
               "What happens to it if I move away from Warsaw?"),
        (False, "It stays yours. A reservation is a deed, not a subscription — there is nothing "
                "further to pay and nothing to keep up. If you decide against it later, "
                "the cemetery office will buy it back at the current rate."),
        (True, "And if I die somewhere else entirely?"),
        (False, "Then we bring you back, if that is what the file says. It is roughly the cost of "
                "the mileage band and we have done it from as far as Lisbon."),
        (True, "Please put that in the file."),
        (False, "It is in the file."),
    ]),
    ("z.adamska@example.com", 260, [
        (True, "The invoice shows a line for out-of-hours collection. Nobody mentioned that."),
        (False, "It applies between 18:00 and 08:00 and it is €180. We collected at 02:40, "
                "so it is correctly charged — but it should have been said out loud at the time "
                "and it was not. I have taken it off."),
        (True, "You did not have to do that."),
        (False, "We quote in advance or we do not charge. Revised invoice attached."),
        (True, "Thank you. Noted, and appreciated."),
    ]),
    ("h.baran@example.com", 480, [
        (True, "Could I add the memorial tree after the service rather than before? "
               "My sister is not ready to talk about it yet."),
        (False, "You can add it at any point, including years later. The grove takes plantings "
                "twice a year, in April and October, and the plaque is cut to whatever text "
                "you send us at the time."),
        (True, "April, then. I will write to you in the new year."),
        (False, "I will put a reminder against the file for February so you do not have to "
                "remember it yourself."),
    ]),
]


# --- more of the dead -------------------------------------------------------
# A home this size buries more people in four months than anyone wants to write
# by hand, and the same name appearing on two funerals is the one detail that
# makes a demo read as fake. Past the hand-written entries above, `deceased()`
# draws a fresh name from these pools and dresses it in an earlier entry's
# circumstances — the prose stays real, the roll of the dead stays distinct.

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


def deceased(index: int) -> dict:
    """The `index`-th deceased, with a name nobody else in the seed carries.

    Below `len(DECEASED)` this is simply the hand-written entry. Above it, the
    name comes from the pools and everything else — the rite, the manner, the
    attire, the height the casket is cut to — is borrowed from an earlier entry,
    which keeps the detail plausible without writing a five-hundredth funeral.
    """
    if index < len(DECEASED):
        return dict(DECEASED[index])
    n = index - len(DECEASED)
    template = dict(DECEASED[n % len(DECEASED)])
    first = _EXTRA_FIRST[n % len(_EXTRA_FIRST)]
    last = _EXTRA_LAST[(n * 7 + n // len(_EXTRA_FIRST)) % len(_EXTRA_LAST)]
    template["full_name"] = f"{first} {last}"
    return template
