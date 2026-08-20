# TODO — prioritized gaps (pre-hackathon review, 2026-08-19)

Snapshot from the whole-repo review on `develop` (see `REPORT.md` for what was
fixed). Items below were **found and deliberately deferred** — each names the
exact spot so it can be picked up cold. P1 = do first.

## P1 — correctness gaps that can bite during the event

1. **Capacity is check-then-insert with no serialization** —
   `backend/app/routers/bookings.py` `_resolve_selection` reads the
   `slot_occupancy` view, then the insert commits with no DB-level guard. Two
   concurrent creates for the last seat both pass and overbook (same race
   between create and approve's re-check). Needs a serialized commit (advisory
   lock like `seed.seed_lock`, an RPC, or a constraint) — a re-read narrows
   but cannot close it.
2. **Partial writes on the booking/slot join** — create (`bookings.py` ~line
   670), reschedule (delete→insert→update), and `_book_repeats` write the
   booking row and `booking_slots` in separate PostgREST calls with no cleanup
   on failure: a confirmed booking can hold zero capacity, or a reschedule can
   leave joins on the new slots while price/slot_id say the old ones.
3. **Waitlist races** — `waitlist.py`: join computes `position = max+1` and the
   `maxPerSlot` cap from a prior read (two concurrent joins collide); promote
   is not compare-and-set on `status='waiting'`, so two concurrent
   cancellations double-promote the same head. (`messages._repoint_preview`
   guards its identical race — copy that pattern.)
4. **Seeded demo data violates its own rules** — `backend/seed.py` seeds
   single-slot lifecycle bookings while `seed_config.py` writes
   `min_slots_per_booking = booking.duration.minUnits` (2 in the shipped
   config), so the demo's flagship "changeable" booking cannot be rescheduled
   at its own size (`_resolve_selection` → INVALID_RANGE). Also
   `_slot_for_booking` (seed.py ~519) ignores occupancy, so the demo booking
   can land on the holds-user's 100%-full slot. Fix the seeder before a
   min-units>1 pivot is demoed.
5. **Final-day availability offers slots booking refuses** — seed horizon
   iterates day `+forward` inclusive with local wall times, but
   `rules._advance_window` compares to an instant (`now + N days`), so on the
   last seeded day every slot later than the current time-of-day is visible
   on the calendar and refused at create. Either seed one day fewer or make
   the window a date comparison.
5b. **Entitlement credits need a ledger** — `backend/app/routers/bookings.py`
   `_consume_credit` / `_refund_credit`: spends and refunds are bare counter
   updates plus a `credit_refunded` metadata stamp, not receipts. Residual
   windows even after the CAS work: a crash between the refund decrement and
   the stamp write double-refunds on retry, and a booking whose best-effort
   consume failed can still refund (the entitlement drifts one credit rich).
   Fix: one ledger row per spend, unique on `booking_id`, making consume and
   refund naturally idempotent and auditable.

## P2 — security hardening (documented decisions needed)

6. **`POST /demo/reset` / `/demo/vertical` are require_user only** — any
   self-registered user can wipe and reseed the whole database
   (`routers/demo.py`). This is a *deliberate* demo feature (Account tab
   exposes it), but it ships as a one-request data-destruction endpoint.
   Decide: env-gate it (`DEMO_ENDPOINTS=off` in anything public) or accept.
7. **JWT `alg` is attacker-selectable** — `auth.py` (~209): an `alg: HS256`
   header always routes to the static `SUPABASE_JWT_SECRET` even on an ES256
   project, so forgery reduces to the weaker scheme; neither path checks
   `iss`. Add an `AUTH_ALLOWED_ALGS` allow-list (drop HS256 once the project
   is ES256-only) and an issuer check.
8. **Fail-open role fallback** — `auth.py:142-147`: any `profiles` lookup
   exception falls back to the token's `user_metadata.role`, which the user
   can set via GoTrue directly — a demoted owner regains owner powers during
   any profiles outage. Consider fail-closed (fallback to `client`) or a
   longer-lived last-known-good cache.
9. **JWKS cache cleared on every bad signature** — `auth.py:198-201` clears
   and refetches JWKS on `InvalidSignatureError`; a flood of garbage-signed
   tokens hammers the JWKS endpoint. Refresh only on unknown-kid /
   `PyJWKClientError`.

## P3 — declared-but-drifting behavior

10. **`rate.per: "unit"` is unbookable through the API** — `pricing._quantity`
    reads `ctx["unit_count"]`, which no request model can supply; only the
    offline pivot harness passes it, so pivots "pass" quantities the live API
    prices at 1. Add `unitCount` to `QuoteReq`/`BookingCreateReq` or move the
    key to the DECLARED_ONLY table.
11. **Legacy price column vs global tiers** — `rules.py` ~475 folds
    `price_minor_units` into `rate.amountMinorUnits`, but a *global*
    `pricing.tiers` still outranks it in `quote()`: an un-pivoted service
    serializes the column price and charges the tier. Decide the precedence
    and pin it.
12. **`partySize` tier clause matches weighted units, not heads** —
    `pricing.py:273-275` compares `_person_units(ctx)`; with `priceFactor`
    bands, tier eligibility flips with the weighting and with whether the
    client sent bands at all. Decide (heads is the intuitive read) and test.
13. **Capability↔block contradiction check exists only for `payments`** —
    `config_schema.validate`: `capabilities.recurrence: false` +
    `recurrence.enabled: true` (etc. for waitlist/entitlements/prerequisites)
    validates clean and is silently inert. Add the three checks; re-run
    `scripts/check_pivots.py` after (some pivots may need fixing).
14. **Waitlist promotion runs only on cancel** — slots freed by *reschedule*
    and requests *rejected* after filling never promote
    (`promote_from_waitlist` has one call site, `bookings.py` cancel).
15. Minor state nits: `is_upcoming` counts a cancelled future booking as
    upcoming (contradicts its own comment); a customer cannot withdraw a
    capacity-free `pending` request inside the cutoff. (The rejected→cancelled
    flip was fixed — cancel now refuses rejected requests.)
16. `messages.py`: `reply_to_id` accepts a message from a *different*
    conversation; `mark_read` stamps soft-deleted messages.
17. Seed ignores `capabilities.reviews`/`.follows` (always seeds a review +
    follow), so `make checkseed` FAILs on any pivot with either off; the
    "inside cutoff" fixture goes negative when cutoff < ~1.7h.
18. `seed_if_empty` TOCTOU: the emptiness read happens before the try-lock
    and is never re-checked after acquiring — a boot racing a finishing
    reseed can re-truncate a fully seeded DB (`seed.py:897-944`).

## P4 — frontend polish

19. **Quote errors are swallowed on the confirm screen** —
    `confirm-screen.tsx` ~173: `.catch(() => quote: null)` renders "Price
    unavailable — confirmed when you book" even for `SLOT_UNAVAILABLE`, which
    means the booking *cannot* succeed. Surface the code and offer re-pick.
20. **Party of zero books as one** — `party-bands.tsx` allows all bands at 0;
    `booking-flow.tsx` then forces partySize=1. Disable confirm at 0 total.
21. **401/403 map to `NETWORK`** — `api/index.ts` `statusCode()`. Adding an
    `AUTH` code touches `ApiErrorCode` + `errors.py` + the contract test —
    do all three together.
22. **`frontend/knip.json` was loosened** (`ignoreExportsUsedInFile: true`)
    in the pivot-presets branch — this weakens the dead-export CI gate.
    Confirm intentional or revert.

## P5 — docs & tooling debt

23. Stale `CLAUDE.md`s: backend (missing `messages`/`waitlist` routers,
    `gdpr`/`avatars`/`clock`/`references`, quote/pay/return/prerequisites
    endpoints; "quotes/cart have no backend" is no longer true), supabase
    (missing conversations/messages/entitlements/waitlist_entries), frontend
    (missing Messages tab, `/owner/*`, `/login/business`, cart), test
    (stale counts/tree), root (repo-layout table omits `landing/`).
24. `scripts/check_pivots.py` audit map double-claims: `payments.flow` and
    `inventory.returnRequired` sit in both ENFORCED and DECLARED_ONLY;
    `booking.party.composition`/`subject`/`options` and
    `timing.blackouts`/`seasons` sit in DECLARED_ONLY but are enforced.
25. `DEPLOY.md` has no `landing/` deployment story (docker-compose :3001 only).
26. No mypy on the backend; no pre-commit; no frontend runtime tests (the
    contract test covers paths + error codes only).
27. `pivots/everything-on.example.json` is byte-identical to the root
    `domain.config.json` — editing either silently diverges them; add a check
    or a generation step.
28. ~10 stale local branches remain (squash-merged, so `git branch -d`
    refuses); prune with `-D` after confirming against `origin`.
