# 81 — Adding a footer (and a landing-page pass)

Adds a real footer to the landing page, moves the theme toggle into it, rebrands
the product to **Arbor**, simplifies the background, and unifies the glass so
every plate frosts the backdrop the same way as the footer.

## What changed & why

### Footer (`components/landing/footer.tsx`)
- Replaced the one-line pink credit with a full **footer bar** on the shared
  `GlassPanel`: a big centered **Leaf** indicator icon (like the other plates),
  brand name + pitch on the left, the site's real links in two columns on the
  right (**Explore**: How it works / Calendar / Reviews / Docs · **More**:
  Login/Open app · **Data handling & privacy policy** → `/privacy`), and a
  bottom row with the interactive `© Arbor` credit + the day/night toggle.
- Only real routes/anchors — no filler columns.
- Giant **ARBOR** wordmark below the bar, fading **top→bottom** (transparent at
  the top, solid at the very bottom edge) via a mask gradient; black in light
  mode, white in dark. Interactive on hover.

### Theme
- Toggle **moved out of the nav** into the footer; its text label dropped
  (icon only).
- `layout.tsx`: `defaultTheme` `light → system`, so the page follows the OS
  light/dark setting until a toggle pins an explicit choice.

### Rebrand → Arbor
- `service.com` → **Arbor** everywhere on the landing surface: hero wordmark,
  closing CTA, browser tab title (`layout.tsx` metadata), and the four
  testimonial mentions. Nav shows the plain **Arbor** name (no icon).

### Background (`components/landing/scene-background.tsx`)
- Removed the colored gradient + blooms and the pink petals. Now a plain
  **black/white** base (white light / black dark) with slow **monochrome**
  flecks spread over the full height — a neutral texture for the glass to blur,
  no color.

### Glass unification (`components/landing/scroll-reveal.tsx`)
- `GlassPanel` simplified to the footer's clean treatment (dropped the diagonal
  sheen + inner-bevel shadows; added `overflow-hidden`); the footer now uses
  `GlassPanel` too.
- **Removed the `useScrollMotion` opacity dimming.** Applying `opacity`/
  `willChange` to a plate's wrapper forced it into an isolated compositing
  group, which changed how its `backdrop-filter` sampled the page behind it — so
  those plates frosted the background more weakly than the footer (which never
  dimmed). The hook is now inert (returns a ref only), so every plate renders at
  full opacity and frosts the backdrop identically to the footer.
  **Tradeoff:** the scroll-focus fade is gone.

### Indicator icons
- Added big centered interactive icon badges to the plates that lacked them —
  **How it works** (Zap), **Calendar** (CalendarDays), **Reviews** (Quote) —
  matching Docs/Business. Only the hero (first plate) has none.

### Scroll-chevron rule
- The **Reviews** left/right chevrons now follow the nav's rule: each dims +
  disables (`opacity-25`) when there's nothing left to scroll that way
  (`atStart`/`atEnd` via a scroll + `ResizeObserver` listener), and the nudge
  animation only plays on the scrollable side.
- The **nav** chevrons got the same nudge-on-the-scrollable-side treatment.

## Verification
- `python .github/scripts/validate_domain_config.py` → `✓ domain.config.json`
- `python -m pytest test -q` → **1017 passed, 8 skipped** (skips are live-API
  e2e tests needing a server on :8000).
- Frontend: `npm ci` ✓ · `npx tsc --noEmit` ✓ · `npm run build` ✓.

## Notes / follow-ups
- Testimonial quotes were rewritten `service.com → Arbor`; they're credited by
  name, so teammates may want a heads-up.
- Brand mentions outside the frontend (backend seed data, docs, READMEs) still
  say service.com — not user-facing on the landing page; a repo-wide sweep is a
  separate task if wanted.
- The `useScrollMotion` scroll-focus fade can be reinstated without touching the
  glass (animate a child's opacity, or a transform that doesn't trigger backdrop
  isolation) if the effect is missed.
