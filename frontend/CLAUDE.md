# frontend/ — Next.js UI

## Role

Next.js 14 (App Router) + Tailwind v4 + `react-aria-components` UI. The live app
is **`frontend/src/`**. See root [CLAUDE.md](../CLAUDE.md) for the architecture and
[backend/CLAUDE.md](../backend/CLAUDE.md) for the API this talks to.

The public marketing landing page **lives here now**: `src/app/page.tsx` is the
landing page, served at the app root `/`, built from `src/components/landing/*`
(hero, nav-bar, how-it-works, calendar-showcase, testimonials, docs-cta,
business-cta, footer, plus the shared scene/scroll primitives). It sits outside
the gated `(app)` group and uses no auth/context — its CTAs are plain same-origin
`next/link`s to `/login`, `/docs`, and `/privacy`. (It was briefly split out into
a standalone `landing/` app; that split has been reverted and the page folded
back in — `/login` and the landing page share `SceneBackground`/`GlassPanel`
directly again, no frozen copies.)

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
| `src/lib/auth.tsx` | `<AuthProvider>` / `useAuth()` — session + `role`/`isOwner`/`roleReady` (resolved via the seam's `getMyRole`), `signIn`/`signUp`/`signOut`; `getAccessToken()` for the seam's Bearer header |
| `src/components/auth-gate.tsx` | Redirects anonymous visitors to `/login`; holds the app until a session exists |
| `src/app/login/page.tsx` | **Customer** portal — email/password sign-in + sign-up (Supabase Auth) |
| `src/app/login/business/page.tsx` | **Business** portal — same form, business branding; accepts any account |
| `src/app/docs/page.tsx` | Public **`domain.config.json` setup guide** (`/docs`), linked from the landing page's nav pill. Block-by-block: defaults, allowed values, per-service overrides. Defaults are quoted from `backend/app/config_schema.py` `DEFAULTS` (not from the prose docs) — re-check them when the schema changes |
| `src/components/docs/` | `DocShell` (sticky header + scroll-spy TOC) and the long-form prose primitives the page renders with |
| `src/app/layout.tsx` | Root layout — wraps the tree in `<AuthProvider>` |
| `src/app/(app)/layout.tsx` | `<AuthGate>` → `<AppProvider>` → `<AppShell>` (stays mounted across tabs) |
| `src/context/app-context.tsx` | Current user (`/me`), active vertical, locked-in provider/service/resource |
| `src/config/verticals.ts` | **Pure UI vocabulary** per vertical (nouns/verbs/categories/copy). No data/seed — that lives in the backend now |
| `src/components/ui/inline-message.tsx` | `<InlineMessage>` — every inline error/notice: entrance animation, remount-on-change, `role="alert"`/`"status"` |
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

**Render them through `<InlineMessage>`**, never a hand-rolled `<p
className="bg-destructive/10 …">`. The class string was copy-pasted at seven
call sites and had already drifted (three were missing `role="alert"`, rounding
and borders disagreed). The component also owns two behaviours that are easy to
miss and jarring when absent: a short fade+slide so the message doesn't snap in
and shove the layout down unannounced, and a remount keyed on the message text —
without it React reuses the node, so a *second, different* rejection swaps
silently under a motionless element and the user sees nothing happen. Pass
`tone="notice"` for "it worked, but not the way you meant"; spacing and rounding
stay overridable via `className`.

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
- **Either login portal accepts either account.** `/login` and
  `/login/business` are two doors to one system, not two account systems:
  whichever you use, you land at your role's home — `/owner` for a business, the
  customer app otherwise. `/login/business` is a branded entrance. Don't add a
  per-portal refusal: it stopped valid credentials at one URL while the same
  person reached the same app by typing another, which is friction without a
  boundary. The real boundary is `owner/layout.tsx` + `require_owner` on the
  API — the *console* is role-gated, while the `(app)` group gates on a session
  only and the backend lets an owner hold bookings (`POST /bookings` is
  `require_user`). So a business account can use the customer app by URL; there
  is deliberately no UI affordance pointing there.
- **Never read the role off the JWT.** `useAuth().role` / `.isOwner` come from
  `GET /me/role`, which the backend resolves from `profiles` — the same value
  the API gates on. `user_metadata.role` is writable by the user
  (`supabase.auth.updateUser`), so deriving the role from the token let a
  customer open the whole business UI while every request inside it 403'd, and
  hid business mode from anyone an admin promoted the documented way. Anything
  that *routes* on the role must also wait for **`roleReady`** — the role lands a
  beat after the session, and reading the interim value as "not an owner" bounces
  a business out of business mode on every page load.
- Env: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY` (see `.env.local.example`).
- **Interactivity is config-driven** — the hover/press "feel" of every button,
  card, row, chevron, star, heading and clickable icon comes from
  `src/config/buttons.ts` (`buttonFx`), not from inline `hover:scale…` strings.
  Any new/changed interactive element must pull a `buttonFx` token (add a new
  role there if none fits); never re-invent the feel at the call site. Full rule
  + the token table: [docs/interactivity.md](../docs/interactivity.md). (`<Button>`
  already bakes in `buttonFx.press`.)
- **Theming** is `next-themes` (`attribute="class"`, `defaultTheme="system"`,
  `enableSystem`) mounted in `src/app/layout.tsx`; dark tokens live under `.dark`
  in `globals.css`. The Account tab's `appearance-picker.tsx` sets Light / Dark /
  Smart (`"system"`), both built on the shared `components/theme-toggle.tsx`
  (also used by the `/docs` header and the landing page footer). First
  load follows the OS `prefers-color-scheme` live (system default); flipping a
  toggle pins an explicit choice, which then persists.

## Views (per the root `CLAUDE.md`)

1. **Login / sign-up** — `src/app/login/page.tsx` (Supabase Auth). *Built.*
2. **Search** (tab 1) — provider discovery: text/category/near, code entry + QR,
   follow, provider preview. *Built.*
3. **Provider** (tab 2) — locked-in provider's services + resources. *Built.*
4. **Calendar** (tab 3) — month-density heatmap + day/week availability, the
   multi-slot + party-size booking flow. *Built.*
5. **Bookings** (tab 4) — upcoming/past, detail, reschedule, cancel, review.
   *Built.*
6. **Account** (tab 5) — profile edit (`PATCH /me`), sign-out, **Appearance**
   theme toggle (Light / Dark / Smart). *Built.*
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
