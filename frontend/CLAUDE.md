# frontend/ — Next.js UI

## Role

Next.js 14 (App Router) + Tailwind v4 + `react-aria-components` UI. The live app
is **`frontend/src/`**. See root [CLAUDE.md](../CLAUDE.md) for the architecture and
[backend/CLAUDE.md](../backend/CLAUDE.md) for the API this talks to.

The public marketing landing page is **not** here — it's the standalone
[landing/](../landing/CLAUDE.md) app, air-gapped from this one (no shared
imports). `frontend/`'s root `/` just redirects to `/login`; a visitor arrives
here only via `landing/`'s cross-origin link, exactly like a real embedder's
site would eventually reach this app.

**One exception, both directions**: `/login` reuses the landing page's
liquid-glass background (`SceneBackground`/`GlassPanel`), so
`src/components/landing/{scene-background,scroll-reveal,particles}.tsx` here
is a frozen copy of `landing/`'s originals (trimmed — `scroll-reveal.tsx`
here only exports `GlassPanel`, not the landing-only `useScrollMotion` hook).
Same deal for `src/config/buttons.ts` (`buttonFx`), which `landing/` also
keeps its own copy of. Neither direction is wired together — a design/behavior
fix to one copy needs the same fix applied to the other by hand. (This bit a
merge from `develop` once already: a login-page redesign there added the
`scene-background`/`scroll-reveal` imports after `landing/` had already moved
the originals out — see `docs/issues/97-...` — so if either side's copy looks
stale after a merge, check the other.)

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
| `src/app/docs/page.tsx` | Public **`domain.config.json` setup guide** (`/docs`), linked from `landing/`'s nav pill via a cross-origin link. Block-by-block: defaults, allowed values, per-service overrides. Defaults are quoted from `backend/app/config_schema.py` `DEFAULTS` (not from the prose docs) — re-check them when the schema changes |
| `src/components/docs/` | `DocShell` (sticky header + scroll-spy TOC) and the long-form prose primitives the page renders with |
| `src/app/layout.tsx` | Root layout — wraps the tree in `<AuthProvider>` |
| `src/app/(app)/layout.tsx` | `<AuthGate>` → `<AppProvider>` → `<AppShell>` (stays mounted across tabs) |
| `src/context/app-context.tsx` | Current user (`/me`), active vertical, locked-in provider/service/resource |
| `src/config/verticals.ts` | **Pure UI vocabulary** per vertical (nouns/verbs/categories/copy). No data/seed — that lives in the backend now |
| `src/lib/format.ts` | UTC → viewer-timezone formatting |
| `src/lib/geo.ts` | Haversine distance + formatting; origin and unit come from the pivot file via `setGeoSettings()` |

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
- **Distance origin and unit come from the config**, not a constant. `AppProvider`
  boot calls `getPivotConfig()` (one `/config` request, same round-trip count as
  the old tenancy-only call) and applies `location.origin` / `location.distanceUnit`
  through `setGeoSettings()`. `geo.ts` falls back to Warsaw/km only when `/config`
  is unreachable — never import a reference location as a constant again.
- **Every limit/number comes from the backend** (per-service rules on the
  `Service` object), never a literal.
- **Auth is Supabase Auth.** Use `useAuth()` / the Supabase client for
  email/password; never hand-roll a password flow. The `(app)` group is gated on
  a session; `getCurrentUser`/`updateUser` map to `/me`.
- Env: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` (see `.env.local.example`).
- **Theming** is `next-themes` (`attribute="class"`, `defaultTheme="system"`,
  `enableSystem`) mounted in `src/app/layout.tsx`; dark tokens live under `.dark`
  in `globals.css`. The Account tab's `appearance-picker.tsx` sets Light / Dark /
  Smart (`"system"`), both built on the shared `components/theme-toggle.tsx`
  (also used by the `/docs` header) — `landing/` keeps its own frozen copy of
  the latter (see `landing/CLAUDE.md`) since it's a separate app now. First
  load follows the OS `prefers-color-scheme` live (system default); flipping a
  toggle pins an explicit choice, which then persists.

## Views (per README)

1. **Login / sign-up** — `src/app/login/page.tsx` (Supabase Auth). *Built.*
2. **Search** (tab 1) — provider discovery: text/category/near, code entry + QR,
   follow, provider preview. *Built.*
3. **Provider** (tab 2) — locked-in provider's services + resources. *Built.*
4. **Calendar** (tab 3) — month-density heatmap + day/week availability, the
   multi-slot + party-size booking flow. *Built.*
5. **Bookings** (tab 4) — upcoming/past, detail, reschedule, cancel, review.
   *Built.*
6. **Account** (tab 5) — profile edit (`PATCH /me`), sign-out, **Appearance**
   theme toggle (Light / Dark / Smart), demo vertical-switch/reset. *Built.*
7. **Docs** — `/docs`, ungated like `privacy/`: how to set up
   `domain.config.json`, block by block (tenancy → capabilities → booking →
   pricing → payments → timing → location → optional → vocabulary), plus
   per-service overrides, applying an edit, and what the engine actually
   enforces today. *Built.*

Owner/admin self-service **is** built: an owner with no business gets the
create form (`components/business/create-business.tsx`), and each service in the
console carries its units + availability
(`components/business/service-resources.tsx`). Seeds are now a convenience, not
the only route to a working catalogue.

## Testing

Don't write tests here. Stack/integration tests live in `test/` and are owned by
the `test-writer` agent — see [test/CLAUDE.md](../test/CLAUDE.md).
