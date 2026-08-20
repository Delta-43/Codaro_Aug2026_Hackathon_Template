"use client";

/**
 * Floating glass nav pill over the scene. Section links smooth-scroll to the
 * anchors; `route` links (Docs) are real same-origin navigations via next/link.
 * The primary button reads "Dashboard" (→ the app) when a session exists, else
 * "Login".
 *
 * Layout: the Arbor brand is pinned far-left and the Login button far-right;
 * the section links live in a scrollable middle strip. When the window is wide enough for every link, the
 * strip centres them as a group (`safe center`, so nothing overflows out of
 * reach) and no chevrons show. When the width shrinks and the links no longer
 * fit, the strip scrolls horizontally and small `‹ ›` chevrons fade in over its
 * edges (absolute overlays with a gradient, so they take no layout width) to
 * nudge it left/right, dimmed at whichever end you've reached. Because they don't
 * occupy the row, they never appear when the links fit, and the brand/Login never
 * shift when they toggle. (The day/night toggle lives in the footer now.)
 */
import { useEffect, useRef, useState, type MouseEvent } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { buttonFx } from "@/config/buttons";
import { ScrollTopLink } from "@/components/landing/scroll-top-link";
import { useAuth } from "@/lib/auth";
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
  // Wrapped in <AuthProvider> at the root layout, so the landing page can tell a
  // signed-in visitor apart: the primary pill becomes "Dashboard" → the app,
  // otherwise it stays "Login". `loading` keeps it as Login until the session
  // resolves, avoiding a Dashboard→Login flicker on first paint.
  const { session, loading, isOwner } = useAuth();
  const signedIn = !loading && Boolean(session);
  // Same split the login redirect uses (login/page.tsx): owners land on their
  // console, clients on the search app. Sending an owner to /search hangs them.
  const dashboardHref = isOwner ? "/owner" : "/search";

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

  // Edge nudge chevrons — overlaid at the strip's ends (absolute), so they take
  // no layout width. Reserving width for them (the previous approach) shrank the
  // strip enough to make it "overflow" and show the chevrons even on wide/tablet
  // screens where the links comfortably fit.
  const edgeChev =
    "absolute inset-y-0 z-10 grid w-10 place-items-center text-muted-foreground transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-30";

  return (
    <nav className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <div className="flex w-full max-w-4xl items-center gap-2 rounded-3xl border border-border/60 bg-background/70 px-4 py-2 shadow-sm backdrop-blur-xl">
        {/* Far left — the platform name; clicking it glides back to the top of
            the landing page, like the section links scroll to their anchors. */}
        <ScrollTopLink className="flex shrink-0 origin-left items-center gap-1.5 text-base font-bold tracking-tight text-primary transition-transform duration-200 ease-out hover:scale-110">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-6 -translate-y-[9%]" />
          Arbor
        </ScrollTopLink>

        {/* Middle — links, centred when they fit, horizontally scrollable when
            not. The nudge chevrons are overlaid at the strip's edges (absolute),
            so they never consume layout width and only render when the strip can
            actually scroll — nothing shows on wide/tablet screens where the links
            fit, and the brand/Login never shift when the chevrons toggle. */}
        <div className="relative flex min-w-0 flex-1 items-center">
          <div
            ref={scrollRef}
            className="no-scrollbar flex w-full min-w-0 items-center gap-2 overflow-x-auto [justify-content:safe_center]"
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

          {overflow && (
            <>
              <button
                type="button"
                aria-label="Scroll links left"
                className={cn(edgeChev, "left-0 justify-items-start bg-gradient-to-r from-background via-background/90 to-transparent")}
                disabled={atStart}
                onClick={() => nudge(-1)}
              >
                <ChevronLeft className={cn("size-4", !atStart && "landing-nudge-left")} aria-hidden />
              </button>
              <button
                type="button"
                aria-label="Scroll links right"
                className={cn(edgeChev, "right-0 justify-items-end bg-gradient-to-l from-background via-background/90 to-transparent")}
                disabled={atEnd}
                onClick={() => nudge(1)}
              >
                <ChevronRight className={cn("size-4", !atEnd && "landing-nudge")} aria-hidden />
              </button>
            </>
          )}
        </div>

        {/* Far right — primary button (pinned): Dashboard when signed in, else Login */}
        <Link
          href={signedIn ? dashboardHref : "/login"}
          className={cn(
            buttonVariants({ size: "sm" }),
            buttonFx.pill,
            "shrink-0 px-4",
          )}
        >
          {signedIn ? "Dashboard" : "Login"}
        </Link>
      </div>
    </nav>
  );
}
