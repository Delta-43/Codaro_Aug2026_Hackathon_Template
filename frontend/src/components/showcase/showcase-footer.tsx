// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import Link from "next/link";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { BRAND_NAME } from "@/components/showcase/showcase-copy";

const LINK_CLASS = cn("text-white/60 hover:text-white", buttonFx.link);

/**
 * Slim, bespoke footer for `/showcase`. Deliberately not the landing page's
 * `Footer` — that one is wired to `particles.tsx` and its own in-page anchors,
 * neither of which apply to this leaf page.
 */
export function ShowcaseFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="relative z-10 flex flex-col items-center gap-2 px-6 py-10 text-center text-sm text-white/50 sm:flex-row sm:justify-between sm:px-10">
      <div className="flex flex-col items-center gap-1 sm:items-start">
        <p>&copy; {year} {BRAND_NAME}</p>
        <p className="text-xs text-white/35">Powered by Arbor</p>
      </div>
      <nav className="flex items-center gap-4">
        <Link href="/" className={LINK_CLASS}>
          Home
        </Link>
        <Link href="/privacy" className={LINK_CLASS}>
          Privacy
        </Link>
      </nav>
    </footer>
  );
}
