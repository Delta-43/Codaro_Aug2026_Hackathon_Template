# frontend/ — Next.js UI

## Role

Next.js 14 + Tailwind (shadcn/ui per `Project_Summary.md`) UI, fully driven
by the config the backend serves at `GET /config`. See root
[CLAUDE.md](../CLAUDE.md) for the overall architecture and
[backend/CLAUDE.md](../backend/CLAUDE.md) for the API this talks to.

## Files

| File | Responsibility |
|------|-----------------|
| `lib/domain.tsx` | `fetchConfig()`, `<DomainProvider>`, `useDomain()`, `<Term>` |
| `lib/api.ts` | Typed client for `/resources` `/slots` `/bookings` (+ `/slots/occupancy`), plus `ApiError` |
| `lib/session.ts` | Remembers the claimed email in `localStorage` (identity only, no auth) |
| `lib/format.ts` | `formatSlotTime()` (UTC → viewer's timezone), `hoursUntil()` |
| `app/layout.tsx` | Wraps the app in `<DomainProvider>` |
| `app/page.tsx` | Landing page — resource showcase + email identify → `/dashboard` |
| `app/dashboard/page.tsx` | Customer dashboard — book, reschedule, cancel |

## Surfacing backend rule violations

`app/rules.py` rejections come back as HTTP 409 with a `detail` string.
`request()` in `lib/api.ts` unwraps that into an `ApiError`, so UI code should
catch `ApiError` and render `e.detail` verbatim rather than inventing its own
copy — the rule text follows the config, so hardcoding it would drift on pivot.

The dashboard *also* greys out cancel/reschedule client-side when the slot is
within `rules.cancellationWindowHours`. That's a hint, not the enforcement —
the backend stays the authority.

## Conventions

- **Every label goes through `<Term>` or `useDomain().copy`, never a
  hard-coded string.** e.g. `<Term term="resource" plural />`, not
  `"Resources"`.
- **Every limit/number comes from `useDomain().rules`,** never a literal
  (e.g. don't hardcode "24 hours" for cancellation — read
  `rules.cancellationWindowHours`).
- **No password auth.** "Login" is just identifying by email/userid — there
  is no password field or auth provider to wire up.
- Use `NEXT_PUBLIC_API_BASE` (see `.env.local.example`) for the backend URL,
  never a hardcoded `localhost:8000`.

## Required views (per README)

1. **Landing page** — showcase resources. *Built* (`app/page.tsx`): resource
   cards with an open-slot count, plus the identify form.
2. **Login / identify** — email or userid only. *Built* (on the landing page,
   backed by `lib/session.ts`).
3. **Customer dashboard** — view available slots, book, reschedule, cancel.
   *Built* (`app/dashboard/page.tsx`).
4. **Owner dashboard** — CRUD resources/slots, confirm/cancel bookings, view
   all bookings, per-item analytics. **Not built yet.** Note the backend is
   also incomplete here: there is no confirm endpoint and no analytics
   endpoint, and `status` only ever moves confirmed → cancelled/rescheduled.

Each of these should stay config-driven: e.g. the owner/customer split uses
`terms.admin` / `terms.client` for labeling, not hardcoded "Owner"/"Customer"
strings.

## Testing

Don't write tests in this directory. Stack/integration tests live in
`test/` and are owned by the `test-writer` agent — see
[test/CLAUDE.md](../test/CLAUDE.md).
