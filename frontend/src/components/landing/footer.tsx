// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Landing footer — a full-width footer bar on the shared glass plate
 * (`GlassPanel`). A big interactive Leaf badge is centered on top like the
 * other plates' indicator icon; below it the bar keeps its left/right layout:
 * brand name + pitch on the left, the site's real links in two columns on the
 * right, then the credit + the day/night toggle that used to live in the nav.
 * Only routes/anchors we actually have — no filler.
 *
 * Below the bar, a giant ARBOR wordmark fades top→bottom (transparent at the
 * top, solid at the very bottom edge; black in light mode, white in dark) — the
 * closing flourish, like the SUKOYA reference. Hovering it nudges it up a touch.
 *
 * Server component; only the nested `ThemeToggle` needs the client.
 */
import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";
import { GlassPanel } from "@/components/landing/scroll-reveal";
import { ScrollTopLink } from "@/components/landing/scroll-top-link";
import { SHOWCASE_ONLY, SOURCE_URL } from "@/config/showcase";

const EXPLORE = [
  { href: "#services", label: "What you can pivot", anchor: true },
  { href: "#calendar", label: "Calendar", anchor: true },
  { href: "#proof", label: "Evidence", anchor: true },
];

const LINK_CLASS = "text-sm text-muted-foreground transition-colors hover:text-foreground";
const COL_HEAD = "text-xs font-semibold uppercase tracking-wide text-foreground/50";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="flex min-h-[80vh] snap-start snap-always flex-col justify-end">
      {/* The bar */}
      <div className="mx-auto w-full max-w-4xl px-4">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          {/* Bar — brand + pitch on the left, link columns on the right */}
          <div className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-xs">
              <ScrollTopLink className="inline-flex origin-left items-center gap-1.5 text-lg font-bold tracking-tight text-primary transition-transform duration-200 ease-out hover:scale-110">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-7 -translate-y-[9%]" />
                Arbor
              </ScrollTopLink>
              <p className="mt-3 text-sm leading-relaxed text-foreground/70">
                A config-driven booking engine. One neutral spine, one JSON file, and the
                same deployment becomes a different business.
              </p>
            </div>

            <div className="flex gap-14 sm:gap-20">
              <nav aria-label="Explore" className="flex flex-col gap-2.5">
                <h3 className={COL_HEAD}>Explore</h3>
                {EXPLORE.map((l) =>
                  l.anchor ? (
                    <a key={l.href} href={l.href} className={LINK_CLASS}>
                      {l.label}
                    </a>
                  ) : (
                    <Link key={l.href} href={l.href} className={LINK_CLASS}>
                      {l.label}
                    </Link>
                  ),
                )}
              </nav>
              <nav aria-label="More" className="flex flex-col gap-2.5">
                <h3 className={COL_HEAD}>More</h3>
                <Link href={SHOWCASE_ONLY ? SOURCE_URL : "/login"} className={LINK_CLASS}>
                  Login
                </Link>
                <Link href="/privacy" className={LINK_CLASS}>
                  Data handling &amp; privacy policy
                </Link>
              </nav>
            </div>
          </div>

          {/* Bottom row — interactive credit + the light/dark toggle (no label) */}
          <div className="mt-10 flex items-center justify-between border-t border-border/40 pt-6">
            <p className="origin-left cursor-pointer text-sm font-medium text-primary transition-transform duration-200 ease-out hover:scale-105">
              © {year} Arbor
            </p>
            <ThemeToggle />
          </div>
        </GlassPanel>
      </div>

      {/* Giant fading wordmark — dissolving upward from the bottom, locked to the
          exact same width as the glass plates above (same `max-w-4xl` + `px-4`
          container). Drawn as SVG text whose viewBox matches the word's *natural*
          proportions in the site font (≈ 842 × 180 for "ARBOR" at weight 800), so
          `w-full` scales it up to the plate width uniformly — big, responsive, and
          without the horizontal stretch a fixed `textLength` would force. The
          particle field finds this element by `data-wordmark` and steers its dots
          clear of it while it's on screen. */}
      <div aria-hidden className="mx-auto mt-10 w-full max-w-4xl px-4">
        <svg
          data-wordmark
          viewBox="0 0 842 180"
          preserveAspectRatio="xMidYMax meet"
          className="block w-full origin-bottom cursor-default select-none fill-black transition-transform duration-300 ease-out hover:-translate-y-1 hover:scale-[1.02] dark:fill-white"
          style={{
            WebkitMaskImage: "linear-gradient(to bottom, transparent 8%, rgba(0,0,0,0.16) 46%, #000 97%)",
            maskImage: "linear-gradient(to bottom, transparent 8%, rgba(0,0,0,0.16) 46%, #000 97%)",
          }}
        >
          <text
            x="421"
            y="173"
            textAnchor="middle"
            fontSize="240"
            fontWeight="800"
            style={{ fontFamily: "inherit" }}
          >
            ARBOR
          </text>
        </svg>
      </div>
    </footer>
  );
}
