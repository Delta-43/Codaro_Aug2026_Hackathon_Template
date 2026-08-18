# 73 — Fixing the landing page

Polish pass on the marketing landing page: real macOS-style "liquid glass"
plates, a cleaner backdrop, a smarter nav bar, and a batch of responsive /
scroll bugs.

## What changed

**Liquid-glass plates (`scroll-reveal.tsx`, `scene-background.tsx`)**
- Reworked toward a macOS-Tahoe-style liquid glass: an SVG `feTurbulence` +
  `feDisplacementMap` filter referenced from `backdrop-filter: url(#…)`, plus a
  beveled rim and layered highlights.
- **Known limitation:** no current browser (Chromium, Safari, Firefox) actually
  renders an `url()` SVG filter inside `backdrop-filter` — the property is
  limited to the built-in filter functions — so the live displacement/refraction
  does **not** render; every browser falls back to the `-webkit-backdrop-filter`
  blur + the bevel/sheen. The plates therefore read as high-quality frosted
  glass, not true real-time refraction. Genuine refraction would need a
  different approach (e.g. an SVG/WebGL layer over a captured snapshot).
- Beveled depth via a bright rim, a diagonal specular sheen, a top-edge
  highlight, and layered inner highlight/shadow — glass, not a card.
- `GlassPanel` now applies the caller's layout classes to the inner content box
  (not the root), fixing content (terminal, step icons) that had stopped
  centering.

**Backdrop (`scene-background.tsx`)**
- Removed the background photo and the aurora effect entirely. Replaced with a
  soft theme-aware gradient, three blurred colour blooms for the glass to bend,
  and gently drifting petals. All motion is pure CSS, off under
  `prefers-reduced-motion`.

**Nav bar (`nav-bar.tsx`)**
- Dropped the `service.com` brand wordmark from the bar.
- Theme toggle pinned far-left, Login pinned far-right, section links in a
  scrollable middle strip laid out `justify-evenly` so they're mirror-symmetric
  toward the toggle and Login (no centre void, no dead space).
- Width-aware `‹ ›` chevrons: a `ResizeObserver` measures the strip live and
  shows the chevrons only when the links actually overflow, dimming whichever
  end you've reached. In-flow beside the strip, so they never overlap a link.

**Scroll behaviour (`scroll-reveal.tsx` + `snap-always` on the section files)**
- Removed the mid-scroll blur — panels only dim slightly as they leave centre,
  so all copy stays legible. Wider dead-zone keeps the panel you're on crisp.
- `snap-start snap-always` on every chapter so a scroll commits fully to the
  next panel instead of parking you between two.

**Step icons on mobile (`dock.tsx`, `how-it-works.tsx`)**
- The dock magnify now ignores non-mouse pointers (`pointerType`), fixing icons
  that stuck enlarged after a touch.
- Uses 2D distance (`Math.hypot`) so a hover scales only the nearest icon, not
  the whole stacked column on narrow screens.

**Hero / calendar (`hero.tsx`, `calendar-demo.tsx`)**
- `service.com` wordmark: all-pink, mid-size, with a subtle hover scale.
- "Booking, in three taps" heading centred on the calendar panel.
- Calendar card gets `min-w-0 overflow-x-auto` so its content is fully visible
  (no right-edge cut-off) at small widths.

## Verified
- `npx tsc --noEmit` clean; container recompiles clean.
- Frontend-only change; no backend/schema/config touched.
