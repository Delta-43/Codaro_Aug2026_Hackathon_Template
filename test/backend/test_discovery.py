"""Unit tests for `app.discovery.search_facets`.

`search_facets(db)` derives which filter/sort dimensions the current catalog
supports directly from the seeded data, so the filter UI pivots automatically
with no hand-kept flags (see `main._config_with_facets`, which threads this onto
`GET /config`). These tests exercise the helper in isolation against the offline
`FakeSupabase`:

* `price`  — True iff **any** service has `price_minor_units > 0`.
* `distance` — True iff **any** provider's `metadata.location` has a non-zero
  `lat` or `lng`.
* `rating`  — always True (every provider carries one).
"""

from __future__ import annotations

from app import discovery
from fakes import FakeSupabase
from helpers import make_provider, make_service


def _facets(db: FakeSupabase) -> dict[str, bool]:
    return discovery.search_facets(db)


def test_empty_catalog_supports_only_rating():
    """No services and no providers -> price/distance off, rating still on."""
    db = FakeSupabase()
    assert _facets(db) == {"price": False, "distance": False, "rating": True}


def test_priced_services_and_real_coords_enable_every_facet():
    db = FakeSupabase()
    provider = make_provider(db, metadata={"location": {"lat": 52.2297, "lng": 21.0122}})
    make_service(db, provider["id"], price_minor_units=2500)

    assert _facets(db) == {"price": True, "distance": True, "rating": True}


def test_all_free_services_disable_the_price_facet():
    """A completely free catalog (every price_minor_units == 0) -> price off,
    even though a provider still has real coordinates."""
    db = FakeSupabase()
    provider = make_provider(db, metadata={"location": {"lat": 40.0, "lng": -3.0}})
    make_service(db, provider["id"], name="Free A", price_minor_units=0)
    make_service(db, provider["id"], name="Free B", price_minor_units=0)

    facets = _facets(db)
    assert facets["price"] is False
    assert facets["distance"] is True
    assert facets["rating"] is True


def test_a_single_priced_service_among_free_ones_enables_price():
    """`price` is an *any* over the catalog — one paid service is enough."""
    db = FakeSupabase()
    provider = make_provider(db)
    make_service(db, provider["id"], name="Free", price_minor_units=0)
    make_service(db, provider["id"], name="Paid", price_minor_units=1)

    assert _facets(db)["price"] is True


def test_missing_location_metadata_disables_distance():
    """Providers with no `metadata.location` at all -> distance off (a priced
    service keeps price on so the two facets are shown to be independent)."""
    db = FakeSupabase()
    provider = make_provider(db)  # metadata defaults to {} -> no location
    make_service(db, provider["id"], price_minor_units=999)

    facets = _facets(db)
    assert facets["distance"] is False
    assert facets["price"] is True
    assert facets["rating"] is True


def test_zero_coordinates_do_not_count_as_a_location():
    """A `location` present but with lat == lng == 0 is treated as no coords."""
    db = FakeSupabase()
    make_provider(db, metadata={"location": {"lat": 0, "lng": 0}})

    assert _facets(db)["distance"] is False


def test_a_nonzero_lat_alone_enables_distance():
    db = FakeSupabase()
    make_provider(db, metadata={"location": {"lat": 51.5, "lng": 0}})

    assert _facets(db)["distance"] is True


def test_a_nonzero_lng_alone_enables_distance():
    db = FakeSupabase()
    make_provider(db, metadata={"location": {"lat": 0, "lng": -0.12}})

    assert _facets(db)["distance"] is True


def test_distance_is_an_any_over_providers():
    """One provider with real coords is enough even if others have none."""
    db = FakeSupabase()
    make_provider(db, name="No coords")
    make_provider(db, name="Has coords", metadata={"location": {"lat": 48.85, "lng": 2.35}})

    assert _facets(db)["distance"] is True


def test_rating_is_always_true():
    """Rating is offered regardless of catalog contents."""
    db = FakeSupabase()
    assert _facets(db)["rating"] is True

    provider = make_provider(db, metadata={"location": {"lat": 10.0, "lng": 10.0}})
    make_service(db, provider["id"], price_minor_units=5000)
    assert _facets(db)["rating"] is True


def test_null_price_minor_units_is_treated_as_free():
    """A service row whose price_minor_units is None (nullable column) counts as
    0, not a crash — mirrors `int(s.get(...) or 0)`."""
    db = FakeSupabase()
    provider = make_provider(db)
    make_service(db, provider["id"], price_minor_units=None)

    assert _facets(db)["price"] is False
