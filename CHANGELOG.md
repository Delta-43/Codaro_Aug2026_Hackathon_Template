# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- The pivot library: `pivots/` (100 generated configs), `scripts/check_pivots.py`
  and its companions, `docs/PIVOT-COVERAGE.md`, and the medical example config.
- The funeral-home vertical: its seed catalogue and demo content, the
  `/showcase` animation gallery, and its photography. `domain.config.json` is
  neutral again.

The pivot *system* is unchanged. What went is the example library around it, so
the repository ships the engine and one generic config.

### Added

- Showcase-only deployment mode (`NEXT_PUBLIC_SHOWCASE_ONLY=1`), which serves
  the landing page with no backend. See [DEPLOY.md](DEPLOY.md).
- An Open Graph card, generated at build time from the page's own wording.
While the major version is `0`, minor bumps may contain breaking changes.

## [Unreleased]

## [0.1.0], 2026-09-08

First public release. Arbor was built at the Codaro x Google for Startups
hackathon, where it won Track B (Booking and Resource Scheduling), and has been
developed further since.

### Added

- **Booking engine** on a neutral `provider → service → resource → slot →
  booking → user` spine: multi-slot bookings, party size, reschedule, cancel,
  and an append-only status history.
- **The pivot system**: `domain.config.json` (v2) holds the vocabulary and
  global defaults for a whole business domain. Eleven config blocks
  (`capabilities`, `booking`, `pricing`, `payments`, `inventory`, `location`,
  `prerequisites`, `timing`, `recurrence`, `entitlements`, `discovery`) are
  validated at load and served at `GET /config`, so changing the file changes
  the product without a migration. v1 config files still boot.
- **Per-service overrides**: any config block can be overridden per service via
  `services.metadata.<block>`, so one deployment can host businesses that price
  and gate completely differently.
- **Customer app**: search, provider profiles, availability calendar, booking,
  reschedule, cancel, messaging, reviews and follows.
- **Owner dashboard**: services, booking requests with approve/reject,
  calendar, per-resource analytics, profile and settings.
- **Auth**: Supabase Auth with JWTs verified against the project JWKS
  (ES256/RS256; HS256 deliberately rejected), plus per-user isolation through
  Postgres Row Level Security.
- **Waitlists**, availability by day and density by month.
- **Pivot coverage evidence**: 100 deliberately different businesses expressed
  as real configs and run through the validator and pricing engine
  (`scripts/check_pivots.py`), documented in `docs/PIVOT-COVERAGE.md`.
- **Deployment**: Docker Compose for local work, Railway (backend) and Vercel
  (frontend) for hosting.

### Security

- Symmetric HS256 tokens are rejected; accepting them would have let a token's
  own header select the weaker verification scheme.
- The Supabase service key is confined to system and cross-user work; every
  user-owned read and write goes through a JWT-scoped client so RLS applies.

[Unreleased]: https://github.com/kaveOO/Arbor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kaveOO/Arbor/releases/tag/v0.1.0
