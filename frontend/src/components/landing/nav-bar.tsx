"use client";

/**
 * Floating glass nav pill over the scene. Section links smooth-scroll to the
 * anchors; `route` links (Docs) are real same-origin navigations via next/link.
 * The primary button always reads "Login".
 *
 * Layout: the Arbor brand is pinned far-left and the Login button far-right;
 * the section links live in a scrollable middle strip. When the window is wide enough for every link, the
 * strip centres them as a group (`safe center`, so nothing overflows out of
 * reach) and no chevrons show. When the width shrinks and the links no longer
 * fit, the strip scrolls horizontally and small `‹ ›` chevrons appear beside it
 * (in-flow, so they never sit on top of a link) to nudge the strip left/right —
 * dimmed at whichever end you've reached. (The day/night toggle lives in the
 * footer now, not here.)
 */
import { useEffect, useRef, useState, type MouseEvent } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { buttonFx } from "@/config/buttons";
import { ScrollTopLink } from "@/components/landing/scroll-top-link";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#calendar", label: "Calendar" },
  { href: "#reviews", label: "Reviews" },
  { href: "/docs", label: "Docs", route: true },
];

const LINK_CLASS =
  "shrink-0 origin-center whitespace-nowrap rounded-full px-2.5 py-1.5 text-sm text-muted-foreground transition-all duration-200 ease-out hover:scale-110 hover:bg-muted hover:text-foreground";

function smoothScroll(e: MouseEvent<HTMLAnchorElement>, href: string) {
  e.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
}

export function NavBar() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  // Watch the link strip: expose chevrons only when it can actually scroll, and
  // track which end we're at so the matching chevron dims (no dead controls).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => {
      const max = el.scrollWidth - el.clientWidth;
      setOverflow(max > 1);
      setAtStart(el.scrollLeft <= 1);
      setAtEnd(el.scrollLeft >= max - 1);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.addEventListener("scroll", measure, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", measure);
    };
  }, []);

  const nudge = (dir: 1 | -1) => {
    const el = scrollRef.current;
    if (el) el.scrollBy({ left: dir * el.clientWidth * 0.7, behavior: "smooth" });
  };

  const chevClass =
    "grid size-7 shrink-0 place-items-center rounded-full text-muted-foreground transition-all hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-25";

  return (
    <nav className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <div className="flex w-full max-w-3xl items-center gap-2 rounded-3xl border border-border/60 bg-background/70 px-4 py-2 shadow-sm backdrop-blur-xl">
        {/* Far left — the platform name; clicking it glides back to the top of
            the landing page, like the section links scroll to their anchors. */}
        <ScrollTopLink className="shrink-0 origin-left text-base font-bold tracking-tight text-primary transition-transform duration-200 ease-out hover:scale-110">
          Arbor
        </ScrollTopLink>

        {/* Left chevron — only while the strip can scroll */}
        {overflow && (
          <button
            type="button"
            aria-label="Scroll links left"
            className={chevClass}
            disabled={atStart}
            onClick={() => nudge(-1)}
          >
            <ChevronLeft className={cn("size-4", !atStart && "landing-nudge-left")} aria-hidden />
          </button>
        )}

        {/* Middle — links. Centred as a group when they fit; scrolls when not. */}
        <div
          ref={scrollRef}
          className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto [justify-content:safe_center] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {LINKS.map((l) =>
            l.route ? (
              <Link key={l.href} href={l.href} className={LINK_CLASS}>
                {l.label}
              </Link>
            ) : (
              <a
                key={l.href}
                href={l.href}
                onClick={(e) => smoothScroll(e, l.href)}
                className={LINK_CLASS}
              >
                {l.label}
              </a>
            ),
          )}
        </div>

        {/* Right chevron — only while the strip can scroll */}
        {overflow && (
          <button
            type="button"
            aria-label="Scroll links right"
            className={chevClass}
            disabled={atEnd}
            onClick={() => nudge(1)}
          >
            <ChevronRight className={cn("size-4", !atEnd && "landing-nudge")} aria-hidden />
          </button>
        )}

        {/* Far right — primary button (pinned), links to /login */}
        <Link
          href="/login"
          className={cn(
            buttonVariants({ size: "sm" }),
            buttonFx.pill,
            "shrink-0 px-4",
          )}
        >
          Login
        </Link>
      </div>
    </nav>
  );
}
