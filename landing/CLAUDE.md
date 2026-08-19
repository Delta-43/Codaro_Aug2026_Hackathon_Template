# landing/ — public marketing site

## Role

Next.js 14 + Tailwind v4, the same stack as `frontend/`, but a **separate
deployable app** — its own `package.json`/build/container, zero imports from
`frontend/src`. Pitches the engine/product; the one thing it does that
touches "the app" is a plain cross-origin `<a>` link to
`${NEXT_PUBLIC_APP_URL}/login` (also `/docs`, `/privacy`) — no shared code,
no shared session, no iframe. See root [CLAUDE.md](../CLAUDE.md) for why this
split exists.

## Why air-gapped

Before this split, the landing page lived inside `frontend/src/app/page.tsx`
and imported `useAuth()`/`getTenancy()` directly. That coupling meant landing
redesigns and app-internal changes could touch the same files, causing
avoidable merge conflicts. Now they can't: `landing/` has no file overlap
with `frontend/` at all. The button-click integration point this app relies
on (`<a href="${NEXT_PUBLIC_APP_URL}/login">`) is deliberately the simplest
possible one — a real embedder's site would use exactly this same pattern.

## What's here vs. what's copied

- **Moved from `frontend/`** (this is now the only copy): `src/app/page.tsx`,
  `src/components/landing/*`.
- **Copied from `frontend/`, frozen on purpose** — pure/presentational, no
  auth/context/data dependency, confirmed before copying:
  - `src/components/calendar/{month-view,week-view,day-view,slot-pill}.tsx` —
    feed the `CalendarDemo` section static demo data; this is a visual demo,
    not a live view, so it doesn't need to track the real app calendar's
    evolution file-for-file.
  - `src/components/theme-toggle.tsx`, `src/components/ui/button.tsx`
  - `src/lib/{calendar,format,utils}.ts`, `src/types/domain.ts`
  - `src/config/buttons.ts` (`buttonFx`) — the shared button-interactivity
    tokens; the landing CTAs (`hero.tsx`, `business-cta.tsx`, `docs-cta.tsx`,
    `nav-bar.tsx`) read it the same way `frontend/`'s do.

  **Don't re-couple these to `frontend/`** (a shared package, a monorepo
  workspace reference, etc.) — that would recreate the exact shared-file
  conflict surface this split was built to remove. If a real behavior fix is
  needed here, apply it here; it doesn't need to round-trip into `frontend/`.

  **The reverse copy exists too**: `frontend/src/components/landing/{scene-background,scroll-reveal,particles}.tsx`
  is a frozen copy in the other direction, kept there because `/login` reuses
  the same liquid-glass background. See `frontend/CLAUDE.md`'s note on this —
  when either side's copy gets a real design/behavior fix, check whether the
  other side's copy needs the same fix by hand; nothing wires them together
  automatically.

## No auth, ever

`landing/` has no `AuthProvider`, no Supabase client, no session. It cannot
know whether a visitor is signed in on `frontend/`'s origin — so every CTA
always renders its logged-out copy ("Login" / "Get Started" / "Sign in"),
even for a returning, already-signed-in visitor. This is deliberate, not a
bug: it's the same thing any real third-party site embedding a link to this
engine would see.

## Env

`NEXT_PUBLIC_APP_URL` — the deployed app's origin. Every cross-origin link in
`components/landing/*` (`nav-bar.tsx`, `hero.tsx`, `business-cta.tsx`,
`docs-cta.tsx`, `footer.tsx`) reads it. Local dev: `http://localhost:3000`.

## Testing

Don't write tests here without checking with whoever owns `test/` first —
same convention as `frontend/`, see [test/CLAUDE.md](../test/CLAUDE.md).
