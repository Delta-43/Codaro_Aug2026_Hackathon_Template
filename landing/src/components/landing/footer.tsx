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

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "";

const EXPLORE = [
  { href: "#how", label: "How it works" },
  { href: "#calendar", label: "Calendar" },
  { href: "#reviews", label: "Reviews" },
  { href: `${APP_URL}/docs`, label: "Docs", external: true },
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
              <ScrollTopLink className="inline-block origin-left text-lg font-bold tracking-tight text-primary transition-transform duration-200 ease-out hover:scale-110">
                Arbor
              </ScrollTopLink>
              <p className="mt-3 text-sm leading-relaxed text-foreground/70">
                One booking engine, reshaped for any business — booking, scheduling, and
                availability, without a rewrite.
              </p>
            </div>

            <div className="flex gap-14 sm:gap-20">
              <nav aria-label="Explore" className="flex flex-col gap-2.5">
                <h3 className={COL_HEAD}>Explore</h3>
                {EXPLORE.map((l) =>
                  l.external ? (
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
                <a href={`${APP_URL}/login`} className={LINK_CLASS}>
                  Login
                </a>
                <a href={`${APP_URL}/privacy`} className={LINK_CLASS}>
                  Data handling &amp; privacy policy
                </a>
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

      {/* Giant fading wordmark — full-bleed, dissolving upward from the bottom.
          The particle field finds this element by `data-wordmark` and steers its
          dots clear of it, but only while it's actually on screen (scrolled to
          the footer) — so nothing crawls over the closing wordmark, and the
          field is unaffected anywhere else on the page. */}
      <div aria-hidden className="mt-10 overflow-hidden">
        <span
          data-wordmark
          className="block origin-bottom cursor-default select-none text-center font-extrabold leading-[0.78] tracking-tighter text-black transition-transform duration-300 ease-out hover:-translate-y-1 hover:scale-[1.03] dark:text-white"
          style={{
            fontSize: "clamp(3.5rem, 24vw, 18rem)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent 8%, rgba(0,0,0,0.16) 46%, #000 97%)",
            maskImage: "linear-gradient(to bottom, transparent 8%, rgba(0,0,0,0.16) 46%, #000 97%)",
          }}
        >
          ARBOR
        </span>
      </div>
    </footer>
  );
}
