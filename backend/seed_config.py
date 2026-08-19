"""Build a seed spec from `domain.config.json` instead of `seed_data.VERTICALS`.

`seed_vertical()` consumes a "vertical spec" — a dict of providers, services,
resources and slot grids. Until now the only source of one was `seed_data.py`,
three hardcoded businesses, which is why a pivot changed what the engine
believed while the demo data went on describing a car-rental company.

This module produces the same shape from the pivot file, so a reseed rebuilds
data the loaded config actually describes: the right currency and timezone, the
right durations, prices and cutoffs, capacity that can seat the configured
party, and — in single-tenant mode — a provider whose `public_code` is the one
`tenancy.providerCode` names, so the business always resolves.

What is DERIVED and what is INVENTED, kept honest:

  derived  every number, code and zone (`pricing`, `timing`, `booking`,
           `location`, `tenancy`), the flagship business name (`copy`), the
           service names (`pricing.tiers` / `booking.options`), and all nouns
           (`terms`).
  invented the prose (taglines, descriptions) and, in marketplace mode, the
           names of the businesses *other* than the flagship. The config
           carries no directory of businesses and no marketing copy per
           business; those are generated mechanically from `terms` and
           `location.origin.city` so they at least read as the right niche.

`scripts/check_seed.py` is the acceptance test: after a reseed through this
module its MATCH section should be clean.
"""
from __future__ import annotations

from typing import Any

# `services.booking_model` is a three-value enum in the schema; the config has
# no such field, so it is inferred. Party shape wins over unit kind: anything
# that seats several independent customers in one slot is shared capacity
# whatever the unit is called.
_UNIT_KIND_TO_MODEL = {
    "staff": "one_to_one",
    "class_capacity": "shared_capacity",
    "seat": "shared_capacity",
    "asset": "unit_selection",
    "room": "unit_selection",
    "stock_item": "unit_selection",
    "subscription_slot": "one_to_one",
    "project": "one_to_one",
    "time_slot": "one_to_one",
}

_MULTI_PROVIDER_COUNT = 6  # enough for search, facets and a follows demo

# Marketplace mode needs several businesses and the config names only one (the
# flagship, from `copy.landingTitle`). These qualifiers are the invented part:
# neutral, place-shaped, and combined with the deployment's OWN noun for a
# business (`terms.provider`), so a yoga config yields "Riverside Studio" rather
# than "the city Business 2".
_SIBLING_QUALIFIERS = ["Riverside", "Old Town", "Northgate", "Harbour", "Parkside", "Garden"]


def _city(cfg: dict) -> str:
    """The business's city: from `location.origin`, else the IANA zone's own
    place name (`Europe/Warsaw` -> `Warsaw`), else nothing rather than a
    placeholder that reads as missing data."""
    origin = cfg["location"].get("origin") or {}
    if origin.get("city"):
        return origin["city"]
    zone = cfg["location"]["timezone"]
    if "/" in zone:
        return zone.rsplit("/", 1)[-1].replace("_", " ")
    return ""


def _code(name: str, index: int) -> str:
    """A stable VISTULA-4471-shaped public code derived from the name."""
    letters = "".join(c for c in name.upper() if c.isalpha())[:5] or "BIZ"
    h = 2166136261
    for ch in f"{name}{index}":
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return f"{letters}-{h % 9000 + 1000}"


def booking_model(cfg: dict) -> str:
    party = cfg["booking"]["party"]
    if party["mode"] == "group" or (party.get("max") or 1) > 1 and party["mode"] != "buyout":
        return "shared_capacity"
    return _UNIT_KIND_TO_MODEL.get(cfg["booking"]["unitKind"], "unit_selection")


def _capacity(cfg: dict, model: str) -> int:
    """How many customers one slot must hold.

    A buyout books the whole unit, so its capacity is the unit's size, not the
    party's. A shared-capacity slot must seat `party.max` (falling back to the
    legacy `maxBookingsPerSlot`), and never fewer than `party.min` — capacity
    below the minimum party makes every booking unfillable, which is the
    failure `check_seed.py` flags on a stale seed.
    """
    party = cfg["booking"]["party"]
    declared = party.get("max") or cfg["timing"].get("maxBookingsPerSlot") or 1
    if model == "shared_capacity":
        return max(int(declared), int(party.get("min") or 1), 2)
    if party["mode"] == "buyout":
        return max(int(declared), int(party.get("min") or 1))
    return max(int(declared), 1)


def _grid(cfg: dict, duration_minutes: int) -> dict:
    """Slot grid matched to the configured granularity and booking window.

    A day/night/week unit gets one slot per day at local midnight; anything
    shorter gets a trading day stepped by the slot duration. `_local_days` lays
    these in the business's own zone, so `location.timezone` is what decides
    where they land.
    """
    # Exactly the declared window. It used to be `max(window, 14)` — plus, for
    # long units, a six-unit floor — so the seed reached past what the config
    # said was bookable. That was harmless only while
    # `advanceBookingWindowDays` went unenforced; now that the rule dispatches,
    # seeding beyond it would lay down slots the booking path refuses. A
    # business that wants a longer horizon raises the window, which is what the
    # key is for.
    forward = window = int(cfg["timing"].get("advanceBookingWindowDays") or 30)
    if duration_minutes >= 1440:
        # One slot per UNIT, not per day: a week-long unit laid on a daily grid
        # would start a new 7-day slot every 24h, so seven overlapping slots
        # would cover each week and capacity would read as sevenfold.
        step = duration_minutes // 1440
        # `daysBack` must be a whole number of units, so the lattice lands ON
        # today. At a flat 7 a monthly unit stepped -7, +23, +53 … while
        # `seed._align_to_unit_grid` anchors on today (0, +30, +60 …); a slot
        # placed by one would sit mid-unit on the other's grid and overlap it.
        # Ceil to at least a week so day-sized units keep their 7 days of past.
        back = step * max(1, -(-7 // step))
        # A window measured in DAYS starves a long unit — 30 days of a monthly
        # unit is one bookable month — but that is the CONFIG's statement to
        # make, not the seeder's to override. Such a business raises
        # `advanceBookingWindowDays`; see pivots 007/019/041.
        return {"daysBack": back, "daysForward": forward, "dayStep": step,
                "startTimes": [{"hour": 0, "minute": 0}]}
    starts, minute = [], 9 * 60
    while minute + duration_minutes <= 18 * 60 and len(starts) < 16:
        starts.append({"hour": minute // 60, "minute": minute % 60})
        minute += duration_minutes
    return {"daysBack": 7, "daysForward": forward,
            "startTimes": starts or [{"hour": 9, "minute": 0}]}


def _meta_values(fields: list[dict]) -> dict:
    """Plausible values for the metaFields an entity declares.

    A declared field with no value anywhere in the data is indistinguishable
    from an undeclared one, so the seed fills each declared key by type.
    """
    out: dict[str, Any] = {}
    for f in fields:
        kind, key = f.get("type", "text"), f["key"]
        if kind == "boolean":
            out[key] = False
        elif kind == "number":
            out[key] = f.get("min") or 0
        elif kind == "select":
            options = f.get("options") or []
            out[key] = options[0] if options else ""
        elif kind == "date":
            out[key] = None
        else:
            out[key] = f.get("helpText") or f"{f.get('label', key)} (demo)"
    return out


_LOCATION_LABELS = {
    "on_site": "On site", "at_customer": "At your address", "remote": "Remote",
    "delivery": "Delivery", "pickup": "Collection",
}


def _duration_label(minutes: int) -> str:
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day" + ("s" if days > 1 else "")
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" + ("s" if hours > 1 else "")
    return f"{minutes} min"


def _attributes(cfg: dict, label: str, capacity: int, duration: int) -> list[dict]:
    """The spec rows on a resource card.

    Must be a LIST of `{label, value}` — that is the contract in
    `serialize.py` and `types/domain.ts`, and the provider page maps over it.
    Values are drawn from the config so the card describes the pivoted offering.
    """
    terms = cfg["terms"]
    rows = [{"label": terms["service"], "value": label},
            {"label": terms["slot"], "value": _duration_label(duration)}]
    if capacity > 1:
        # The card renders "label: value", so the party noun belongs on the left
        # — "Whole group: 6" reads; "Capacity: 6 whole group" does not.
        rows.insert(0, {"label": terms["party"], "value": str(capacity)})
    mode = cfg["location"].get("default")
    if mode in _LOCATION_LABELS:
        rows.append({"label": "Where", "value": _LOCATION_LABELS[mode]})
    return rows


def _service_specs(cfg: dict, model: str) -> list[dict]:
    """One service per priced tier, else per option choice, else a single one.

    `pricing.tiers` is the closest thing the config has to a catalogue: each
    tier already carries a customer-facing label and its own price, so a tiered
    pivot seeds as the several offerings it describes rather than one generic
    row.
    """
    pricing, booking, terms = cfg["pricing"], cfg["booking"], cfg["terms"]
    duration = int(cfg["timing"]["slotDurationMinutes"])
    base_price = int(pricing["rate"]["amountMinorUnits"])
    capacity = _capacity(cfg, model)
    res_meta = _meta_values(cfg["metaFields"].get("resources", []))
    slot_meta = _meta_values(cfg["metaFields"].get("slots", []))
    svc_meta = _meta_values(cfg["metaFields"].get("services", []))

    named: list[tuple[str, int]] = [
        (t["label"], int(t["amountMinorUnits"])) for t in pricing.get("tiers") or []
    ]
    if not named:
        for opt in booking.get("options") or []:
            for choice in opt.get("choices") or []:
                label = choice if isinstance(choice, str) else choice.get("label")
                if label:
                    named.append((f"{opt['label']}: {label}", base_price))
    if not named:
        named = [(terms["service"], base_price)]

    specs = []
    for i, (label, price) in enumerate(named[:4]):
        resource_noun = terms["resource"]
        specs.append({
            "name": label,
            "description": f"{label} — {cfg['copy']['landingSubtitle']}",
            "slotDurationMinutes": duration,
            "minSlotsPerBooking": int(booking["duration"]["minUnits"]),
            "maxSlotsPerBooking": int(booking["duration"]["maxUnits"]),
            "priceMinorUnits": price,
            "cancellationCutoffHours": int(cfg["timing"]["cancellationWindowHours"]),
            "grid": _grid(cfg, duration),
            "metaFields": {"service": svc_meta, "resource": res_meta, "slot": slot_meta},
            "resources": [
                {
                    "name": f"{resource_noun} {n + 1}",
                    "description": f"{resource_noun} {n + 1} — {label}.",
                    "capacity": capacity,
                    "attributes": _attributes(cfg, label, capacity, duration),
                }
                # One unit is enough when the customer never picks one; a
                # unit-selection niche needs something to choose between.
                for n in range(3 if model == "unit_selection" else 1)
            ],
        })
        _ = i
    return specs


def spec_from_config(cfg: dict) -> dict:
    """A `seed_data.VERTICALS`-shaped spec describing the loaded pivot."""
    terms, copy_, location = cfg["terms"], cfg["copy"], cfg["location"]
    origin = location.get("origin") or {}
    city = _city(cfg)
    model = booking_model(cfg)
    services = _service_specs(cfg, model)
    single = cfg["tenancy"]["mode"] == "single"

    categories = [{"id": s["name"].lower().replace(" ", "-")[:24] or f"cat{i}",
                   "label": s["name"]} for i, s in enumerate(services)]

    flagship = copy_["landingTitle"]
    names = [flagship] + [
        # Invented: the config carries no directory of businesses.
        f"{_SIBLING_QUALIFIERS[n % len(_SIBLING_QUALIFIERS)]} {terms['provider']}"
        for n in range(_MULTI_PROVIDER_COUNT - 1)
    ]
    if single:
        names = names[:1]

    providers = []
    for i, name in enumerate(names):
        providers.append({
            "name": name,
            "tagline": copy_["landingSubtitle"] if i == 0
            else (f"{terms['services']} in {city}." if city else f"{terms['services']}, booked online."),
            "bio": (f"{name} — {copy_['landingSubtitle']} "
                    f"Book a {terms['slot'].lower()} and we'll confirm it."),
            "categoryId": categories[i % len(categories)]["id"],
            "city": city,
            "country": "",
            "lat": origin.get("lat") or 0.0,
            "lng": origin.get("lng") or 0.0,
            # Single mode resolves THE business through this code, so it must be
            # the one the config names or the whole deployment shows "no business".
            "publicCode": cfg["tenancy"]["providerCode"] if (single and i == 0)
            else _code(name, i),
            "rating": 4.6,
            "reviewCount": 12 + i * 3,
            "links": [],
        })

    simple = dict(services[0])
    simple["resource"] = simple.pop("resources")[0]

    return {
        "verticalId": f"config:{cfg['domain']}",
        "bookingModel": model,
        "currency": cfg["pricing"]["currency"],
        "baseTz": location["timezone"],
        "categories": categories,
        "providers": providers,
        "demoServices": services,
        "simpleService": simple,
    }
