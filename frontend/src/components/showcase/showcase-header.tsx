// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import Link from "next/link";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { BRAND_NAME } from "@/components/showcase/showcase-copy";
import { cinzel, showcaseDisplayClass } from "@/components/showcase/showcase-fonts";

/** Small original crescent-moon mark, echoing the backdrop — kept inline
 *  since it's only ever used here. */
function MoonMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden focusable="false">
      <path
        d="M15.5 3.5a9 9 0 1 0 5 16 8 8 0 0 1-5-16Z"
        fill="currentColor"
      />
    </svg>
  );
}

/**
 * Minimal header for `/showcase` — just the wordmark (home) and a sign-in
 * link. No scroll-spy / in-page anchors: this page has no chapters to jump
 * to, unlike the landing page's `nav-bar.tsx`.
 */
export function ShowcaseHeader() {
  return (
    <header className="relative z-10 flex items-center justify-between px-6 py-6 sm:px-10">
      <Link
        href="/"
        className={cn(
          "flex shrink-0 items-center gap-1.5 text-base font-bold tracking-tight text-primary",
          cinzel.variable,
          showcaseDisplayClass,
          buttonFx.link,
        )}
      >
        <MoonMark className="size-5 text-primary" />
        {BRAND_NAME}
      </Link>
      <Link
        href="/login"
        className={cn(
          "text-sm font-medium text-white/80 hover:text-white",
          buttonFx.link,
        )}
      >
        Sign in
      </Link>
    </header>
  );
}
