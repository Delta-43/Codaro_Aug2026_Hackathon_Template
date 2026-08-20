# Interactivity config — one source for how things react

**Rule of thumb: no interactive element on the platform hard-codes its own
hover/press feel. It pulls the feel from `frontend/src/config/buttons.ts`
(`buttonFx`).** Change a value there and every button, card, chevron, star,
heading and icon across the whole app moves with it — the same way
`domain.config.json` pivots the *vocabulary*, `buttonFx` pivots the *feel*.

This is the "landing-page interactivity, everywhere" system. The delightful
hover-grow the landing page shipped with is now a named token, and every
interactive surface in `frontend/` opts into the token instead of re-inventing a
`transition + hover:scale` string inline.

## Where it lives

| Thing | File |
|-------|------|
| The tokens | `frontend/src/config/buttons.ts` — the `buttonFx` object |
| Baked-in default | `frontend/src/components/ui/button.tsx` — every `<Button>` already carries `buttonFx.press` in its base, so real buttons need nothing extra |
| This rule | `docs/interactivity.md` (here) + a pointer in `frontend/CLAUDE.md` |

`landing/` keeps its **own** frozen copy of `buttonFx` (it's a separate,
air-gapped deployable — see `frontend/CLAUDE.md`). The extra roles below
(`heading`, `icon`, `chevron`) were added on the `frontend/` side for the app;
mirror them into `landing/`'s copy only if `landing/` starts using them.

## The tokens (roles)

Pick the token by **what the element is**, then `cn()` it onto the element:

| Token | Use it for | Feel |
|-------|-----------|------|
| `press` | any real button / small pill / icon-button / toggle | gentle grow on hover (scale-105). Already baked into `<Button>`. |
| `pill` | primary CTAs & floating round controls | `rounded-full` shape (opt-in). |
| `link` | standalone text/nav links (not inline prose) | stronger grow (scale-110). |
| `surface` | clickable **cards / list rows** (a booking, a provider, a service, a search result) | full-strength muted fill + primary-tinted border on hover. |
| `tile` | small pickable **calendar day cells** | pink hover tint ("you're on this one"). |
| `star` | **rating** stars that are the hover target (review input, rate-customer) | lively grow (scale-150), matching the landing testimonials. |
| `pink` | a bare icon / label / status chip that should read as the accent colour on hover | `hover:text-primary` (the platform's "turn pink on hover"). |
| `heading` | interactive **page/plate/section titles** & wordmarks (scroll-to-top, expand) | gentle grow, anchored left (override `origin-*` for centred/right). |
| `icon` | a bare clickable **icon** with no button chrome (theme switch, cog, avatar) | clean grow (scale-110). |
| `chevron` | the `>` / `⌄` glyph at the end of a clickable row | nudges toward its direction on the **row's** hover — put `group` on the row, this token on the chevron. |

### The two mechanics that trip people up

- **A scale token needs a transition to animate it.** Tokens that scale
  (`press`, `star`, `icon`, `link`, `heading`) rely on a `transition-*` on the
  same element. `<Button>` and the token strings that carry their own transition
  (`link`, `icon`, `star`, `heading`) are fine; when you add `press` to a
  hand-rolled element that only had `transition-colors`, switch it to
  `transition-all` so the scale eases too.
- **`chevron` is a group-hover.** The chevron is `aria-hidden` decoration, so it
  animates off the row, not itself: the clickable row gets `group`, the chevron
  gets `buttonFx.chevron`.

### Don't scale inline prose links

A link in the middle of a sentence (a privacy-policy link, a "Create an account"
switch) keeps `hover:underline` — growing mid-sentence text jitters the line.
`link`/`heading` are for **standalone** links and titles.

## How to apply it (the pattern)

```tsx
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

// a clickable card / row
<Link className={cn("group flex items-center gap-3 rounded-xl border border-border bg-card p-3", buttonFx.surface)}>
  …
  <ChevronRight className={cn("size-5 text-muted-foreground", buttonFx.chevron)} aria-hidden />
</Link>

// a hand-rolled control (not the <Button> component)
<button className={cn("… transition-all hover:bg-muted", buttonFx.press)}>…</button>
```

Real `<Button>` components already have `press` — don't add it again.

## For the next pivot / the next agent

When you build, change, or adjust **any** interactive element:

1. **Use a `buttonFx` token, never a fresh inline `hover:scale…`/`transition`
   feel.** If you catch yourself typing `hover:scale-105` or
   `transition-transform … hover:scale…` at a call site, stop and reach for the
   token instead.
2. If no token fits the *role*, **add a new token to `buttons.ts`** (with a
   JSDoc note on when to use it) and use that — so the feel stays editable from
   one file. Don't special-case it inline.
3. Keep the token **names** stable; tune their **values**. The whole point is
   that a future business can dial the platform's interaction feel up or down by
   editing one file.
4. If you touch the shared `buttonFx` behaviour (not just add a role), apply the
   same change to `landing/`'s frozen copy.

## Theme note (related front-door change)

Theming is `next-themes` with `defaultTheme="system"` (`frontend/src/app/layout.tsx`),
so every page — the login front door included — follows the OS light/dark
preference live on first load. The explicit control (Light / Dark / **Smart** =
system) lives in **Settings → Appearance** via the compact `AppearancePicker`;
the login pages intentionally carry no theme control, they just inherit the
system/persisted choice.
