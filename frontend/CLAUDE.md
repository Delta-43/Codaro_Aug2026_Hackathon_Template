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
| `lib/api.ts` | Typed client for `/resources` `/slots` `/bookings` (+ `/slots/occupancy`, owner CRUD + `analytics`), plus `ApiError` |
| `lib/supabase.ts` | Browser Supabase client (`getSupabase()`, null when env unset) |
| `lib/auth.tsx` | `<AuthProvider>` / `useAuth()` — Supabase session + `role`/`isOwner`, `signIn`/`signUp`/`signOut`, `roleOf()` (replaces the retired `lib/session.ts`) |
| `app/login/page.tsx` | Email/password login + client sign-up; role-aware redirect (owner → `/owner`) |
| `app/owner/register/page.tsx` | Register as a professional — sign-up carrying the owner role |
| `lib/format.ts` | `formatSlotTime()` (UTC → viewer's timezone), `hoursUntil()` |
| `app/layout.tsx` | Wraps the app in `<DomainProvider>` |
| `app/page.tsx` | Landing page — resource showcase + email identify → `/dashboard` |
| `app/dashboard/page.tsx` | Customer dashboard — book, reschedule, cancel |
| `app/owner/page.tsx` | Owner dashboard — create resources/slots, per-resource analytics |

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
- **Auth is Supabase Auth** (added on this branch). Use the Supabase JS client
  for email/password sign-up + login, and attach the session's access token as
  `Authorization: Bearer <jwt>` on every backend call. Don't hand-roll a
  password flow. (Reverses the engine's original "no password auth" rule.)
- Use `NEXT_PUBLIC_API_BASE` (see `.env.local.example`) for the backend URL,
  never a hardcoded `localhost:8000`.

## Required views (per README)

1. **Landing page** — showcase resources. *Built* (`app/page.tsx`): resource
   cards with an open-slot count, plus the identify form.
2. **Login / sign-up** — Supabase Auth (email/password). *Built*
   (`app/login/page.tsx`): sign-in/sign-up toggle backed by `useAuth()`. The
   old landing-page email identify (`lib/session.ts`) has been retired. See
   **Auth** below.
3. **Customer dashboard** — view available slots, book, reschedule, cancel.
   *Built* (`app/dashboard/page.tsx`); now gated on an authenticated session and
   scoped to the verified user's email.
4. **Owner dashboard** — *Built* (`app/owner/page.tsx`): create
   `<Term>`-labelled resources (with config-driven `metaFields` inputs) and
   slots (`ends_at` derived from `slotDurationMinutes`, capacity defaulted
   from `maxBookingsPerSlot`), plus per-resource analytics (occupancy rate,
   bookings-by-status). Now **gated on the owner role** — a signed-in non-owner
   sees an access-denied panel; an anonymous visitor is sent to `/login`.
   Professionals sign up at `app/owner/register`. The backend owner API is
   complete — `confirm`, `analytics`, `PATCH`/`DELETE`, and the `actor` cancel
   override all exist. Editing/deleting existing rows from the UI is the
   remaining stretch: those endpoints exist, but the forms are create-only for
   now.

Each of these should stay config-driven: e.g. the owner/customer split uses
`terms.admin` / `terms.client` for labeling, not hardcoded "Owner"/"Customer"
strings.

## Auth (Supabase Auth)

Added on branch `16-auth-system`, replacing the email-only identity. Target:

- Use `@supabase/supabase-js` (or `@supabase/ssr`) with
  `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` for
  email/password sign-up + login; Supabase stores the session.
- In `lib/api.ts`, attach the session access token as
  `Authorization: Bearer <jwt>` on every backend call so the backend can verify
  the user.
- Gate `app/dashboard` (client) and `app/owner` (owner) on an authenticated
  session; owner-only UI checks the role from the session, still labelled via
  `terms.admin` / `terms.client` (no hardcoded "Owner"/"Customer").
- `lib/session.ts` (localStorage email) has been retired; the Supabase session
  is the source of truth via `useAuth()`.

### Roles

Roles are engine-neutral strings `"owner"` / `"client"` (see `EngineRole` in
`lib/auth.tsx`), labelled in the UI through `terms.admin` / `terms.client` —
never hardcoded "Owner"/"Customer". `roleOf(user)` reads the role, preferring
`app_metadata.role` (trusted, set server-side) and falling back to
`user_metadata.role` (what the professional sign-up sets via
`signUp(email, password, "owner")`). `useAuth()` exposes `role` and `isOwner`.

**Caveat:** `user_metadata` is self-asserted at sign-up, so until the backend
verifies the JWT and/or promotes the role into `app_metadata`, owner access is
**client-side gating only** — good enough to route the UI, not a security
boundary. The real enforcement is `require_owner` on the backend + RLS (see
backend/`supabase` CLAUDE.md).

Status: **client + professional (owner) sign-up implemented.** `<AuthProvider>`
wraps the app (`app/layout.tsx`); `lib/api.ts` attaches
`Authorization: Bearer <jwt>` on every request; `app/login` handles client
sign-in/sign-up with a role-aware redirect; `app/owner/register` creates owner
accounts; `app/dashboard` and `app/owner` are both gated (owner dashboard on the
owner role). Remaining: the backend must verify the JWT
(`require_user`/`require_owner`) and promote/validate the role — until then the
Bearer token is sent but the backend still trusts the body identity (see
backend/CLAUDE.md "Auth").

## Testing

Don't write tests in this directory. Stack/integration tests live in
`test/` and are owned by the `test-writer` agent — see
[test/CLAUDE.md](../test/CLAUDE.md).
