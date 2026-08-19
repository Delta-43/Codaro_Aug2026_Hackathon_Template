/**
 * Single source of truth for button *interactivity* — the "feel" of a button
 * (how it reacts to hover/press and its shape), kept separate from colour and
 * size, which live in the Button variants (`ui/button.tsx`).
 *
 * Why this file exists: the interactive feel used to be copy-pasted inline at
 * every call site (the landing hero, the CTAs, the nav), so "make buttons feel
 * the same everywhere" meant editing a dozen files. Now it lives here. Change a
 * value below and every button on the whole platform — landing, login, and the
 * app — changes with it.
 *
 * `press` is baked into the shared button base, so *every* button and CTA gets
 * it automatically. `pill` and `link` are opt-in extras a call site can add.
 */
export const buttonFx = {
  /**
   * The standard interactive feel, applied to every button platform-wide:
   * a gentle grow on hover (the transition itself comes from the button base's
   * `transition-all`). Scaling from the centre keeps layout stable.
   */
  press: "origin-center hover:scale-105",

  /** Rounded "pill" shape — primary CTAs and floating controls opt into this. */
  pill: "rounded-full",

  /**
   * Text/nav links (not real buttons): a slightly stronger hover grow and its
   * own transition, since links don't carry the button base classes.
   */
  link: "origin-center transition-transform duration-200 ease-out hover:scale-110",

  /**
   * Clickable *surfaces* — cards and list rows (a booking, a service). A clear
   * hover so it's obvious the whole tile is interactive: a full-strength muted
   * fill (not a faint half-tint) plus a primary-tinted border.
   */
  surface: "transition-colors hover:border-primary/40 hover:bg-muted",

  /**
   * Small pickable tiles — calendar day cells. A pink hover tint so cursoring a
   * date reads clearly as "you're on this one".
   */
  tile: "transition-colors hover:bg-primary/10 hover:text-primary",

  /**
   * Rating stars — a lively grow on hover, matching the landing testimonials.
   */
  star: "origin-center transition-transform duration-200 ease-out hover:scale-150",
} as const;
