"""Ported three-vertical seed data (transcribed verbatim from
frontend/src/api/seed/{fleet,oneToOne,group}.ts). Pure data — the assembler in
seed.py turns each vertical into DB rows."""

# --- funeral vertical helpers ---------------------------------------------
# A funeral arrangement occupies a whole DAY, not a time-of-day slot: one venue,
# one family, one date. `seed_config._grid` takes the same branch for any
# service whose duration is >= 1440 minutes — a single 00:00 start per day —
# so the calendar reads as a date picker rather than a timetable.

_FUNERAL_DAY = 1440


def _funeral_grid() -> dict:
    """One bookable date per venue per day: a week back (so the owner's history
    is populated) and two months forward (so pre-need arrangements have room)."""
    return {
        "daysBack": 7,
        "daysForward": 60,
        "dayStep": 1,
        "startTimes": [{"hour": 0, "minute": 0}],
    }


def _funeral_service(
    name: str,
    description: str,
    price_minor_units: int,
    resources: list[dict],
    *,
    cancellation_cutoff_hours: int = 48,
) -> dict:
    """One entry in a funeral home's catalogue.

    Every arrangement is a full-day, single-unit booking: `minSlotsPerBooking`
    and `maxSlotsPerBooking` are both 1 because a family books one date, and the
    48-hour cutoff is the point past which the hearse, the celebrant and the
    registry entry are all committed and can no longer be released.
    """
    return {
        "name": name,
        "description": description,
        "slotDurationMinutes": _FUNERAL_DAY,
        "priceMinorUnits": price_minor_units,
        "cancellationCutoffHours": cancellation_cutoff_hours,
        "minSlotsPerBooking": 1,
        "maxSlotsPerBooking": 1,
        "grid": _funeral_grid(),
        "resources": resources,
    }


def _venue(name: str, description: str, attributes: list[dict]) -> dict:
    """A funeral home's bookable unit — a chapel, a hearse, a retort, a bay.
    Capacity is always 1: these are exclusive-use rooms and vehicles, and the
    engine's `unit_selection` model means the family picks which one."""
    return {"name": name, "description": description, "capacity": 1, "attributes": attributes}


DEFAULT_VERTICAL = "fleet"

VERTICALS = {
    "fleet": {
        "verticalId": "fleet",
        "bookingModel": "unit_selection",
        "currency": "EUR",
        "baseTz": "Europe/Warsaw",
        "categories": [
            {"id": "economy", "label": "Economy"},
            {"id": "suv", "label": "SUV"},
            {"id": "van", "label": "Van"},
            {"id": "electric", "label": "Electric"},
            {"id": "luxury", "label": "Luxury"},
        ],
        "providers": [
            {
                "name": "Vistula Auto",
                "tagline": "City rentals, no queues",
                "bio": "Family-run rental desk two minutes from Warsaw Central. Same-day pickup, transparent pricing, and a fleet kept under three years old.",
                "categoryId": "economy",
                "city": "Warsaw",
                "country": "Poland",
                "lat": 52.2297,
                "lng": 21.0122,
                "publicCode": "VISTULA-4471",
                "rating": 4.7,
                "reviewCount": 318,
                "links": [
                    {"label": "Website", "url": "https://example.com/vistula"},
                    {"label": "Terms", "url": "https://example.com/vistula/terms"},
                ],
            },
            {
                "name": "Nord Fleet",
                "tagline": "Coastal SUVs & 4x4s",
                "bio": "Rugged vehicles for the Tricity and beyond. Roof boxes and child seats included on request.",
                "categoryId": "suv",
                "city": "Gdańsk",
                "country": "Poland",
                "lat": 54.352,
                "lng": 18.6466,
                "publicCode": "NORD-2210",
                "rating": 4.5,
                "reviewCount": 142,
                "links": [],
            },
            {
                "name": "Kraków Renta",
                "tagline": "Budget cars, old-town pickup",
                "bio": "Economy hatchbacks collected steps from the Kazimierz district.",
                "categoryId": "economy",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0647,
                "lng": 19.945,
                "publicCode": "KRK-8890",
                "rating": 4.3,
                "reviewCount": 96,
                "links": [],
            },
            {
                "name": "Odra Motors",
                "tagline": "Vans & movers",
                "bio": "Cargo and passenger vans for house moves and crew transport.",
                "categoryId": "van",
                "city": "Wrocław",
                "country": "Poland",
                "lat": 51.1079,
                "lng": 17.0385,
                "publicCode": "ODRA-5560",
                "rating": 4.6,
                "reviewCount": 74,
                "links": [],
            },
            {
                "name": "Baltic EV",
                "tagline": "All-electric fleet",
                "bio": "Zero-emission rentals with free charging on the first day.",
                "categoryId": "electric",
                "city": "Gdańsk",
                "country": "Poland",
                "lat": 54.372,
                "lng": 18.638,
                "publicCode": "BALT-7788",
                "rating": 4.8,
                "reviewCount": 205,
                "links": [],
            },
            {
                "name": "Piast Cars",
                "tagline": "Executive & luxury",
                "bio": "Premium saloons with chauffeur option for business travel.",
                "categoryId": "luxury",
                "city": "Poznań",
                "country": "Poland",
                "lat": 52.4064,
                "lng": 16.9252,
                "publicCode": "PIAST-3301",
                "rating": 4.9,
                "reviewCount": 61,
                "links": [],
            },
            {
                "name": "Tatra Wheels",
                "tagline": "Mountain-ready SUVs",
                "bio": "Winter tyres as standard from October. Ski racks available.",
                "categoryId": "suv",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0619,
                "lng": 19.9368,
                "publicCode": "TATRA-6642",
                "rating": 4.4,
                "reviewCount": 88,
                "links": [],
            },
        ],
        "demoServices": [
            {
                "name": "Compact class",
                "description": "Nimble city cars — easy to park, light on fuel.",
                "slotDurationMinutes": 1440,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 14,
                "priceMinorUnits": 4200,
                "cancellationCutoffHours": 48,
                "grid": {"daysBack": 28, "daysForward": 56, "startTimes": [{"hour": 0, "minute": 0}]},
                "resources": [
                    {
                        "name": "Unit C-4471",
                        "description": "Volkswagen Polo",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Manual"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Petrol"},
                            {"label": "Doors", "value": "5"},
                            {"label": "Bags", "value": "2"},
                        ],
                    },
                    {
                        "name": "Unit C-4472",
                        "description": "Toyota Yaris",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Automatic"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Hybrid"},
                            {"label": "Doors", "value": "5"},
                            {"label": "Bags", "value": "2"},
                        ],
                    },
                    {
                        "name": "Unit C-4473",
                        "description": "Škoda Fabia",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Manual"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Diesel"},
                            {"label": "Doors", "value": "5"},
                            {"label": "Bags", "value": "3"},
                        ],
                    },
                    {
                        "name": "Unit C-4474",
                        "description": "Ford Fiesta",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Manual"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Petrol"},
                            {"label": "Doors", "value": "3"},
                            {"label": "Bags", "value": "2"},
                        ],
                    },
                    {
                        "name": "Unit C-4475",
                        "description": "Hyundai i20",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Automatic"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Petrol"},
                            {"label": "Doors", "value": "5"},
                            {"label": "Bags", "value": "2"},
                        ],
                    },
                ],
            },
            {
                "name": "SUV class",
                "description": "Higher ride, more boot space, all-weather grip.",
                "slotDurationMinutes": 1440,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 14,
                "priceMinorUnits": 7500,
                "cancellationCutoffHours": 48,
                "grid": {"daysBack": 28, "daysForward": 56, "startTimes": [{"hour": 0, "minute": 0}]},
                "resources": [
                    {
                        "name": "Unit S-3310",
                        "description": "Toyota RAV4",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Automatic"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Hybrid"},
                            {"label": "Drive", "value": "AWD"},
                            {"label": "Bags", "value": "4"},
                        ],
                    },
                    {
                        "name": "Unit S-3311",
                        "description": "Volkswagen Tiguan",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Automatic"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Diesel"},
                            {"label": "Drive", "value": "FWD"},
                            {"label": "Bags", "value": "4"},
                        ],
                    },
                    {
                        "name": "Unit S-3312",
                        "description": "Kia Sportage",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Manual"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Petrol"},
                            {"label": "Drive", "value": "FWD"},
                            {"label": "Bags", "value": "3"},
                        ],
                    },
                    {
                        "name": "Unit S-3313",
                        "description": "Mazda CX-5",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Transmission", "value": "Automatic"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Fuel", "value": "Petrol"},
                            {"label": "Drive", "value": "AWD"},
                            {"label": "Bags", "value": "4"},
                        ],
                    },
                ],
            },
            {
                "name": "Electric class",
                "description": "Zero-emission rentals with first-day charging included.",
                "slotDurationMinutes": 1440,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 14,
                "priceMinorUnits": 6400,
                "cancellationCutoffHours": 48,
                "grid": {"daysBack": 28, "daysForward": 56, "startTimes": [{"hour": 0, "minute": 0}]},
                "resources": [
                    {
                        "name": "Unit E-9001",
                        "description": "Tesla Model 3",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Range", "value": "491 km"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Drive", "value": "RWD"},
                            {"label": "Charge", "value": "CCS"},
                        ],
                    },
                    {
                        "name": "Unit E-9002",
                        "description": "Hyundai Ioniq 5",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Range", "value": "481 km"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Drive", "value": "AWD"},
                            {"label": "Charge", "value": "CCS"},
                        ],
                    },
                    {
                        "name": "Unit E-9003",
                        "description": "Renault Zoe",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Range", "value": "395 km"},
                            {"label": "Seats", "value": "5"},
                            {"label": "Drive", "value": "FWD"},
                            {"label": "Charge", "value": "Type 2"},
                        ],
                    },
                ],
            },
        ],
        "simpleService": {
            "name": "Standard class",
            "description": "A dependable mid-range car for everyday trips.",
            "slotDurationMinutes": 1440,
            "priceMinorUnits": 5200,
            "cancellationCutoffHours": 48,
            "minSlotsPerBooking": 1,
            "maxSlotsPerBooking": 14,
            "grid": {"daysBack": 7, "daysForward": 42, "startTimes": [{"hour": 0, "minute": 0}]},
            "resource": {
                "name": "Unit A-1",
                "description": "Opel Astra",
                "capacity": 1,
                "attributes": [
                    {"label": "Transmission", "value": "Manual"},
                    {"label": "Seats", "value": "5"},
                    {"label": "Fuel", "value": "Petrol"},
                    {"label": "Bags", "value": "3"},
                ],
            },
        },
    },
    "oneToOne": {
        "verticalId": "oneToOne",
        "bookingModel": "one_to_one",
        "currency": "EUR",
        "baseTz": "Europe/Warsaw",
        "categories": [
            {"id": "math", "label": "Maths & sciences"},
            {"id": "languages", "label": "Languages"},
            {"id": "music", "label": "Music"},
            {"id": "coding", "label": "Coding"},
            {"id": "exam", "label": "Exam prep"},
        ],
        "providers": [
            {
                "name": "Northline Tutoring",
                "tagline": "One-to-one, results-first",
                "bio": "A small studio of specialist tutors covering STEM and languages. Sessions are hourly, in person near the centre or online.",
                "categoryId": "math",
                "city": "Warsaw",
                "country": "Poland",
                "lat": 52.2297,
                "lng": 21.0122,
                "publicCode": "NORTH-1180",
                "rating": 4.9,
                "reviewCount": 214,
                "links": [{"label": "Website", "url": "https://example.com/northline"}],
            },
            {
                "name": "Verba Languages",
                "tagline": "Conversational fluency",
                "bio": "Native-speaker language coaching for adults and teens.",
                "categoryId": "languages",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0647,
                "lng": 19.945,
                "publicCode": "VERBA-3320",
                "rating": 4.7,
                "reviewCount": 158,
                "links": [],
            },
            {
                "name": "Sono Music School",
                "tagline": "Piano, guitar, voice",
                "bio": "Instrument lessons for beginners through grade eight.",
                "categoryId": "music",
                "city": "Gdańsk",
                "country": "Poland",
                "lat": 54.352,
                "lng": 18.6466,
                "publicCode": "SONO-7745",
                "rating": 4.8,
                "reviewCount": 121,
                "links": [],
            },
            {
                "name": "Codeworks Mentors",
                "tagline": "Learn to ship code",
                "bio": "Practical programming mentorship in Python, JavaScript and SQL.",
                "categoryId": "coding",
                "city": "Wrocław",
                "country": "Poland",
                "lat": 51.1079,
                "lng": 17.0385,
                "publicCode": "CODE-2091",
                "rating": 4.6,
                "reviewCount": 89,
                "links": [],
            },
            {
                "name": "Apex Exam Prep",
                "tagline": "SAT · IB · Matura",
                "bio": "Targeted revision and mock exams with detailed feedback.",
                "categoryId": "exam",
                "city": "Poznań",
                "country": "Poland",
                "lat": 52.4064,
                "lng": 16.9252,
                "publicCode": "APEX-6612",
                "rating": 4.8,
                "reviewCount": 143,
                "links": [],
            },
            {
                "name": "Helix STEM",
                "tagline": "Maths, physics, chemistry",
                "bio": "University-level tutors for demanding science coursework.",
                "categoryId": "math",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0619,
                "lng": 19.9368,
                "publicCode": "HELIX-4408",
                "rating": 4.5,
                "reviewCount": 67,
                "links": [],
            },
        ],
        "demoServices": [
            {
                "name": "Mathematics",
                "description": "Algebra, calculus and problem-solving with Ana.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 2,
                "priceMinorUnits": 6000,
                "cancellationCutoffHours": 24,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "weekdays": [1, 2, 3, 4, 5],
                    "startTimes": [
                        {"hour": 9, "minute": 0},
                        {"hour": 10, "minute": 0},
                        {"hour": 11, "minute": 0},
                        {"hour": 13, "minute": 0},
                        {"hour": 14, "minute": 0},
                        {"hour": 15, "minute": 0},
                        {"hour": 16, "minute": 0},
                    ],
                },
                "resources": [
                    {
                        "name": "Ana Ruiz",
                        "description": "PhD in applied mathematics, 8 years tutoring.",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Levels", "value": "GCSE → University"},
                            {"label": "Format", "value": "In person or online"},
                            {"label": "Languages", "value": "English, Polish"},
                        ],
                    },
                ],
            },
            {
                "name": "Physics",
                "description": "Mechanics, electromagnetism and lab report coaching.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 2,
                "priceMinorUnits": 6500,
                "cancellationCutoffHours": 24,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "weekdays": [1, 2, 3, 4, 5],
                    "startTimes": [
                        {"hour": 9, "minute": 0},
                        {"hour": 10, "minute": 0},
                        {"hour": 11, "minute": 0},
                        {"hour": 13, "minute": 0},
                        {"hour": 14, "minute": 0},
                        {"hour": 15, "minute": 0},
                        {"hour": 16, "minute": 0},
                    ],
                },
                "resources": [
                    {
                        "name": "Jon Vekic",
                        "description": "MSc physics, examiner for the national board.",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Levels", "value": "A-level → University"},
                            {"label": "Format", "value": "Online"},
                            {"label": "Languages", "value": "English"},
                        ],
                    },
                ],
            },
            {
                "name": "Exam prep",
                "description": "Structured revision with weekly mock papers.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 2,
                "priceMinorUnits": 7000,
                "cancellationCutoffHours": 24,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "weekdays": [1, 2, 3, 4, 5],
                    "startTimes": [
                        {"hour": 9, "minute": 0},
                        {"hour": 10, "minute": 0},
                        {"hour": 11, "minute": 0},
                        {"hour": 13, "minute": 0},
                        {"hour": 14, "minute": 0},
                        {"hour": 15, "minute": 0},
                        {"hour": 16, "minute": 0},
                    ],
                },
                "resources": [
                    {
                        "name": "Priya Nair",
                        "description": "Specialist in Matura and IB mathematics.",
                        "capacity": 1,
                        "attributes": [
                            {"label": "Focus", "value": "Matura, IB"},
                            {"label": "Format", "value": "In person or online"},
                            {"label": "Languages", "value": "English, Polish"},
                        ],
                    },
                ],
            },
        ],
        "simpleService": {
            "name": "Introductory lesson",
            "description": "A first hour to assess level and set a plan.",
            "slotDurationMinutes": 60,
            "priceMinorUnits": 5000,
            "cancellationCutoffHours": 24,
            "minSlotsPerBooking": 1,
            "maxSlotsPerBooking": 1,
            "grid": {
                "daysBack": 7,
                "daysForward": 42,
                "weekdays": [1, 2, 3, 4, 5],
                "startTimes": [
                    {"hour": 9, "minute": 0},
                    {"hour": 10, "minute": 0},
                    {"hour": 11, "minute": 0},
                    {"hour": 13, "minute": 0},
                    {"hour": 14, "minute": 0},
                    {"hour": 15, "minute": 0},
                    {"hour": 16, "minute": 0},
                ],
            },
            "resource": {
                "name": "Lead tutor",
                "description": "Assigned on booking.",
                "capacity": 1,
                "attributes": [
                    {"label": "Format", "value": "In person or online"},
                    {"label": "Duration", "value": "60 min"},
                ],
            },
        },
    },
    "group": {
        "verticalId": "group",
        "bookingModel": "shared_capacity",
        "currency": "EUR",
        "baseTz": "Europe/Warsaw",
        "categories": [
            {"id": "vinyasa", "label": "Vinyasa"},
            {"id": "hatha", "label": "Hatha"},
            {"id": "pilates", "label": "Pilates"},
            {"id": "meditation", "label": "Meditation"},
            {"id": "strength", "label": "Strength"},
        ],
        "providers": [
            {
                "name": "Lotus Studio",
                "tagline": "Breathe, move, reset",
                "bio": "A light-filled studio in the old town offering daily classes for every level. Mats and props provided; walk-ins welcome when space allows.",
                "categoryId": "vinyasa",
                "city": "Warsaw",
                "country": "Poland",
                "lat": 52.2297,
                "lng": 21.0122,
                "publicCode": "LOTUS-5150",
                "rating": 4.9,
                "reviewCount": 402,
                "links": [
                    {"label": "Website", "url": "https://example.com/lotus"},
                    {"label": "Timetable", "url": "https://example.com/lotus/timetable"},
                ],
            },
            {
                "name": "Riverside Yoga",
                "tagline": "Hatha by the Vistula",
                "bio": "Slow, alignment-focused classes suitable for beginners.",
                "categoryId": "hatha",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0647,
                "lng": 19.945,
                "publicCode": "RIVER-3380",
                "rating": 4.6,
                "reviewCount": 176,
                "links": [],
            },
            {
                "name": "Core Pilates Lab",
                "tagline": "Reformer & mat",
                "bio": "Small-group Pilates focused on strength and posture.",
                "categoryId": "pilates",
                "city": "Gdańsk",
                "country": "Poland",
                "lat": 54.352,
                "lng": 18.6466,
                "publicCode": "CORE-9925",
                "rating": 4.7,
                "reviewCount": 133,
                "links": [],
            },
            {
                "name": "Still Point",
                "tagline": "Guided meditation",
                "bio": "Drop-in mindfulness and breathwork sessions.",
                "categoryId": "meditation",
                "city": "Wrocław",
                "country": "Poland",
                "lat": 51.1079,
                "lng": 17.0385,
                "publicCode": "STILL-2044",
                "rating": 4.8,
                "reviewCount": 98,
                "links": [],
            },
            {
                "name": "Forge Strength",
                "tagline": "Small-group conditioning",
                "bio": "Coached strength circuits, capped at twelve per session.",
                "categoryId": "strength",
                "city": "Poznań",
                "country": "Poland",
                "lat": 52.4064,
                "lng": 16.9252,
                "publicCode": "FORGE-6710",
                "rating": 4.5,
                "reviewCount": 71,
                "links": [],
            },
            {
                "name": "Sunrise Vinyasa",
                "tagline": "Morning flows",
                "bio": "Energetic dawn classes to start the day.",
                "categoryId": "vinyasa",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0619,
                "lng": 19.9368,
                "publicCode": "SUNRISE-4416",
                "rating": 4.7,
                "reviewCount": 154,
                "links": [],
            },
        ],
        "demoServices": [
            {
                "name": "Vinyasa Flow",
                "description": "A dynamic, breath-led flow for all levels.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 1,
                "priceMinorUnits": 1800,
                "cancellationCutoffHours": 12,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "startTimes": [
                        {"hour": 7, "minute": 0},
                        {"hour": 9, "minute": 0},
                        {"hour": 12, "minute": 0},
                        {"hour": 17, "minute": 0},
                        {"hour": 18, "minute": 30},
                    ],
                },
                "resources": [
                    {
                        "name": "Studio A",
                        "description": "Main room, sprung floor, 12 mats.",
                        "capacity": 12,
                        "attributes": [
                            {"label": "Capacity", "value": "12 spots"},
                            {"label": "Level", "value": "All levels"},
                            {"label": "Heated", "value": "No"},
                        ],
                    },
                ],
            },
            {
                "name": "Hatha Basics",
                "description": "Slower, alignment-focused practice for beginners.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 1,
                "priceMinorUnits": 1600,
                "cancellationCutoffHours": 12,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "startTimes": [
                        {"hour": 7, "minute": 0},
                        {"hour": 9, "minute": 0},
                        {"hour": 12, "minute": 0},
                    ],
                },
                "resources": [
                    {
                        "name": "Studio B",
                        "description": "Quiet room, 10 mats.",
                        "capacity": 10,
                        "attributes": [
                            {"label": "Capacity", "value": "10 spots"},
                            {"label": "Level", "value": "Beginner"},
                            {"label": "Heated", "value": "No"},
                        ],
                    },
                ],
            },
            {
                "name": "Candlelight Meditation",
                "description": "A restorative evening wind-down.",
                "slotDurationMinutes": 60,
                "minSlotsPerBooking": 1,
                "maxSlotsPerBooking": 1,
                "priceMinorUnits": 1400,
                "cancellationCutoffHours": 12,
                "grid": {
                    "daysBack": 28,
                    "daysForward": 56,
                    "startTimes": [{"hour": 20, "minute": 0}],
                },
                "resources": [
                    {
                        "name": "Studio A",
                        "description": "Main room, dimmed, bolsters provided.",
                        "capacity": 16,
                        "attributes": [
                            {"label": "Capacity", "value": "16 spots"},
                            {"label": "Level", "value": "All levels"},
                            {"label": "Props", "value": "Provided"},
                        ],
                    },
                ],
            },
        ],
        "simpleService": {
            "name": "Open class",
            "description": "A drop-in group session for every level.",
            "slotDurationMinutes": 60,
            "priceMinorUnits": 1500,
            "cancellationCutoffHours": 12,
            "minSlotsPerBooking": 1,
            "maxSlotsPerBooking": 1,
            "grid": {
                "daysBack": 7,
                "daysForward": 42,
                "startTimes": [
                    {"hour": 7, "minute": 0},
                    {"hour": 9, "minute": 0},
                    {"hour": 12, "minute": 0},
                ],
            },
            "resource": {
                "name": "Main room",
                "description": "Shared studio space.",
                "capacity": 12,
                "attributes": [
                    {"label": "Capacity", "value": "12 spots"},
                    {"label": "Level", "value": "All levels"},
                ],
            },
        },
    },
    # ------------------------------------------------------------------
    # Funeral homes. The arrangement is the unit: one family, one venue, one
    # date. Booking model is `unit_selection` because the family chooses WHICH
    # chapel / hearse / retort, and capacity is 1 everywhere — nothing here is
    # shared. Every duration is a whole day (1440), which puts `seed_config`'s
    # `_grid` on its day-lattice branch and turns the calendar into a date
    # picker. Prices are EUR minor units and escalate from a direct committal
    # to committal in low Earth orbit.
    # ------------------------------------------------------------------
    "funeral": {
        "verticalId": "funeral",
        "bookingModel": "unit_selection",
        "currency": "EUR",
        "baseTz": "Europe/Warsaw",
        "categories": [
            {"id": "burial", "label": "Burial"},
            {"id": "cremation", "label": "Cremation"},
            {"id": "memorial", "label": "Memorial"},
            {"id": "aftercare", "label": "Aftercare"},
            {"id": "eternal", "label": "Indefinite Arrangements"},
        ],
        "providers": [
            # Provider 0 is the demo home: the owner login owns it and it
            # carries the entire catalogue below, so the business dashboard,
            # the Requests tab and the analytics all have data.
            {
                "name": "Wieczny Spokój",
                "tagline": "Warsaw's funeral directors since 1889 — answered in person, at any hour",
                "bio": (
                "Four generations of funeral directors on ulica Powązkowska, licensed in "
                "1889 and not closed for a day since. Two chapels of rest, a preparation "
                "suite and a full fleet. If you are calling because someone has died in "
                "the last hour, say so and we will put you through to whoever is on call."
            ),
                "categoryId": "burial",
                "city": "Warsaw",
                "country": "Poland",
                "lat": 52.2297,
                "lng": 21.0122,
                "publicCode": "WIECZNY-1889",
                "rating": 4.9,
                "reviewCount": 412,
                "links": [
                    {"label": "Website", "url": "https://example.com/wieczny-spokoj"},
                    {"label": "Full price list (PDF)", "url": "https://example.com/wieczny-spokoj/prices"},
                    {"label": "24-hour line", "url": "https://example.com/wieczny-spokoj/contact"},
                    {"label": "What to do in the first 24 hours", "url": "https://example.com/wieczny-spokoj/first-day"},
                    {"label": "Registry and paperwork we file for you", "url": "https://example.com/wieczny-spokoj/registry"},
                    {"label": "Indefinite arrangements — escrow terms", "url": "https://example.com/wieczny-spokoj/escrow"},
                ],
            },
            {
                "name": "Kaplica Lipowa",
                "tagline": "Cremation, arranged in one visit",
                "bio": "A single-site crematorium on the southern edge of Kraków. Two retorts, an "
                       "unattended committal option, and ashes returned within fourteen days.",
                "categoryId": "cremation",
                "city": "Kraków",
                "country": "Poland",
                "lat": 50.0647,
                "lng": 19.945,
                "publicCode": "LIPOWA-3320",
                "rating": 4.7,
                "reviewCount": 198,
                "links": [
                    {"label": "Website", "url": "https://example.com/kaplica-lipowa"},
                    {"label": "Collection of ashes", "url": "https://example.com/kaplica-lipowa/ashes"},
                ],
                "service": _funeral_service(
                    "Cremation",
                    "Committal to the retort, with or without a preceding service. Ashes are returned "
                    "in a sealed urn to the person named on the application, in person, by appointment.",
                    165000,
                    [
                        _venue(
                            "Retort 1",
                            "Primary chamber. Filtration certified to the 2019 emissions standard, and "
                            "the only one of the two with a gallery, so a witnessed committal is booked here.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Chamber temperature", "value": "870 °C"},
                                {"label": "Cycle", "value": "90 minutes"},
                                {"label": "Witnessed committal", "value": "Permitted, up to 6 mourners"},
                            ],
                        ),
                        _venue(
                            "Retort 2",
                            "Secondary chamber, worked on the afternoon shift. No gallery and no "
                            "adjoining room, so committals here are unattended by arrangement.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Chamber temperature", "value": "870 °C"},
                                {"label": "Cycle", "value": "90 minutes"},
                                {"label": "Witnessed committal", "value": "Not available"},
                            ],
                        ),
                        _venue(
                            "Chapel of Rest",
                            "The house chapel, used for the short service that precedes a committal. "
                            "Twenty-four seats, a lectern and a recorded-music system.",
                            [
                                {"label": "Capacity", "value": "24 mourners"},
                                {"label": "Service length", "value": "25 minutes"},
                                {"label": "Music", "value": "Recorded, any format"},
                                {"label": "Committal follows", "value": "Same day"},
                            ],
                        ),
                    ],
                ),
            },
            {
                "name": "Dom Żałoby Bursztyn",
                "tagline": "Memorial services on the Baltic coast",
                "bio": "A quiet house of mourning ten minutes from the Gdańsk waterfront, built around "
                       "a single north-lit chapel. We specialise in gatherings rather than processions: "
                       "seated services, readings, and scattering at sea by arrangement with the harbour office.",
                "categoryId": "memorial",
                "city": "Gdańsk",
                "country": "Poland",
                "lat": 54.352,
                "lng": 18.6466,
                "publicCode": "BURSZTYN-7714",
                "rating": 4.8,
                "reviewCount": 143,
                "links": [
                    {"label": "Website", "url": "https://example.com/bursztyn"},
                    {"label": "Scattering at sea — harbour permits", "url": "https://example.com/bursztyn/at-sea"},
                ],
                "service": _funeral_service(
                    "Memorial Gathering",
                    "A seated service without a committal, held on a date of the family's choosing — "
                    "weeks or years after the death. Catering, an order of service and a PA for readings "
                    "are included; the chapel seats forty.",
                    78000,
                    [
                        _venue(
                            "Chapel of Rest B",
                            "North-lit chapel, forty seats, lectern and induction loop. The window looks "
                            "onto the water, which is the reason most families choose us.",
                            [
                                {"label": "Capacity", "value": "40 mourners"},
                                {"label": "Lectern time", "value": "18 minutes"},
                                {"label": "Induction loop", "value": "Fitted"},
                                {"label": "Catering", "value": "Included"},
                            ],
                        ),
                    ],
                ),
            },
            {
                "name": "Odra Pamięć",
                "tagline": "Arrange now, at today's price",
                "bio": "A pre-need practice in Wrocław. We take the arrangement while the person is "
                       "still here to make it, fix the price in escrow, and hold the file until it is needed. "
                       "Most of our clients never meet us twice.",
                "categoryId": "aftercare",
                "city": "Wrocław",
                "country": "Poland",
                "lat": 51.1079,
                "lng": 17.0385,
                "publicCode": "ODRA-2260",
                "rating": 4.6,
                "reviewCount": 87,
                "links": [
                    {"label": "Website", "url": "https://example.com/odra-pamiec"},
                    {"label": "Escrow terms", "url": "https://example.com/odra-pamiec/escrow"},
                ],
                "service": _funeral_service(
                    "Pre-Need Arrangement",
                    "A two-hour consultation at which the arrangement is specified in full and the price "
                    "is fixed in escrow. The file is then held indefinitely at no further charge. "
                    "Nothing is provided on the day of the appointment except tea and a folder.",
                    45000,
                    [
                        _venue(
                            "Preparation Suite",
                            "Private consultation room at the front of the house. Documents are "
                            "witnessed and notarised at the table, so nothing has to be posted.",
                            [
                                {"label": "Capacity", "value": "1 family"},
                                {"label": "Consultation", "value": "2 hours"},
                                {"label": "Price hold", "value": "Indefinite, escrowed"},
                                {"label": "Notary", "value": "On site"},
                            ],
                        ),
                    ],
                ),
            },
            {
                "name": "Cichy Dom",
                "tagline": "No service, no procession, no fuss",
                "bio": "Poznań's direct-disposal specialist. One price, no upsell, no chapel. "
                       "We collect, we complete the paperwork, we return the ashes. "
                       "Families who want more than that are better served elsewhere, and we will say so.",
                "categoryId": "burial",
                "city": "Poznań",
                "country": "Poland",
                "lat": 52.4064,
                "lng": 16.9252,
                "publicCode": "CICHY-5051",
                "rating": 4.5,
                "reviewCount": 64,
                "links": [
                    {"label": "One-page price list", "url": "https://example.com/cichy-dom/price"},
                ],
                "service": _funeral_service(
                    "Direct Committal",
                    "Collection, documentation and committal with no attending mourners and no ceremony. "
                    "The family is notified by telephone once it is complete. This is the least expensive "
                    "arrangement we offer and we do not recommend it against the family's wishes.",
                    90000,
                    [
                        _venue(
                            "Hearse — Mercedes S-Class",
                            "Unmarked private ambulance for collection. No cortège, no following cars, "
                            "and nothing on the vehicle that identifies the trade.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Mourners", "value": "None"},
                                {"label": "Collection radius", "value": "80 km"},
                                {"label": "Notice required", "value": "48 hours"},
                            ],
                        ),
                        _venue(
                            "Preparation Suite",
                            "Where the deceased is held, and the paperwork completed, between collection "
                            "and committal. The family does not attend and is not asked to.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Refrigeration", "value": "4 °C"},
                                {"label": "Holding period", "value": "Up to 5 days"},
                                {"label": "Viewing", "value": "Not offered"},
                            ],
                        ),
                    ],
                ),
            },
            # The specialist for the indefinite tier. Small review count, perfect
            # rating: not many families have needed them yet.
            {
                "name": "Ostatnia Granica",
                "tagline": "Arrangements measured in centuries",
                "bio": "A licensed cryonics and orbital-committal facility outside Łódź, operating under "
                       "the same registry obligations as any funeral home. We take no position on whether "
                       "revival will one day be possible. We take a position on maintaining −196 °C in the "
                       "meantime, which is a matter of engineering and standing orders rather than belief.",
                "categoryId": "eternal",
                "city": "Łódź",
                "country": "Poland",
                "lat": 51.7592,
                "lng": 19.4560,
                "publicCode": "GRANICA-0001",
                "rating": 5.0,
                "reviewCount": 12,
                "links": [
                    {"label": "Website", "url": "https://example.com/ostatnia-granica"},
                    {"label": "Escrow terms", "url": "https://example.com/ostatnia-granica/escrow"},
                    {"label": "Standing orders and alarm log", "url": "https://example.com/ostatnia-granica/standing-orders"},
                ],
                "service": _funeral_service(
                    "Cryogenic Suspension",
                    "Perfusion, vitrification and transfer to long-term storage at −196 °C. The bay is "
                    "held under a standing order funded from escrow and reviewed annually. "
                    "No claim is made, or implied, regarding eventual revival.",
                    4800000,
                    [
                        _venue(
                            "Cryo-Vault Bay 3",
                            "Dewar bay under continuous nitrogen top-up and independent alarm "
                            "monitoring, on the vault's south wall.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Cooling", "value": "−196 °C"},
                                {"label": "Top-up interval", "value": "11 days"},
                                {"label": "Funding", "value": "Escrow, reviewed annually"},
                                {"label": "Minimum term", "value": "100 years"},
                            ],
                        ),
                        _venue(
                            "Preparation Suite",
                            "The perfusion theatre. Cannulation and cryoprotectant exchange happen here "
                            "immediately on arrival; the transfer to the vault follows within the hour.",
                            [
                                {"label": "Capacity", "value": "1 occupant"},
                                {"label": "Cooling rate", "value": "1 °C per minute"},
                                {"label": "Standby team", "value": "3, on call"},
                                {"label": "Window from death", "value": "Under 6 hours"},
                            ],
                        ),
                    ],
                    cancellation_cutoff_hours=168,
                ),
            },
        ],
        # The demo home's full catalogue. Index 0 is the primary service and is
        # manual-approve, so its requests wait in the owner's Requests tab.
        "demoServices": [
            _funeral_service(
                "Traditional Funeral Service",
                "A full service in the chapel of rest followed by a cortège to the graveside or the "
                "crematorium. The fee covers the celebrant, six bearers, an order of service printed to "
                "your own text, the chapel for the morning or the afternoon, and every registry filing "
                "the death requires. A director walks in front of the hearse to the corner of the street, "
                "which is the last thing most families remember of the day.",
                285000,
                [
                    _venue(
                        "Chapel of Rest A",
                        "The principal chapel: sixty seats, a two-manual organ, and a private family "
                        "room to the rear with its own entrance from the courtyard.",
                        [
                            {"label": "Capacity", "value": "60 mourners"},
                            {"label": "Organ", "value": "Two-manual, tuned quarterly"},
                            {"label": "Family room", "value": "Private, adjoining"},
                            {"label": "Service length", "value": "45 minutes"},
                        ],
                    ),
                    _venue(
                        "Chapel of Rest B",
                        "The smaller chapel, forty seats, chosen by families who would rather a full "
                        "room than an empty one. Induction loop and graveside PA included.",
                        [
                            {"label": "Capacity", "value": "40 mourners"},
                            {"label": "Induction loop", "value": "Fitted"},
                            {"label": "Overflow", "value": "Relayed to the foyer"},
                            {"label": "Service length", "value": "45 minutes"},
                        ],
                    ),
                    _venue(
                        "Hearse — Mercedes S-Class",
                        "The standard cortège vehicle, kept in the yard and washed the night before. "
                        "Up to two following limousines travel with it at no supplement.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Following cars", "value": "Up to 2"},
                            {"label": "Cortège speed", "value": "Walking pace to the corner"},
                            {"label": "Livery", "value": "Black, unmarked"},
                        ],
                    ),
                    _venue(
                        "Hearse — Rolls-Royce Phantom",
                        "Coachbuilt 1972 hearse for a full state-style cortège, with four following "
                        "cars. It is slow, it is loud on cobbles, and it is worth it.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Following cars", "value": "Up to 4"},
                            {"label": "Coachwork", "value": "Bespoke, 1972"},
                            {"label": "Supplement", "value": "Included in this arrangement"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Cremation",
                "Committal to the retort, with or without a preceding chapel service. Ashes are returned "
                "in a sealed urn within fourteen days, in person, to the applicant named on the form and "
                "to nobody else. We will scatter them for you at the garden of remembrance if you would "
                "prefer not to be the one holding the urn.",
                165000,
                [
                    _venue(
                        "Retort 1",
                        "The primary chamber, with a viewing gallery above it for families who wish to "
                        "see the charging. Filtration certified to the 2019 emissions standard.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Chamber temperature", "value": "870 °C"},
                            {"label": "Cycle", "value": "90 minutes"},
                            {"label": "Witnessed committal", "value": "Permitted, up to 6 mourners"},
                        ],
                    ),
                    _venue(
                        "Retort 2",
                        "The secondary chamber, worked on the afternoon shift. No gallery, so committals "
                        "here are unattended and priced identically.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Chamber temperature", "value": "870 °C"},
                            {"label": "Cycle", "value": "90 minutes"},
                            {"label": "Witnessed committal", "value": "Not available"},
                        ],
                    ),
                    _venue(
                        "Chapel of Rest B",
                        "The forty-seat chapel, for the short service that precedes the committal. The "
                        "curtain closes at the end of the last reading, not before.",
                        [
                            {"label": "Capacity", "value": "40 mourners"},
                            {"label": "Service length", "value": "30 minutes"},
                            {"label": "Music", "value": "Organ or recorded"},
                            {"label": "Committal follows", "value": "Same day"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Burial",
                "Interment at the cemetery of your choosing. We prepare the grave, provide six bearers, "
                "and deal with the cemetery office over depth, headstone permissions and the plot deed — "
                "three conversations that are difficult to have in the week after a death. Powązki, "
                "Bródno and Północny are all within our standard route.",
                195000,
                [
                    _venue(
                        "Chapel of Rest B",
                        "The forty-seat chapel, used for the service that precedes the interment. The "
                        "cortège forms in the courtyard directly outside it.",
                        [
                            {"label": "Capacity", "value": "40 mourners"},
                            {"label": "Graveside PA", "value": "Included"},
                            {"label": "Bearers", "value": "6"},
                            {"label": "Service length", "value": "35 minutes"},
                        ],
                    ),
                    _venue(
                        "Hearse — Mercedes S-Class",
                        "The standard cortège vehicle for a burial, with two following limousines and a "
                        "director walking ahead of it as far as the cemetery gate.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Following cars", "value": "Up to 2"},
                            {"label": "Cemetery access", "value": "Powązki, Bródno, Północny"},
                            {"label": "Livery", "value": "Black, unmarked"},
                        ],
                    ),
                    _venue(
                        "Hearse — Horse-Drawn",
                        "A two-horse glass carriage. The route is walked and surveyed the week before, "
                        "and the tram wires on Okopowa mean it cannot go everywhere.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Horses", "value": "2, black, plumed"},
                            {"label": "Maximum route", "value": "3 km"},
                            {"label": "Weather limit", "value": "Cancelled above force 6"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Memorial Gathering",
                "A seated service with no committal, held on any date the family chooses — including "
                "months or years after the death, or after a cremation elsewhere. Readings, music and "
                "catering for forty are included. Families who were abroad when it happened, or who were "
                "not ready in the first week, book this most often, and there is no time limit on it.",
                78000,
                [
                    _venue(
                        "Chapel of Rest A",
                        "The principal chapel laid out for a gathering rather than a service: seating in "
                        "a horseshoe, the catering table at the back, the organ closed.",
                        [
                            {"label": "Capacity", "value": "60 mourners"},
                            {"label": "Catering", "value": "Included, 40 covers"},
                            {"label": "Lectern time", "value": "18 minutes"},
                            {"label": "Committal", "value": "None"},
                        ],
                    ),
                    _venue(
                        "Chapel of Rest B",
                        "The smaller chapel, for gatherings of twenty or fewer, where a large room "
                        "would make the attendance feel thin.",
                        [
                            {"label": "Capacity", "value": "40 mourners"},
                            {"label": "Catering", "value": "Included, 20 covers"},
                            {"label": "Induction loop", "value": "Fitted"},
                            {"label": "Committal", "value": "None"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Direct Committal",
                "Collection, documentation and committal with no mourners present and no ceremony of any "
                "kind. The family is telephoned once it is complete, usually the same afternoon. This is "
                "our least expensive arrangement and it is a legitimate choice, not a lesser one — but we "
                "will say plainly if we think a family is choosing it under pressure.",
                90000,
                [
                    _venue(
                        "Hearse — Mercedes S-Class",
                        "The unmarked collection vehicle. No cortège, no following cars, and nothing on "
                        "the car that identifies the trade to the neighbours.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Mourners", "value": "None"},
                            {"label": "Collection radius", "value": "80 km"},
                            {"label": "Notification", "value": "By telephone, same day"},
                        ],
                    ),
                    _venue(
                        "Retort 2",
                        "The chamber without a gallery, which is where an unattended committal goes. "
                        "The ashes are held for collection or posted by registered courier.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Chamber temperature", "value": "870 °C"},
                            {"label": "Attendance", "value": "None permitted"},
                            {"label": "Ashes returned", "value": "Within 14 days"},
                        ],
                    ),
                    _venue(
                        "Preparation Suite",
                        "Where the deceased is held and the registry paperwork completed between "
                        "collection and committal. No viewing is offered on this arrangement.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Refrigeration", "value": "4 °C"},
                            {"label": "Holding period", "value": "Up to 5 days"},
                            {"label": "Viewing", "value": "Not offered"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Pre-Need Arrangement",
                "A consultation at which a person specifies their own funeral in full — chapel, vehicle, "
                "readings, the lot — and fixes the price in escrow at today's figure. The file is then "
                "held indefinitely at no further charge and may be amended as often as they like. "
                "Nothing at all is delivered on the day of the appointment except tea and a folder.",
                45000,
                [
                    _venue(
                        "Preparation Suite",
                        "The private consultation room at the front of the house. Documents are "
                        "witnessed and notarised at the table, so nothing needs to be posted afterwards.",
                        [
                            {"label": "Capacity", "value": "1 family"},
                            {"label": "Consultation", "value": "2 hours"},
                            {"label": "Price hold", "value": "Indefinite, escrowed"},
                            {"label": "Amendments", "value": "Unlimited, free"},
                        ],
                    ),
                    _venue(
                        "Chapel of Rest A",
                        "Booked for an hour so that the person arranging can sit in the room they are "
                        "choosing, hear the organ, and change their mind if they want to.",
                        [
                            {"label": "Capacity", "value": "1 family"},
                            {"label": "Viewing", "value": "1 hour, by appointment"},
                            {"label": "Organ", "value": "Demonstrated on request"},
                            {"label": "Obligation", "value": "None"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Cryogenic Suspension",
                "Perfusion, vitrification and transfer to long-term storage at −196 °C, arranged with our "
                "partner facility outside Łódź and administered from here. Cooling is funded from an "
                "escrow account under a standing order reviewed each January, and the vault is alarmed "
                "independently of the building. We make no claim, and permit none to be made on our "
                "behalf, regarding eventual revival.",
                4800000,
                [
                    _venue(
                        "Cryo-Vault Bay 3",
                        "A dewar bay on the vault's south wall under continuous nitrogen top-up with "
                        "independent alarm monitoring routed to two directors' telephones.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Cooling", "value": "−196 °C"},
                            {"label": "Top-up interval", "value": "11 days"},
                            {"label": "Minimum term", "value": "100 years"},
                            {"label": "Revival", "value": "Not warranted"},
                        ],
                    ),
                    _venue(
                        "Preparation Suite",
                        "Used as the perfusion theatre. Cannulation and cryoprotectant exchange are "
                        "carried out here on arrival and the transfer follows within the hour.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Cooling rate", "value": "1 °C per minute"},
                            {"label": "Standby team", "value": "3, on call"},
                            {"label": "Window from death", "value": "Under 6 hours"},
                        ],
                    ),
                ],
                cancellation_cutoff_hours=168,
            ),
            _funeral_service(
                "Orbital Committal",
                "Vitrification followed by launch to a stable low Earth orbit at 620 km, where the "
                "payload remains for approximately four centuries before atmospheric re-entry. The launch "
                "window is confirmed six weeks in advance and the family is invited to the pad; a scrub "
                "moves the date at no charge and has happened twice. Tracking data is sent to the family "
                "annually for as long as the object is catalogued.",
                6500000,
                [
                    _venue(
                        "Launch Pad 4",
                        "The dedicated small-payload pad. One committal per window, with the family "
                        "observing from the three-kilometre line and a director beside them.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Orbit", "value": "620 km, sun-synchronous"},
                            {"label": "Expected duration", "value": "≈400 years"},
                            {"label": "Family viewing", "value": "3 km observation line"},
                            {"label": "Scrub policy", "value": "Rescheduled at no charge"},
                        ],
                    ),
                    _venue(
                        "Preparation Suite",
                        "Where the payload is prepared, sealed and weighed before it is trucked to the "
                        "range. The family may attend the sealing and most do.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Payload mass", "value": "Up to 4.2 kg"},
                            {"label": "Sealing", "value": "Witnessed, family may attend"},
                            {"label": "Transfer to range", "value": "6 weeks before window"},
                        ],
                    ),
                ],
                cancellation_cutoff_hours=168,
            ),
            _funeral_service(
                "Nocturnal Aftercare Programme",
                "An after-hours arrangement for light-sensitive families. The chapel is opened after "
                "sunset and closed before first light, the west windows are shuttered, and the cortège "
                "route is planned to avoid the eastern approach at dawn. Staff are briefed not to ask "
                "why, and the reason is not recorded on the file. Mirrors in the foyer are covered as a "
                "matter of course, which several families have told us they appreciated.",
                132000,
                [
                    _venue(
                        "Chapel of Rest B",
                        "The forty-seat chapel, shuttered on its west aspect and opened from sunset to "
                        "04:30 for services too large for the lower hall.",
                        [
                            {"label": "Capacity", "value": "40 mourners"},
                            {"label": "Opening hours", "value": "Sunset to 04:30"},
                            {"label": "Glazing", "value": "Shuttered, west aspect"},
                            {"label": "Lighting", "value": "Candle only"},
                            {"label": "Reason recorded", "value": "No"},
                        ],
                    ),
                    _venue(
                        "Hearse — Mercedes S-Class",
                        "Fitted with laminated privacy glazing for this programme and dispatched only "
                        "between dusk and 04:00. The route avoids the eastern approach.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Glazing", "value": "Laminated, UV-opaque"},
                            {"label": "Dispatch window", "value": "Dusk to 04:00"},
                            {"label": "Route", "value": "Surveyed to avoid dawn eastward"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Discreet Arrangement",
                "For a death that the family would rather not explain. We do not ask how it happened and "
                "we do not speculate on the file. Collection is unmarked and out of hours, the register "
                "entry carries the minimum detail the law requires and not one word more, and all "
                "correspondence goes by sealed post to an address of your choosing. Where the law "
                "obliges us to notify someone, we will tell you before we do it.",
                340000,
                [
                    _venue(
                        "Preparation Suite",
                        "Reached by the side entrance from the yard. No visitor log is kept for this "
                        "room and it is outside the building's camera coverage.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Collection", "value": "Unmarked, out of hours"},
                            {"label": "Visitor log", "value": "Not kept"},
                            {"label": "Correspondence", "value": "Sealed post"},
                            {"label": "Questions asked", "value": "None"},
                        ],
                    ),
                    _venue(
                        "Hearse — Mercedes S-Class",
                        "Plated to a leasing company rather than to us, and dispatched between 01:00 and "
                        "04:00. It does not stop at the front of the house.",
                        [
                            {"label": "Capacity", "value": "1 occupant"},
                            {"label": "Plates", "value": "Leasing company"},
                            {"label": "Dispatch window", "value": "01:00 to 04:00"},
                            {"label": "Entrance used", "value": "Yard, side gate"},
                        ],
                    ),
                ],
            ),
            _funeral_service(
                "Adjacent Plot Reservation",
                "Choose your neighbours. Reserve the plot beside an existing interment, or two side by "
                "side for later, on a fifty-year renewable term. The cemetery register is a public "
                "document and we will print the neighbouring entries for you before you commit — who is "
                "already there, when they were interred, and how long their own term has left to run.",
                62000,
                [
                    _venue(
                        "Preparation Suite",
                        "Where the deed is drawn and witnessed. The cemetery office countersigns within "
                        "ten working days and the reservation dates from the signature, not the counter.",
                        [
                            {"label": "Capacity", "value": "1 family"},
                            {"label": "Deed", "value": "Witnessed and notarised on site"},
                            {"label": "Countersignature", "value": "10 working days"},
                            {"label": "Transferable", "value": "Once, to a named relative"},
                        ],
                    ),
                    _venue(
                        "Chapel of Rest B",
                        "Used for the site visit briefing before the drive to the cemetery, where a "
                        "director walks the family to the plot itself and lets them stand on it.",
                        [
                            {"label": "Capacity", "value": "1 family"},
                            {"label": "Site visit", "value": "Included, by car"},
                            {"label": "Cemeteries", "value": "Powązki, Bródno, Północny"},
                            {"label": "Decision required", "value": "Not on the day"},
                        ],
                    ),
                ],
            ),
        ],
        # Fallback for any home that has not been given its own headline
        # `service` above, so search never shows six identical rows.
        "simpleService": {
            "name": "Funeral Arrangement",
            "description": "A full arrangement from collection to committal, on a date of the "
                           "family's choosing. The celebrant, the bearers, the vehicle and every "
                           "registry filing are included in the one figure.",
            "slotDurationMinutes": 1440,
            "priceMinorUnits": 210000,
            "cancellationCutoffHours": 48,
            "minSlotsPerBooking": 1,
            "maxSlotsPerBooking": 1,
            "grid": {
                "daysBack": 7,
                "daysForward": 60,
                "dayStep": 1,
                "startTimes": [{"hour": 0, "minute": 0}],
            },
            "resource": {
                "name": "Chapel of Rest",
                "description": "The house chapel, laid out for a service.",
                "capacity": 1,
                "attributes": [
                    {"label": "Capacity", "value": "1 family"},
                    {"label": "Service length", "value": "45 minutes"},
                    {"label": "Registry filings", "value": "Included"},
                ],
            },
        },
    },
}
