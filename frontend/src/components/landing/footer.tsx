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
import { Leaf } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { GlassPanel } from "@/components/landing/scroll-reveal";

const EXPLORE = [
  { href: "#how", label: "How it works" },
  { href: "#calendar", label: "Calendar" },
  { href: "#reviews", label: "Reviews" },
  { href: "/docs", label: "Docs" },
];

const LINK_CLASS = "text-sm text-muted-foreground transition-colors hover:text-foreground";
const COL_HEAD = "text-xs font-semibold uppercase tracking-wide text-foreground/50";

export function Footer({ authed }: { authed: boolean }) {
  const year = new Date().getFullYear();
  return (
    <footer className="flex min-h-[80vh] snap-start snap-always flex-col justify-end">
      {/* The bar */}
      <div className="mx-auto w-full max-w-5xl px-4">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          {/* Centered indicator icon — big interactive Leaf, like the other plates */}
          <div className="mb-8 flex justify-center">
            <Link href="/" aria-label="Arbor — home" className="flex size-12 origin-center items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <Leaf className="size-6" aria-hidden />
            </Link>
          </div>

          {/* Bar — brand + pitch on the left, link columns on the right */}
          <div className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-xs">
              <Link
                href="/"
                className="inline-block origin-left text-lg font-bold tracking-tight text-foreground transition-transform duration-200 ease-out hover:scale-110"
              >
                Arbor
              </Link>
              <p className="mt-3 text-sm leading-relaxed text-foreground/70">
                One booking engine, reshaped for any business — booking, scheduling, and
                availability, without a rewrite.
              </p>
            </div>

            <div className="flex gap-14 sm:gap-20">
              <nav aria-label="Explore" className="flex flex-col gap-2.5">
                <h3 className={COL_HEAD}>Explore</h3>
                {EXPLORE.map((l) => (
                  <Link key={l.href} href={l.href} className={LINK_CLASS}>
                    {l.label}
                  </Link>
                ))}
              </nav>
              <nav aria-label="More" className="flex flex-col gap-2.5">
                <h3 className={COL_HEAD}>More</h3>
                <Link href={authed ? "/search" : "/login"} className={LINK_CLASS}>
                  {authed ? "Open app" : "Login"}
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

      {/* Giant fading wordmark — full-bleed, dissolving upward from the bottom. */}
      <div aria-hidden className="mt-10 overflow-hidden">
        <span
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
