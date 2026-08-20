# 106 — Landing-page polish: dock lag, calendar symmetry, wordmark width, dual business CTA

Four small-but-visible issues left on the landing page.

## 1. Steps bar — hover felt laggy

`components/landing/dock.tsx` (the macOS-dock magnify under "How it works")
recomputed scale through React state: every `pointermove` did one `setState` on
the `Dock` **plus** one `setState` per `DockItem`, each with a layout read — so a
single cursor move triggered several re-renders and reflows. That's the lag.

Rewrote it to coalesce moves into a **single `requestAnimationFrame`** and push
updates through a ref-based subscription; each item writes its own `transform`
straight to the DOM. No React re-render happens on move. Same visual effect
(1.6× peak, 2D falloff, touch ignored), smooth tracking.

## 2. Calendar bar — asymmetric right side, plate jumped between modes

`components/landing/calendar-demo.tsx`. The left calendar column changed height a
lot between Month / Week / Day, so the plate resized and the right-hand "Booking
in three taps" manual floated to the top (asymmetric).

- Wrapped the three views in a fixed **`min-h-[22rem]`** box (the day list is the
  tallest view) → the plate is now a **constant height** in every mode.
- Grid is `md:items-center` → the manual sits **vertically centred** against the
  calendar, balanced in all three modes.

## 3. Giant ARBOR wordmark — now locked to the plate width

`components/landing/footer.tsx`. The closing wordmark used a viewport-relative
`clamp()` font-size, so its width drifted from the glass plates above it.

Replaced the `<span>` with **SVG text stretched to the full container width**
(`textLength` + `lengthAdjust="spacingAndGlyphs"`) inside the same
`max-w-4xl px-4` wrapper as the plates. The word now spans **exactly** the plate
width at any viewport (verified: 686px == footer plate 686px). Fade mask, theme
colour (`fill-black dark:fill-white`), hover nudge, and the `data-wordmark` hook
the particle field steers around are all preserved.

## 4. "Run a business?" — split into two paths (self-serve vs. concierge)

`components/landing/business-cta.tsx`. Researched the usual SaaS pattern: landing
CTAs commonly split **"start now" (self-serve)** from **"talk to us" (sales /
concierge)**. Applied that:

- **Set it up yourself** → `Start your business` routes to `/login/business`, with
  a **help window** (reuses `components/modal.tsx`) explaining the one
  `domain.config.json` file — what it controls, per-service overrides, repivot
  without a rewrite — and links to `/docs` and business sign-up.
- **Have us set it up** → `Talk to the founders` opens a **contact window** with a
  placeholder founders' address (`founders@arbor.build`, flagged as a demo
  address), a **copy button**, a prefilled **mailto** (subject + a "what to tell
  us" body template), and a checklist of what to send (business type, offering,
  rules, volume, launch date) plus a response-time note.

The concierge card carries an amber accent, echoing the gold "Business" chip used
elsewhere, so the two paths read as distinct at a glance.

## Verification (round 1)

- `npx tsc --noEmit` clean.
- Live (preview at 280px): dock magnifies + resets + ignores touch with no
  re-render storm; calendar plate constant across modes (spread 0px); wordmark
  width == plate width; both CTA modals open/close (Escape + overlay), help links
  to `/docs` + `/login/business`, contact mailto prefilled + copy works. No
  console errors.

## Round 2 — follow-up feedback

Reworked three of the four after review, plus a new nav bug.

### Calendar — made smaller / more symmetric
The 22rem reserved height made the calendar plate much taller than the short
3-step manual beside it. Swapped `min-h-[22rem]` for a fixed, compact
`h-[16rem] overflow-y-auto [scrollbar-gutter:stable]`: the default Month view
still shows in full, the taller Day list scrolls inside, the plate stays a
constant size across modes, and the calendar now reads as balanced against the
manual (`md:items-center`). Measured columns 364 vs 213px (was ~460 vs 213).

### Wordmark — reverted the stretch, kept the plate-width lock
The `textLength` stretch looked distorted. Rebuilt the SVG with a viewBox at the
word's **natural** proportions in Outfit (≈ 842 × 180 for "ARBOR" @ 800), no
`textLength`/`letterSpacing`, so `w-full` scales it up to the plate width
*uniformly* — big and responsive without any horizontal stretch. Verified it
spans the visible plate exactly (864px, left 168 / right 1032) at 1000px, height
185px, natural letterforms, no clip.

### "Run a business?" — professional, on-palette, symmetric
Dropped the amber accent entirely (grep: 0 `amber`). Two **identical-shape**
cards (icon badge → title → one line → one full-width button), hierarchy carried
by button weight (primary `Start your business` vs. outline `Talk to the
founders`), not colour. Card icon badges are now interactive — they scale + fill
primary on card hover (`group` + `group-hover:`). Moved the config-help into a
single shared ghost link under both cards, so neither card grows taller — cards
measure 268×399 each. Both modals also de-ambered to the primary palette.

### Nav bar — Login no longer jumps on resize (new)
At the width where the link strip starts to overflow, the `‹ ›` scroll chevrons
were mounted/unmounted, so the far-right Login button shifted ~36px — it looked
like it slid toward the edge as you resized. Now the chevron **slots are always
reserved** (they fade + disable via `opacity-0 pointer-events-none` when the
strip fits, with `aria-hidden`/`tabIndex=-1`), so the brand and Login keep their
positions across the overflow threshold. Verified Login's inset is a steady 1px
from the plate edge at 1200px (chevrons hidden) and 500px (chevrons shown),
symmetric with the brand's 1px, no overflow.

## Verification (round 2)

- `npx tsc --noEmit` clean; no console errors.
- Measured live at 500 / 1000 / 1200px (text tools): calendar constant 256px
  viewport + balanced columns; wordmark == plate width, natural, unclipped; CTA
  cards symmetric 268×399, 0 amber; nav Login steady 1px inset across the
  overflow threshold.

## Round 3 — follow-up feedback

### CTA — swap the two cards
"Have us set it up" (concierge) now sits **left**, "Set it up yourself"
(self-serve, primary) **right**. Verified order live.

### CTA — remove the separate helper plate, fold its info into the main plate
Dropped the "How Arbor is configured" ghost link and the whole `HelpWindow`
modal. The one-config-file explanation now lives in the section's own intro copy
("Arbor is one config file that sets your vocabulary, rules, pricing and look…"),
and the self-serve card references "that one config file". Cards stay equal
height without the shared helper (they already balance via `items-stretch` +
`flex-1` body). Removed now-unused `FileCog`/`BookOpen` imports.

### Nav — chevrons appeared on tablet/wide even with nothing to scroll
Round 2's "reserve the chevron slots" fix backfired: the reserved 56px shrank the
link strip enough to make it *self-overflow*, so the chevrons showed on tablet
widths where the links actually fit. Reworked them as **absolute overlays** at
the strip's edges (gradient fade) that only render when the strip can truly
scroll — they take no layout width, so no self-induced overflow, and the
brand/Login still never shift. Verified: 0 chevrons at 900px (fits), 2 absolute
overlays at 460px (scrolls), Login steady 1px inset in both.

### Right-side scroll spine — removed
The calendar viewport's `overflow-y-auto [scrollbar-gutter:stable]` was drawing a
visible scrollbar groove. Swapped for the repo's `no-scrollbar` utility (hides
the bar, keeps wheel/touch scroll) — consistent with the app-wide hidden
scrollbars. The page scrollbar itself was already hidden globally.

### Copy — stripped the em-dash "AI tell"
Removed every em dash (—) from **visible** landing copy (hero, how-it-works,
calendar, testimonials, docs-cta, business-cta, footer), rephrasing with commas /
colons / periods so it reads naturally. Compound hyphens (multi-slot, go-live)
left intact. Code comments untouched. `grep "—"` now shows only comment lines.

## Round 4 — calendar reimagined as a full-screen "interactive video"

Replaced `calendar-demo.tsx` with **`calendar-showcase.tsx`** (new
`CalendarShowcase`, wired into `page.tsx`; old file deleted). Inspired by Zoho
Bookings' product tour.

- **Full-screen pink stage.** The section is `min-h-screen` with its own
  theme-aware pink backdrop (a `color-mix(var(--primary) …)` flat tint plus a
  soft radial glow), so it reads pink in light mode and deep rose in dark, over
  the otherwise monochrome scene.
- **Autoplaying synthetic-cursor tour of the real calendar.** A pointer glides
  across the genuine `MonthView` / `WeekView` / `DayView`: clicks **Month** and
  sweeps the days (each lights up), switches to **Week** then **Day** lighting up
  slots, selects a slot on the real control, clicks the real **Book this slot**
  button, shows a **Booking confirmed** card, then the **"Book in three steps"**
  panel zooms up to fill the plate. Then it loops (~18s).
- **Drives real DOM, nothing faked.** The cursor targets view pills by
  `data-demo-view`, month cells by their `aria-label` date, and day rows tagged
  `data-demo-slot`; the "interaction" is the components' own selected/hover
  styling. Real users can click too (the handlers are wired).
- **Plays only in view, pauses out of view** (IntersectionObserver), and
  **falls back to a static Month calendar** under `prefers-reduced-motion`. The
  loop is a run-id-guarded async sequence that abandons cleanly on pause/unmount.

Verified live at 1280px: pink stage + "Live demo" badge + real calendar render;
sampled over 12s the views cycle `M→W→D` and the overlay opacity reaches `1.0`
for ~3.4s before looping; the synthetic cursor is present; the "Booking
confirmed" bar shows the real slot (09:00–10:00 Warsaw). `tsc` clean, no console
errors. Also stripped the em dash from the week-view empty placeholder is *not*
done (that's a shared app glyph, left as-is).

## Verification (round 3)

- `npx tsc --noEmit` clean; no console errors.
- Live (text tools + one zoom): CTA cards swapped, no helper button; nav 0
  chevrons at 900px / 2 absolute overlays at 460px with Login stable; calendar
  no visible scrollbar; visible copy has no em dashes.

## Round 4 — calendar reimagined as an interactive "video" (Zoho-inspired)

Replaced the static calendar section (`calendar-demo.tsx`, deleted) with
`calendar-showcase.tsx`: a full-screen, **pink** stage where a **synthetic
cursor auto-drives the real app calendar on a loop**.

- **Pink stage** — the section is `min-h-screen` with its own theme-aware pink
  background (`color-mix(primary, background)` flat tint + a soft radial glow),
  so it stands out from the monochrome scene behind the rest of the page.
- **Real calendar, not a mockup** — it renders the genuine `MonthView` /
  `WeekView` / `DayView` + a real `buttonVariants` booking button, fed static
  demo data. What visitors watch is exactly the app.
- **The loop** — a cancellable async state machine (guarded by a run id, paused
  via `IntersectionObserver` when off-screen, disabled under
  `prefers-reduced-motion`): click **Month** → sweep ~5 day cells (each lights up
  with the calendar's own hover styling) → **Week** → light up slots → **Day** →
  glide the times, select one (real selected ring) → click **Book this slot** →
  **Booking confirmed** card → the **"Book in three steps"** panel zooms up
  (`scale-90→100`, opacity) to **fill the whole screen** → resets and loops.
- **Cursor** targets real DOM: view pills by `data-demo-view`, month cells by
  their `aria-label` date, day rows tagged with `data-demo-slot`. The
  "interaction" is the components' own selected/hover classes — nothing faked.
- Everything is genuinely clickable by a real visitor too (the views' `onSelect`
  / `onPickDay` are wired), so it doubles as a playable calendar.

## Verification (round 4)

- `npx tsc --noEmit` clean; no console errors.
- Live at 760px (text tools + screenshots): pink stage renders; loop advances
  Month→Week→Day with the cursor moving and slots lighting up; "Book in three
  steps" overlay is a section child that fills the full screen (measured
  760×815 at full scale). Old two-column demo gone.

## Round 5 — calendar showcase, refined from "raw" to finished

Reworked `calendar-showcase.tsx` per nine points of feedback:

1. **Flat pink** — dropped the radial glow; the stage is now one flat
   theme-aware tint (`color-mix(var(--primary) 20%, var(--background))`), no
   effects. (Verified `background-image: none`.)
2. **No glass plate** — removed the `rounded-3xl border bg-card/85 shadow-xl
   backdrop-blur-md` card; the calendar sits plainly on the pink.
3. **Click to take over** — a real click on any control (view pill, slot,
   `Book this slot`) calls `takeOver()`: it bumps the run id, clears the timer,
   hides the cursor and stops the tour so the visitor drives. The synthetic
   tour drives state imperatively (never dispatches DOM clicks), so it never
   trips its own take-over. Leaving the section resets the flag; returning
   replays. (Verified: clicking Month stops the show, zooms back to scale 1,
   collapses the outro.)
4. **"Live demo" badge removed.**
5. **Sane cursor** — every `point()` skips a null target instead of parking at
   the corner, and a `waitFor()` poller waits for a just-swapped view to render
   before aiming (Week/Day slots, the tagged book-slot row, the book button).
   No more clicking things that aren't there yet.
6. **Example slots** — each demo day carries simple example times (09:00 open,
   11:00 partly booked, 13:00 full, 16:00 open) so Week/Day look lived-in.
7. **One-by-one reveal** — the three steps ease in staggered
   (`transition-delay 350 + i·500ms`, 800ms each), Apple-`/mac`-style, slow.
8. **Calendar stays, zooms out** — when the tour ends the calendar shrinks to
   `scale-[0.88]` and the steps reveal *under* it (a `grid-rows [0fr]→[1fr]`
   height animation), instead of a full-screen overlay replacing it. (Verified:
   calendar bottom 516px, steps top 652px — steps sit below; calendar still on
   screen.)
9. **No loop** — `run()` fires once per view entry; it replays only when the
   section leaves and re-enters view (IntersectionObserver).

## Verification (round 5)

- `npx tsc --noEmit` clean; no console errors.
- Live (text tools + one screenshot): flat pink (no gradient), badge gone, no
  glass classes; tour runs Month→Week→Day and books on the real control
  (`Booking confirmed`); ends zoomed to 0.88 with all three steps at opacity 1
  underneath; clicking a pill hands control to the visitor.

## Round 6 — the calendar "in a real plate", and no phantom clicks

Follow-up tightening after round 5 read as still-raw:

- **Normal plate restored.** The calendar sits in a plain card again
  (`rounded-2xl border border-border bg-card p-4 shadow-sm`), like the real app,
  instead of floating unbounded on the pink. `max-w-2xl → max-w-md` and the
  views box `19rem → 15rem`, so the whole thing is noticeably smaller.
- **Steps show on direct interaction too.** The reveal is now driven by
  `revealed = finished || takenOver`: whether the tour finishes *or* a visitor
  clicks in, the calendar zooms out and the three-step note appears. (Previously
  a take-over hid the steps.)
- **No cut-off.** Steps are a compact three-column row (`sm:grid-cols-3`,
  smaller type, bordered cells) and the section padding shrank, so calendar +
  steps fit the viewport. Measured at 1200×840: steps bottom 737 ≤ 840.
- **Cursor only ever clicks things that exist.** `point()` now bails on a
  disconnected node (`el.isConnected`) before moving/clicking, and the booking
  tail is strictly gated: the slot is selected only if its row is really present,
  and the confirm fires only after the real `Book this slot` button has appeared
  and been clicked — the button only exists once a slot is picked, so the cursor
  can't click it early, and the confirmation is never faked.
- **Snappier.** Trimmed per-move settle and sweep counts (~20s → ~14s).

## Verification (round 6)

- `npx tsc --noEmit` clean; no console errors.
- Live at 1200×840 (text tools + one screenshot): calendar in a `bg-card` plate,
  smaller; auto-tour books on the real button (`Booking confirmed`); ends at
  scale 0.9 with all three steps opacity 1 and fully on-screen (bottom 737).
  Clicking a pill mid-tour stops it, hides the cursor, zooms out, reveals the
  steps, and the visitor can then pick a slot and reach a confirmed booking.

## Round 7 — back on glass, over the real backdrop; vertical steps that fit

- **Background restored.** Dropped the flat-pink stage `<div>`; the section is
  transparent again so the shared `SceneBackground` (neutral white/black base +
  monochrome particle field) shows through, matching the rest of the page.
- **On a liquid-glass plate.** The calendar and the three-step note now live on
  one `GlassPanel` (`max-w-2xl`), the same frosted material as the other
  chapters, instead of floating loose. The calendar sits directly on the glass
  (no inner card chrome) and zooms toward its top (`scale-[0.92]`) on finish, so
  the steps get room without the plate growing much.
- **No corner wander.** The synthetic cursor's targeting was folded into a single
  `aimAt()` guard: it only moves to a real, still-mounted, non-disabled element
  whose centre falls **inside the calendar plate**. A missing/off-plate/zero-size
  target is skipped and the cursor stays put (hidden until the first genuine
  target), so it can never drift to an empty corner.
- **Steps stack vertically.** The three-step list is a `flex-col` column now
  (was a 3-col grid), each line easing in one after another.
- **Fits the viewport.** Shorter view area (`13rem`), compact vertical steps, and
  the top-origin zoom keep the whole plate on screen.

## Verification (round 7)

- `npx tsc --noEmit` clean.
- Live at 1200×840 (text tools + one screenshot): glass plate present
  (`.liquid-glass`, width 672, centred) over the particle backdrop; auto-tour
  ends at calendar `scale 0.92` with `Booking confirmed`; three steps stacked
  vertically (same left, increasing top), all opacity 1; plate spans 67→773,
  last step bottom 740, all within the 840 viewport (no overflow).

### Round 7 follow-up — exact plate width + whole month visible

- Plate widened from `max-w-2xl` to `max-w-4xl` so it matches the other chapters
  exactly (measured 896px == the "How it works" plate). Padding aligned to the
  chapter norm (`px-6 py-10 sm:px-10 sm:py-12`). The calendar keeps a `max-w-md`
  body centred on the wider plate.
- Dropped the `h-[13rem]` scroll box on the views container (now `min-h-[13rem]`)
  so the Month grid renders in full — the whole calendar (all week rows + the
  Openness legend) is visible while the cursor sweeps it, instead of being
  clipped. Verified live: views 431px unclipped, legend within the plate, plate
  bottom 759 ≤ 840.

### Round 8 follow-up — steps beside the calendar, so it fits one screen

The plate had enough horizontal room (`max-w-4xl`) but the steps still revealed
*below* the calendar, so Month view or the finished state overflowed the fold.
Fix: spend the plate's width, not its height.

- The GlassPanel body is now a flex row (`sm:flex-row`): the tour plays on the
  calendar (left, `max-w-sm`); the "Book in three steps" note reveals to the
  **right** on wide screens and **below** on mobile.
- Reveal is a grid trick in the right direction per breakpoint —
  `grid-cols-[0fr]→[1fr]` (horizontal) on `sm`, `grid-rows-[0fr]→[1fr]`
  (vertical) on mobile. The three steps still stack vertically inside their
  column.
- Trimmed panel padding to `py-8 sm:py-10`.

Verified live at 1200×840: finished state (Day + steps) bottom 660; worst case
(Month + steps, via a real Month click) bottom 798 ≤ 840 — fits with headroom.
Steps sit to the right of the calendar (steps left 672 > calendar right 628).
`tsc --noEmit` clean.

### Round 9 — steps back under the calendar: wide, interactive, bouncing arrow

Reverted the side-by-side layout back to steps stacked **under** the calendar,
per request, and made them fit the plate properly:

- **Interactive plates.** Added a `plate` role to `src/config/buttons.ts`
  (`buttonFx.plate` — gentle centre grow + soft primary tint/border on hover)
  and applied it to each step card, so hovering a plate zooms and tints it,
  matching the platform's config-driven interactivity convention.
- **Full-width plates.** The step cards now span ~the full inner width of the
  liquid-glass plate (measured 830px), so text has room and nothing crowds or
  overlaps.
- **Bouncing arrow.** A down-pointing `ChevronDown` (`animate-bounce`,
  primary-tinted) reveals under the "Book in three steps" heading.
- **Still fits one screen.** Stacking under is taller, so the calendar was
  trimmed to `max-w-[20rem]`, panel padding to `py-6 sm:py-8`, section padding to
  `py-6`, and the step rows tightened. Verified live at 1200×840: Day+steps panel
  733px; worst case Month+steps 816px with bottom exactly at the 840 fold — the
  whole month stays visible and nothing leaks. `tsc --noEmit` clean.

### Round 10 — symmetrical centered step plates + fit-to-screen plate

- **Step plates sized to the sentence.** The three plates are now capped at
  `max-w-lg` (512px) and centered (`mx-auto`) instead of spanning the whole
  plate — just wider than the longest step line ("Open days are highlighted, and
  the dots show how open each one is.") plus its number icon, so all three
  sentences sit on one line and the block reads symmetrical. Verified live: ol
  512px, centered, every body one line.
- **Fit-to-screen plate.** The page snap-scrolls, so a plate taller than the
  viewport couldn't be scrolled into full view and got cut on short screens. Added
  a fit transform: a `ResizeObserver` measures the plate's natural height and
  scales it down only when it wouldn't fit (`scale = clamp(0.55, avail/natural,
  1)`), collapsing the wrapper to the scaled height. The synthetic-cursor
  `aimAt` divides screen distances by the scale so it still tracks. Removed the
  section's `overflow-hidden` and used `[justify-content:safe_center]`.
  - Verified: 900px tall → scale 1, calendar glass **896px = the How-it-works
    plate (896px)**, same width as the other chapters; 680px tall → scales to
    0.77, panel fully visible (top 28, bottom 652 ≤ 680), nothing clipped.
    `tsc --noEmit` clean.

### Round 11 — trim the calendar plate + equalise Month mode height

- **Shorter plate:** `GlassPanel` vertical padding `py-6 sm:py-8` → `py-4 sm:py-6`,
  shaving ~16px top+bottom across every mode.
- **Month mode no longer towers:** the month grid's cells are `aspect-square`, so
  a full-width month (320px) was 321px tall — ~83px taller than Week/Day. Wrapped
  `MonthView` in `mx-auto max-w-[13.5rem]`; the narrower grid is a shorter grid, so
  the views area drops to 236px and the whole plate is 396px vs Day's 398px —
  matched. It's real layout (not a transform), so the tour's synthetic cursor still
  aims correctly at month day cells.

Verified live (DOM heights): Month plate 396px, Day 398px, Week 368px (Week floored
by the container `min-h`, unchanged and not in scope). `tsc --noEmit` clean; config
validator ✓; backend suite 1105 passed / 1 skipped.
