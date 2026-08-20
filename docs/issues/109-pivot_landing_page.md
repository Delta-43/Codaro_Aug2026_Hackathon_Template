# Issue 109 — Pivot the landing page to the funeral-home business

Re-skin the public landing page (`/`) for the funeral pivot ("book a farewell":
the subject is deceased, someone else pays, and neither chooses the date — a
director sets it within the week). **Landing page only** — no backend, config,
or engine changes. The Arbor brand name and leaf mark stay exactly as they were.

## What changed

**Removed three plates** (deleted the components, unwired from `page.tsx`):
- `how-it-works.tsx` — the "From idea to booking in three steps." plate
- `docs-cta.tsx` — the "Curious how it works?" plate
- `business-cta.tsx` — the "Run a business? Bring it to Arbor." plate
- `dock.tsx` — orphaned once How-it-works was gone (its only consumer)

**New page order** (`src/app/page.tsx`):
Hero → Calendar showcase → **Popular products (new)** → Reviews → Footer.

**New plate** `products.tsx` (`#services`) — "What families choose most.": an
interactive glass grid of six farewell products drawn from the pivot brief —
Cremation & Burial, Ashes-to-Diamond, Memorial Tree, Eternal (3D-printed)
Flowers, A Star in Their Name, AI Voice Companion — plus a footnote nodding at
cryogenic suspension / orbital committal. Hover feel via `buttonFx.plate`
(config-driven, per frontend/CLAUDE.md); funeral-themed lucide icons.

**Copy adapted to the funeral business:**
- `hero.tsx` — "Don't worry, be sad." + deadpan subtitle; CTA "Arrange a farewell".
- `pipeline-terminal.tsx` — the terminal now runs the arrangement pipeline
  (submit arrangement → assign director & chapel → set the date within 7 days).
- `calendar-showcase.tsx` — demo resource renamed "Studio A" → "Chapel of Rest A";
  "Booking confirmed" → "Date reserved"; "Book this slot" → "Reserve this date";
  "Pick a time to book." → "Pick a date to reserve."; the reveal heading and the
  three step cards rewritten for arrangements.
- `testimonials.tsx` — the dev-team reviews replaced with five deadpan
  bereaved-family reviews (new names, each nodding at a product); heading
  "Families we've helped say goodbye." / "Real farewells, in the words of the
  bereaved."
- `footer.tsx` — pitch line rewritten; Explore links point to real in-page
  sections (What we offer / Calendar / Families); dropped the engine "Docs" link.
- `nav-bar.tsx` — links now Services / Calendar / Families; dropped "Docs".

**Icons** adapted to the business (Flame, Gem, TreePine, Flower, Sparkles,
MessageCircle, Heart); the Arbor brand mark (`/arbor-mark-7d.png`) is untouched.

## Verification
- `npx tsc --noEmit` — clean.
- Live preview (docker :3000): no console errors; all copy renders; brand mark
  and calendar tour intact.

Scope note: `/docs` and `/privacy` routes are unchanged; only the in-page DocsCta
teaser plate and its nav/footer links were removed.
