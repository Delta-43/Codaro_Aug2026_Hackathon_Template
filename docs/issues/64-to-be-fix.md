# 64-to-be-fix — landing page polish

Follow-up fixes on the landing page (issue #26 work), plus a repo-wide
token-budget rule. Branch: `64-to-be-fix`.

## What changed

**Navigation bar**
- Logo (`service.com`) now shows only at `lg`+ (desktop). Hidden on mobile and
  tablet, where the pill was too tight once the toggle, chevrons, links, and
  Login were all present.
- Theme (day/night) toggle moves to the **left** of the pill below `lg`, so the
  section links stay centered on mobile and tablet. On desktop it stays on the
  right beside Login.
- Mobile keeps the left/right scroll chevrons for the links row.

**Reviews / testimonials**
- Filled the two placeholder slots with real reviews (Debadeep Chaudhury,
  Peter P.). Five reviews now, no placeholders.
- Removed the dark `from-background/70` fade scrims on the horizontal reviews
  row: in dark mode they rendered as near-black bands the cards scrolled under.
  The chevron buttons keep their own glass background, so scrollability still
  reads.
- Left + right scroll chevrons on the row (both directions).

**Scene background**
- Aurora curtains use `animation-fill-mode: backwards` (+ dim base opacity) so
  they no longer flash at full brightness during their `animation-delay` right
  after switching into dark mode.

**Branding / copy**
- `service.com` lowercase everywhere on the landing page. Darkened faint grey
  text for legibility over the glass plates.

**Docs / process**
- Added `docs/token-budget.md` and a "Token budget (read first)" section in
  `CLAUDE.md` so every agent minimizes token use (screenshots are the #1 cost).

## Verification (per docs/verifying-changes.md — frontend-only ⇒ check 3)

- `npx tsc --noEmit` — clean.
- `npm run build` — compiled successfully, 20/20 static pages, `/` prerenders
  static (11.3 kB, 196 kB First Load JS). No errors or warnings.
- Browser console — no errors across mobile / tablet / desktop, light + dark.

## Still open (NOT done yet)

- **Background not changed yet.** The photographic day/night scene is unchanged;
  the open question of whether to keep a photo background at all is unresolved.
- **No extra navigation info added yet.** The nav still has only the three
  section links (How it works / Calendar / Reviews) — the "too few nav options"
  doubt is not addressed in this branch.
- Footer contact/help links remain a separate future issue.
