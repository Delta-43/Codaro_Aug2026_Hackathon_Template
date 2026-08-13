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
| `lib/api.ts` | Typed client for `/resources` `/slots` `/bookings` (+ `/slots/occupancy`) |
| `app/layout.tsx` | Wraps the app in `<DomainProvider>` |
| `app/page.tsx` | Landing page — currently just an occupancy list |

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

## Required views (per README — none built yet beyond the landing page)

1. **Landing page** — showcase resources (exists as a stub in `page.tsx`,
   needs an actual resource list, not just raw slot occupancy).
2. **Login / identify** — email or userid only, routes into one of:
3. **Customer dashboard** — view available slots, book, reschedule, cancel.
4. **Owner dashboard** — CRUD resources/slots, confirm/cancel bookings, view
   all bookings, per-item analytics.

Each of these should stay config-driven: e.g. the owner/customer split uses
`terms.admin` / `terms.client` for labeling, not hardcoded "Owner"/"Customer"
strings.

## Testing

Don't write tests in this directory. Stack/integration tests live in
`test/` and are owned by the `test-writer` agent — see
[test/CLAUDE.md](../test/CLAUDE.md).
