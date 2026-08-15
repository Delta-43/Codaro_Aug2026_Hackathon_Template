# NOTEBOOK — Codaro Frontend

## 1. Project Snapshot

Demo-ready, mock-data-driven booking & scheduling frontend (Next.js 14 App
Router, Tailwind, shadcn/ui). Consumed by hackathon judges (working demo) and
the backend team (typed data contract + a single API module they later swap
for HTTP). Runtime state is in-memory only; a hard refresh resets to seed.
**Current phase: 8 complete** — contract, API seam, mock store, three seeds,
responsive shell, app-wide context, and all five tabs: **Search**, **Provider**,
**Calendar** (full Month/Week/Day booking flow), **Tab 4 Bookings** (Upcoming/
Past list, detail, reschedule, cancel, review — Phase 7), and **Tab 5 Account**
(profile editing via `updateUser` + timezone, payment stub, demo panel —
Phase 8). The whole click path — search → provider → calendar → book →
reschedule/cancel/review — was run end-to-end against `next dev` and verified.
Remaining: polish/a11y (9) and demo hardening (10).

Feature components are built with `Button` (from the shadcn kit) plus local,
token-styled elements (`components/modal.tsx`, `skeleton.tsx`, `avatar-img.tsx`)
because only `button` has been added via CLI so far. Swapping in shadcn
`Card`/`Input`/`Dialog`/etc. later is a localized change — no component imports
a primitive that doesn't exist, so the build stays green.

The app lives under `frontend/src`. The previous backend-integrated frontend
(`app/` + `lib/`, config-driven from `GET /config`) was retired into
`frontend/_legacy/` (kept in git, excluded from tsconfig, not routed) after an
explicit decision to build the mock-driven app fresh.

## 2. Data Contract

Canonical types — `src/types/domain.ts`. All timestamps UTC ISO-8601 (`…Z`);
convert to `User.timezone` only at render.

- `ID = string`, `IsoUtc = string`, `VerticalId = 'fleet'|'oneToOne'|'group'`
- `BookingModel = 'unit_selection'|'one_to_one'|'shared_capacity'`
- `Provider` — id, name, avatarUrl, coverUrl?, tagline, bio, categoryId,
  location{city,country,lat,lng}, rating, reviewCount, links[], publicCode,
  serviceIds[]
- `Service` — id, providerId, name, description, imageUrl?, bookingModel,
  slotDurationMinutes, minSlotsPerBooking, maxSlotsPerBooking, priceMinorUnits,
  currency, cancellationCutoffHours, resourceIds[]
- `Resource` — id, serviceId, name, description?, imageUrl?, capacity,
  attributes[], active
- `SlotStatus = 'available'|'partially_booked'|'full'|'blocked'|'past'`
- `Slot` — id, serviceId, resourceId, startUtc, endUtc, capacity, bookedCount,
  status (sent explicitly; UI never recomputes)
- `BookingStatus = 'confirmed'|'cancelled'|'completed'`
- `Booking` — id, reference, userId, providerId, serviceId, resourceId,
  slotIds[], startUtc, endUtc, status, partySize, priceMinorUnits, currency,
  createdAtUtc, cancelledAtUtc?, changeHistory[], review?
- `User` — id, displayName, email, avatarUrl, timezone, verified,
  followedProviderIds[]
- `DayAvailability` — date (YYYY-MM-DD in user tz), slots[], totalCapacity,
  totalBooked
- `MonthDensityCell` — date, density(0|1|2|3)

API surface — `src/api/index.ts` (all async, 150–450ms simulated latency,
deep-cloned results, throw `ApiError`):

```
searchProviders(q:{text?,categoryId?,near?}): Promise<Provider[]>
getProvider(id): Promise<Provider>
getProviderByCode(code): Promise<Provider>
followProvider(id): Promise<User>
unfollowProvider(id): Promise<User>
getServices(providerId): Promise<Service[]>
getService(id): Promise<Service>
getResources(serviceId): Promise<Resource[]>
getAvailability(q:{serviceId,resourceId?,fromUtc,toUtc}): Promise<DayAvailability[]>
getMonthDensity(q:{serviceId,resourceId?,month}): Promise<MonthDensityCell[]>
createBooking({serviceId,resourceId,slotIds,partySize}): Promise<Booking>
getBookings(scope:'upcoming'|'past'|'all'): Promise<Booking[]>
getBooking(id): Promise<Booking>
rescheduleBooking(id,newSlotIds): Promise<Booking>
cancelBooking(id): Promise<Booking>
leaveReview(id,rating,text): Promise<Booking>
getCurrentUser(): Promise<User>
updateUser(patch:Partial<User>): Promise<User>
getActiveVertical(): Promise<VerticalId>   // convenience; demo state, not backend
setVertical(id): Promise<void>
resetDemoData(): Promise<void>
```

`ApiError.code = 'SLOT_UNAVAILABLE'|'CUTOFF_PASSED'|'NOT_FOUND'|'CAPACITY_EXCEEDED'|'INVALID_RANGE'|'NETWORK'`.

## 3. Backend Integration Points

- **Replace `src/api/index.ts`** function bodies with HTTP calls returning the
  same shapes and throwing the same `ApiError` codes. Nothing else changes.
- **`src/api/mockStore.ts`, `src/api/latency.ts`, `src/api/seed/*`,
  `src/api/storeTypes.ts`** are mock-only and get deleted at integration.
- **`src/types/domain.ts`** stays — it is the shared contract. Floor rule: add
  fields, never remove.
- **Mutation semantics the server must enforce** (mirrored in the mock now):
  - `createBooking` re-checks each slot's remaining capacity at commit; throws
    `SLOT_UNAVAILABLE` if full, `CAPACITY_EXCEEDED` if partySize > capacity.
  - Multi-slot selections must be contiguous (slot[i].start == slot[i-1].end),
    same resource, count within min/max; else `INVALID_RANGE`.
  - `cancelBooking` → status `cancelled`, sets `cancelledAtUtc`, releases
    capacity on every slot in `slotIds`. `CUTOFF_PASSED` inside the window.
  - `rescheduleBooking` is atomic: acquire new slots first (crediting back the
    booking's own hold on any re-selected slot), release old only on success;
    `CUTOFF_PASSED` inside the window. Records `changeHistory`.
  - Cutoff = `now >= start - cancellationCutoffHours`.
  - A booking with `endUtc` in the past reads as `completed`, never
    `confirmed` (normalized on read).
- **`Slot.status` is authoritative from the server** — the mock derives it from
  (capacity, bookedCount, endUtc, now); the real backend should send the same.

## 4. Architecture Decisions

- **2026-08-15 — Retire the existing backend-integrated frontend, build fresh
  under `src/`.** The repo already had a working `GET /config`-driven app
  (`app/`+`lib/`). The directive specifies an incompatible mock-first,
  vertical-pivot architecture. Chosen (with user sign-off): move old app to
  `_legacy/` (preserved, unrouted, tsconfig-excluded), build the directive's
  app in `src/app` + `src/{types,api,config,lib}`. Alt considered: adapt the
  directive onto the existing live API — rejected as contrary to the mock-first
  mandate and the runtime vertical switcher.
- **2026-08-15 — `@/*` alias remapped to `./src/*`.** Keeps imports clean and
  the legacy tree out of the build.
- **2026-08-15 — Adopt Tailwind v4 (CSS-first).** The shadcn components pulled
  in are v4/react-aria style ("aria-rhea", baseColor "mist", oklch, tw-animate-
  css). Standardized on Tailwind v4: `globals.css` uses `@import "tailwindcss"`
  + `@theme inline` oklch tokens + `@custom-variant dark`; PostCSS uses
  `@tailwindcss/postcss`; the v3 `tailwind.config.ts` and `autoprefixer` were
  removed; `components.json` is `tailwind.config: ""`. UI primitives live in
  `src/components/ui/*` (react-aria + cva). Fonts: `next/font` Outfit exposed as
  `--font-outfit`, mapped to `--font-sans` in `@theme inline`.
- **2026-08-15 — Deterministic images are inline SVG data URIs** (avatars,
  covers, tiles) rather than a placeholder CDN. Satisfies "deterministic
  placeholder image URLs" while honoring the strict no-network constraint;
  renders identically offline every time.
- **2026-08-15 — Slots stored as true UTC instants anchored to a base
  timezone** (`Europe/Warsaw`) via a DST-aware wall-clock→UTC conversion. The
  seeded user shares that timezone, so the demo opens on local working hours;
  changing timezone in Account re-renders the same instants — the intended demo
  moment.
- **2026-08-15 — Dedicated slots for seeded upcoming bookings.** The
  inside/outside-cutoff bookings sit on inserted slots at deterministic offsets
  from `now`, so the locked/changeable states are guaranteed regardless of
  vertical or run time.

## 5. Assumptions Made

- **maxSlotsPerBooking:** fleet 14, oneToOne 2 (enables a real multi-slot
  booking + range selection for back-to-back hours), group 1. Group's "multi"
  dimension is party size, not slot count — so group has no multi-slot seed
  booking (the §8 multi-slot edge case is covered by fleet & oneToOne).
- **Currency EUR across all verticals** for readable demo prices (cities are
  Polish; PLN would be more literal). Easily changed per vertical.
- **Only the demo provider (index 0) gets the rich, edge-case seed.** Other
  providers get one simple service + light availability so locking into them
  still shows a working calendar. §8 only mandates richness for the locked-in
  provider.
- **One provider is pre-followed** (index 1) so Search shows the pinned/
  followed treatment without user action.
- **Seed user:** "Mara Lindqvist", timezone `Europe/Warsaw`, verified.

## 6. Open Questions

1. **`lucide-react ^1.31.0` — verify it resolves on install.** Historically
   lucide-react is 0.x; an unresolvable pin breaks `npm install` for the team.
   (Tailwind v3/v4 question is now resolved → v4; see Architecture Decisions.)
2. ~~**No Node/Docker in the build sandbox**~~ — Resolved: `next build` passes
   clean (all 9 routes) and the app was run under `next dev` and clicked through
   end-to-end (list → detail → reschedule commit → cancel → profile save).
3. Currency/locale per vertical — keep EUR, or localize?

## 7. Demo Script

See directive §12 (kept in sync here once the UI exists). Current status:
scaffold only — the click path is not yet runnable end to end.

## 8. Changelog

- **2026-08-15 — Phase 0:** retired legacy app to `_legacy/`; scaffolded
  `src/app` shell (layout, globals with design tokens + one restrained accent,
  placeholder page); remapped alias; tailwind content globs; `cn()` util.
- **2026-08-15 — Styling stack → Tailwind v4** (CSS-first oklch tokens,
  react-aria shadcn, tw-animate-css); removed v3 `tailwind.config.ts` +
  autoprefixer.
- **2026-08-15 — Phase 1:** `types/domain.ts` (contract); `api/` seam
  (`index.ts`, `mockStore.ts` with full mutation semantics, `errors.ts`,
  `latency.ts`, `storeTypes.ts`); three vertical seeds + shared `common.ts`;
  `config/verticals.ts` registry. Seeds callable from console via
  `window.codaro`.
- **2026-08-15 — Phase 2:** app-wide context (`context/app-context.tsx`:
  vertical + user + locked-in provider/service/resource, switchVertical,
  reseed); responsive shell (`components/app-shell.tsx`: bottom tabs <768px,
  left drawer + top bar ≥768px); `(app)` route group with `/search /provider
  /calendar /bookings /bookings/[id] /account`; `/` redirects to `/search`;
  purposeful empty states on tabs 2–3; Account demo panel wired (vertical
  switch + reset). UI split: primitives added via shadcn CLI by the human;
  Claude builds shell + features on top.
- **2026-08-15 — Phase 3:** Tab 1 Search — debounced text/location + category
  chips (`searchProviders`), "Have a provider code?" (`getProviderByCode`),
  demo QR scanner (no camera; mock targets resolve via code), followed pinned +
  highlighted, provider preview modal with optimistic Follow + Open. Four states
  throughout. New: `components/search/*`, `components/modal.tsx`,
  `hooks/use-debounced-value.ts`, `hooks/use-follow.ts`, `lib/geo.ts`.
- **2026-08-15 — Phase 4:** Tab 2 Provider — cover/avatar/rating/location,
  Follow toggle, switch-provider, bio, external links, services list (duration ·
  price · spots-per-session for shared_capacity). Selecting a service → active +
  calendar; unit_selection opens `components/provider/resource-picker.tsx`
  (units + "Any available unit") first.
- **2026-08-15 — Phase 5:** Tab 3 Calendar — `lib/calendar.ts` (tz-correct week/
  month math), `components/calendar/*` (zoom control, week/day/month views,
  density dots, slot-state pills). Navigation clamps at the current period.
  Browse-only; `Slot.status` from the API drives every pill.
- **2026-08-15 — Phase 6:** booking flow — `components/booking/*`. Single-slot
  services confirm on tap; range services build a contiguous span (validated
  inline via a commit-window availability refetch) with a running total;
  shared_capacity gets a party stepper capped at remaining. Confirm screen
  (full details + policy) → `createBooking` → result screen with reference.
  SLOT_UNAVAILABLE/CAPACITY_EXCEEDED → banner + availability refresh, selection
  cleared, user stays on the calendar. `reloadKey` added to CalendarView.
- **2026-08-15 — Phase 7:** Tab 4 Bookings — `app/(app)/bookings/page.tsx`
  (Upcoming/Past segmented list; provider/service names resolved once per list
  since bookings carry only ids) and `bookings/[id]/page.tsx` (client loader).
  New `components/booking/{booking-card,status-badge,booking-detail,cancel-dialog,
  reschedule-flow,review-form}`. Full lifecycle: **reschedule** (calendar pinned
  to the booking's own resource + party size, atomic commit via
  `rescheduleBooking`, records `changeHistory`; CUTOFF_PASSED bubbles back to
  detail, SLOT_UNAVAILABLE refreshes and re-picks), **cancel** (confirm dialog on
  the shared `Modal`), and **review** (1–5 stars + note, completed only). Cutoff
  greys out actions client-side; the backend stays authority and its ApiError
  messages are shown verbatim. Added `formatBookingWhen` to `lib/format` (uses
  `endUtc − 1ms` so full-day spans don't read one day long).
- **2026-08-15 — Phase 8:** Tab 5 Account — `components/account/profile-form.tsx`
  edits display name / email / timezone through `updateUser` (Save enabled only
  when dirty + valid; changing timezone re-renders every stored instant in the
  new wall clock without touching state). Added a payment-method stub row and a
  help/version footer; the demo panel (vertical switch + reseed) stays as-is.
