"""e2e-suite fixtures.

The live e2e tests mutate the *real* Supabase project — they can switch the
demo vertical and create/cancel bookings. Left alone, that leaves the project
on whatever vertical the last test touched (e.g. stuck on `group`). This
session-scoped, autouse teardown reseeds the default `fleet` vertical once the
whole e2e session finishes, so the project is always left clean.

It reseeds only *after* the session (the tests assert against the current seed
counts, so we must not disturb them up front). It is gated on the same env the
live suite already requires (`SUPABASE_URL` + `SUPABASE_ANON_KEY`), so when the
live suite is skipped this fixture is a no-op and never fails collection.
"""

from __future__ import annotations

import os

import pytest

# `test/conftest.py` has already put `backend/` on sys.path, so `seed`
# resolves to the real backend seeder.
_HAVE_LIVE_ENV = bool(
    os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY")
)

_DEFAULT_VERTICAL = "fleet"


@pytest.fixture(scope="session", autouse=True)
def restore_default_vertical():
    """After the e2e session, reseed the default vertical so the demo project
    is left clean regardless of what the tests switched it to."""
    yield
    if not _HAVE_LIVE_ENV:
        # Live suite was skipped — nothing ran against Supabase, nothing to restore.
        return
    try:
        import seed

        seed.seed_vertical(_DEFAULT_VERTICAL)
    except Exception as exc:  # pragma: no cover - best-effort cleanup
        # Never let cleanup turn a green run red; just surface a warning.
        import warnings

        warnings.warn(f"e2e teardown: could not reseed '{_DEFAULT_VERTICAL}': {exc}")
