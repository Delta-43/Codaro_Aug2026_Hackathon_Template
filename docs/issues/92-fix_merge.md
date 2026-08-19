# 92 — Fix broken merge on the landing page

A colleague's merge (PR #88 / issue 77 landing on top of #89 / issue 81)
reintroduced regressions on the landing page. This restores the intended
look from issue 81 and fixes the wordmark/particle interaction.

## What changed

**`scene-background.tsx` — liquid glass restored.**
The glass CSS was never touched; what broke it was the *substrate* it
refracts. PR #88 put colored bloom `div`s (primary/pink/sky gradients)
behind the glass, and `.liquid-glass`'s `saturate(180%)` amplified those
tints into muddy frost. Removed the three bloom divs, leaving the neutral
`bg-white dark:bg-black` base + the monochrome particle field — so the
plates frost clean, as in #81. The `.liquid-glass` rule and the
`#liquid-glass-distortion` filter are byte-for-byte unchanged.

**`particles.tsx` — wordmark no longer buried under particles.**
Rather than give the ARBOR wordmark its own z-layer, the particle field
now *migrates out of its way*. The field normally gathers in the lower
half of the viewport; when the wordmark scrolls into view (bottom of the
page, detected via `[data-wordmark]` `getBoundingClientRect`), every dot's
vertical spring target flips to an **independent upper-half rest spot**
(`restYUp`), so the whole field glides up and clears the footer/wordmark,
then glides back down when you scroll away.

Two refinements make the migration read as organic rather than mechanical:
- **Per-dot spring rate `ky`** (`0.0009 + rand*0.0025`) instead of one
  shared constant, so dots travel at their own pace and the field never
  moves as a rigid sheet (no visible sweeping line).
- **`restYUp` is drawn independently**, not reflected from `restY`. A
  reflection (`H - restY`) has a fixed point at `H/2`, which pinned any
  mid-resting dot to the center line as a stuck straggler. Independent
  top-weighted draws give every dot a real destination up top, leaving
  the middle line clear (verified: 0 opaque px in the `H/2 ± 8px` band).

**`docs-cta.tsx` — "Read the docs" button is now pink.**
Dropped `variant: "outline"` so it uses the default (`bg-primary`) variant,
matching every other CTA button.

**`footer.tsx` — pink brand labels + wordmark hook.**
"Arbor" brand link and the "© {year} Arbor" credit both `text-foreground`
→ `text-primary` (pink). Added the `data-wordmark` attribute the particle
field keys off of.

## Verification

- `validate_domain_config.py` ✓
- `tsc --noEmit` ✓
- `pytest`: 1024 passed (1 unrelated backend booking-lifecycle failure,
  no frontend/backend code touched by this issue).
- Migration / middle-line behavior verified by canvas pixel sampling
  (`getImageData`): full upper-half migration at the bottom of the page,
  lower half and center-line band both clear.
