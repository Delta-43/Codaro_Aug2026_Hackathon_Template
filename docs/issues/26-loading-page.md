# Issue #26 — Public landing page

Branch: `26-loading-page`

## What changed

Replaced the root route (`frontend/src/app/page.tsx`), previously a bare
`redirect("/search")`, with a full public marketing landing page for anonymous
visitors. It pitches the product itself — a booking engine that adapts to any
business — over a theme-aware nature scene, with glass "chapters" and a set of
interactive touches. Brand shown to users is **Service.com** (matching the
existing app wordmark).

### New files (`frontend/src/components/landing/`)

| File | Role |
|------|------|
| `scene-background.tsx` | Fixed, theme-aware backdrop: day valley (light) / night + **flowing aurora curtains** (dark), a soft sun glow in day, drifting petals. Split from the user-supplied art into `/public/scene-day.jpg` + `scene-night.jpg`. |
| `nav-bar.tsx` | Floating glass nav: logo, section anchors, **day/night theme toggle**, Login. Links scroll horizontally on mobile with a `>` affordance. |
| `hero.tsx` | Above-the-fold pitch on a glass plate: eyebrow, headline, "Get Started", and the pipeline terminal. |
| `pipeline-terminal.tsx` | Stylized macOS terminal (real traffic-light buttons) animating the pivot pipeline. |
| `how-it-works.tsx` | Three steps whose icons use **macOS-dock proximity magnification** and turn dark pink on hover. |
| `calendar-demo.tsx` | The **real** app calendar — `MonthView` / `WeekView` / `DayView` — fed static demo data; the Month/Week/Day pills switch views live. Plus a short manual. |
| `testimonials.tsx` | The team's own reviews in a horizontal, snap-scrolling row (with a `>` scroll affordance); interactive stars + avatars. |
| `business-cta.tsx` | Closing owner pitch with the one down-page "Sign in" button. |
| `footer.tsx` | A single pink "© <year> Service.com" line. |
| `scroll-reveal.tsx` | `GlassPanel` (frosted plate) + `useScrollMotion` (the gradual fade/blur as a chapter leaves the viewport centre). |
| `scroll-cue.tsx` | A "Scroll" pill under each plate that snaps to the next. |
| `dock.tsx` | Reusable macOS-dock magnification (`Dock` + `DockItem`). |

### Modified

- `frontend/src/app/page.tsx` — client page composing the sections inside a
  scroll-snap container: Hero → How it works → Calendar → Testimonials →
  Business CTA → Footer.

## Design decisions & behaviour

- **Vertical-agnostic copy** — no vertical-specific nouns; only the engine's
  neutral spine words. Honors CONTRIBUTING's no-hard-coded-domain-words rule.
- **Tokens only** — colours come from `globals.css` tokens; the only hex literals
  are the macOS terminal traffic-lights (no token exists for those).
- **Theme-aware scene** — day photo in light mode, night + animated aurora in
  dark; `next-themes`, first load light, toggle in the nav.
- **Scroll** — CSS scroll-snap (mandatory): a deliberate scroll advances a whole
  plate; a gradual fade/blur de-emphasises off-centre chapters. Honors
  `prefers-reduced-motion`.
- **Interactions** — dock magnification on the step icons; hover-magnify on the
  nav + hero brand, terminal buttons, review stars + avatars, calendar
  Month/Week/Day pills and step numbers, and the business icon.
- **Real calendar** — the demo reuses the actual `MonthView/WeekView/DayView`
  components with mock availability, so it looks and switches exactly like the app.

## Verification (all green)

- `python3 .github/scripts/validate_domain_config.py` — valid.
- `pytest test -q` — 259 passed, 8 skipped (e2e live-stack, expected).
- `cd frontend && npm ci && npx tsc --noEmit && npm run build` — compiled
  successfully; `/` prerenders static.

See `docs/verifying-changes.md` for the reusable recipe.

## Open questions / doubts (owner)

Carried forward for discussion before this is considered done:

1. **Navigation feels thin** — only three section links; may want more.
2. **"From idea to booking in three steps" text legibility** — with the plates
   at their most transparent, the grey body text is faint over the green scene in
   light mode. The clean fix is to darken that body text (kept consistent across
   all sections) rather than make the plates more opaque — pending a decision.
3. **Testimonials** — two placeholder slots still need the last two teammates'
   reviews.
4. **Aurora** — the animated shimmer still reads slightly artificial; could be
   refined.
5. **Background photo** — open question whether a photographic background is
   wanted at all, vs. a lighter treatment.

## Follow-ups (out of scope here)

- Footer contact / help / legal links → their own issue.
- Owner self-service (create providers/services from the UI) is still unbuilt.
