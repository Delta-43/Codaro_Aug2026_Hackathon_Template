// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Single source of truth for button *interactivity*, the "feel" of a button
 * (how it reacts to hover/press and its shape), kept separate from colour and
 * size, which live in the Button variants (`ui/button.tsx`).
 *
 * Why this file exists: the interactive feel used to be copy-pasted inline at
 * every call site (the landing hero, the CTAs, the nav), so "make buttons feel
 * the same everywhere" meant editing a dozen files. Now it lives here. Change a
 * value below and every button on the whole platform, landing, login, and the
 * app, changes with it.
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

  /** Rounded "pill" shape, primary CTAs and floating controls opt into this. */
  pill: "rounded-full",

  /**
   * Text/nav links (not real buttons): a slightly stronger hover grow and its
   * own transition, since links don't carry the button base classes.
   */
  link: "origin-center transition-transform duration-200 ease-out hover:scale-110",

  /**
   * Clickable *surfaces*, cards and list rows (a booking, a service). A clear
   * hover so it's obvious the whole tile is interactive: a full-strength muted
   * fill (not a faint half-tint) plus a primary-tinted border.
   */
  surface: "transition-colors hover:border-primary/40 hover:bg-muted",

  /**
   * Small pickable tiles: calendar day cells. A pink hover tint so cursoring a
   * date reads clearly as "you're on this one".
   */
  tile: "transition-colors hover:bg-primary/10 hover:text-primary",

  /**
   * Rating stars: a lively grow on hover, matching the landing testimonials.
   */
  star: "origin-center transition-transform duration-200 ease-out hover:scale-150",

  /**
   * Interactive headings: page titles and plate/section headers that do
   * something on click (scroll to top, expand). A gentle grow anchored left so
   * the title doesn't drift. Override the origin at the call site for centred or
   * right-aligned headings, e.g. `cn(buttonFx.heading, "origin-center")`.
   */
  heading: "inline-block origin-left transition-transform duration-200 ease-out hover:scale-105",

  /**
   * Clickable icons: a settings cog, a theme switch, an avatar, an action icon.
   * A clean grow so a bare icon reads as pressable without needing a chrome
   * button around it.
   */
  icon: "origin-center transition-transform duration-200 ease-out hover:scale-110",

  /**
   * A logo/avatar sitting inside a bigger clickable chip or row. Same grow as
   * `icon`, but fired by the *group's* hover (put `group` on the chip), so the
   * mark responds from anywhere in the hit area while the chip itself holds
   * still, which is what a corner-flush element needs, since scaling the whole
   * chip would nudge it toward the screen edge.
   */
  groupIcon: "origin-center transition-transform duration-200 ease-out group-hover:scale-110",

  /**
   * "Turn pink on hover", the accent tint the platform reaches for constantly:
   * a bare icon, label, or status chip that should read as pink (the primary
   * colour) while the cursor is on it. Pair with a chrome button's own `press`
   * where both are wanted.
   */
  pink: "transition-colors hover:text-primary",

  /**
   * The "chevron" affordance, the `>` / `⌄` glyphs that sit at the end of a
   * clickable row or card. They are decorative (aria-hidden), so they animate
   * off the *row's* hover, not their own: put `group` on the row and this token
   * on the chevron, and it nudges toward its direction as you hover the row.
   */
  chevron: "transition-transform duration-200 ease-out group-hover:translate-x-0.5",

  /**
   * Interactive info plates: the landing "three steps" cards and similar
   * explanatory tiles that should invite a touch: a gentle centre grow plus a
   * soft primary tint (fill + border) on hover.
   */
  plate: "origin-center transition-all duration-200 ease-out hover:scale-[1.03] hover:border-primary/40 hover:bg-primary/10",
} as const;
