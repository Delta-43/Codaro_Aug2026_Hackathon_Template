# frontend/ — Next.js UI

## Role

Next.js 14 (App Router) + Tailwind v4 + `react-aria-components` UI. The live app
is **`frontend/src/`**; the earlier prototype (`app/`, `lib/domain.tsx`,
`lib/api.ts`, `lib/auth.tsx`, `app/dashboard`, `app/owner`) is retired under
`frontend/_legacy/`. See root [CLAUDE.md](../CLAUDE.md) for the architecture and
[backend/CLAUDE.md](../backend/CLAUDE.md) for the API this talks to.

## Domain + files

The app models `Provider → Service → Resource → Slot → Booking → User`
(`src/types/domain.ts`, camelCase, UTC-`Z` timestamps — the exact shapes the
backend returns). Five tabs under the gated `(app)` group: **search / provider /
calendar / bookings / account**.

| File | Responsibility |
|------|-----------------|
| `src/api/index.ts` | **The API seam** — real HTTP to the backend for every domain call; attaches the Bearer token, returns the `domain.ts` shapes, throws `ApiError` |
| `src/api/errors.ts` | `ApiError` + the `ApiErrorCode` union (mirrors `backend/app/errors.py`) |
| `src/lib/supabase.ts` | Browser Supabase client (`getSupabase()`, null when env unset) |
| `src/lib/auth.tsx` | `<AuthProvider>` / `useAuth()` — session + `role`/`isOwner`, `signIn`/`signUp`/`signOut`; `getAccessToken()` for the seam's Bearer header |
| `src/components/auth-gate.tsx` | Redirects anonymous visitors to `/login`; holds the app until a session exists |
| `src/app/login/page.tsx` | Email/password sign-in + sign-up (Supabase Auth) |
| `src/app/layout.tsx` | Root layout — wraps the tree in `<AuthProvider>` |
| `src/app/(app)/layout.tsx` | `<AuthGate>` → `<AppProvider>` → `<AppShell>` (stays mounted across tabs) |
| `src/context/app-context.tsx` | Current user (`/me`), active vertical, locked-in provider/service/resource |
| `src/config/verticals.ts` | **Pure UI vocabulary** per vertical (nouns/verbs/categories/copy). No data/seed — that lives in the backend now |
| `src/lib/format.ts` | UTC → viewer-timezone formatting |

## The API seam (`src/api/index.ts`)

Every component/hook/page goes through the seam; none touch transport. Each call:
- attaches `Authorization: Bearer <jwt>` from the Supabase session
  (`getAccessToken()`), so the backend derives identity + RLS scope from the
  token, never the body;
- targets `NEXT_PUBLIC_API_BASE` (never a hardcoded `localhost:8000`);
- returns the exact `domain.ts` shape and **throws `ApiError`** built from the
  backend's `{code, message, details}` envelope — so UI error handling (inline
  "slot was just taken", disabled-with-reason, retry) is unchanged.

The mock (`mockStore.ts`, `latency.ts`, `storeTypes.ts`, `seed/*`) has been
**deleted**; the backend is the only source of data.

## Surfacing backend rule violations

Backend rejections come back as `ApiError` with a `code`
(`SLOT_UNAVAILABLE` / `CAPACITY_EXCEEDED` / `CUTOFF_PASSED` / `INVALID_RANGE` /
`NOT_FOUND`) and a `message`. UI code catches `ApiError` and renders `e.message`
verbatim (the copy pivots with the domain server-side); only the booking/
reschedule flows special-case the codes for re-pick / disabled-with-reason.

## Conventions

- **Every label goes through the vertical config / domain copy**, never a
  hardcoded string (e.g. `useVertical().resourceNoun`, not `"Vehicle"`).
- **Every limit/number comes from the backend** (per-service rules on the
  `Service` object), never a literal.
- **Auth is Supabase Auth.** Use `useAuth()` / the Supabase client for
  email/password; never hand-roll a password flow. The `(app)` group is gated on
  a session; `getCurrentUser`/`updateUser` map to `/me`.
- Env: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` (see `.env.local.example`).

## Views (per README)

1. **Login / sign-up** — `src/app/login/page.tsx` (Supabase Auth). *Built.*
2. **Search** (tab 1) — provider discovery: text/category/near, code entry + QR,
   follow, provider preview. *Built.*
3. **Provider** (tab 2) — locked-in provider's services + resources. *Built.*
4. **Calendar** (tab 3) — month-density heatmap + day/week availability, the
   multi-slot + party-size booking flow. *Built.*
5. **Bookings** (tab 4) — upcoming/past, detail, reschedule, cancel, review.
   *Built.*
6. **Account** (tab 5) — profile edit (`PATCH /me`), sign-out, demo
   vertical-switch/reset. *Built.*

Owner/admin self-service (creating providers/services from the UI) is not built —
seeds populate catalog data; see `TODO.md`.

## Testing

Don't write tests here. Stack/integration tests live in `test/` and are owned by
the `test-writer` agent — see [test/CLAUDE.md](../test/CLAUDE.md).
