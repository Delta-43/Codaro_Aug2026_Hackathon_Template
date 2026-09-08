// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Showcase-only display font. `/showcase` wants a gothic/monumental feel for
 * the wordmark and hero heading that the rest of the site (global `Outfit`,
 * `app/layout.tsx`) doesn't share — so it's loaded here via `next/font/google`
 * and exposed as a CSS variable, scoped to this page's components only.
 * Nothing in `app/layout.tsx` changes; importing this module has no effect
 * outside `/showcase`.
 *
 * Cinzel: a monumental Roman-inscription serif — reads as engraved stone /
 * headstone lettering, which fits a funeral-home brand better than a
 * blackletter face (which skews more "metal band" than "gothic elegance") or
 * a plain display serif like Playfair (too editorial/fashion).
 */
import { Cinzel } from "next/font/google";

export const cinzel = Cinzel({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-showcase-display",
});

/** Apply alongside `cinzel.variable` to render in the showcase display font. */
export const showcaseDisplayClass = "font-[family-name:var(--font-showcase-display)]";
