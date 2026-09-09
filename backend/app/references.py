# Arbor: a config-driven booking engine
# Copyright (C) 2026 Alban Billiette and the Arbor contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Human-facing booking references.

The format lived twice, `routers/bookings.py` minted them for real bookings and
`seed.py` minted them for demo rows, so the two could drift and seeded data
would stop looking like the real thing.
"""
from __future__ import annotations

import secrets

# No ambiguous characters: no I/O/0/1, so a reference read aloud or typed off a
# screen cannot be transcribed wrong.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def booking_reference() -> str:
    """A short, unambiguous booking reference, e.g. `BK-7QK2XM`."""
    return "BK-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
