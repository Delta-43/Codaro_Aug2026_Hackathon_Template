// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * The search surfaces' text-input class string.
 *
 * `search/page.tsx` and `filter-sheet.tsx` carried byte-identical copies, so a
 * focus-ring or height tweak could land on the search bar and not the filter
 * sheet sitting directly on top of it.
 *
 * Deliberately NOT shared with `code-entry.tsx` (h-10, px-3 — no leading icon)
 * or `components/ui/input.tsx` (a different, rounder design): folding those in
 * would change how they look, which is a design decision, not deduplication.
 */
export const SEARCH_INPUT =
  "h-11 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";
