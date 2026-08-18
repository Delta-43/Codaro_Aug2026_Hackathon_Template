"use client";

/**
 * Floating glass nav pill over the scene. Section links smooth-scroll to the
 * anchors; `route` links (Docs) are real navigations, so they go through
 * next/link instead. The primary button is auth-aware (Login → /login, or
 * Open app → /search when signed in).
 *
 * Layout: the theme toggle is pinned far-left and the Login button far-right;
 * the section links live in a scrollable middle strip. When the window is wide
 * enough for every link, the strip centres them as a group (`safe center`, so
 * nothing overflows out of reach) and no chevrons show. When the width
 * shrinks and the links no longer fit, the strip scrolls horizontally and small
 * `‹ ›` chevrons appear beside it (in-flow, so they never sit on top of a link)
 * to nudge the strip left/right — dimmed at whichever end you've reached.
 */
import Link from "next/link";
import { useRef, type MouseEvent } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

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

export function NavBar({ authed }: { authed: boolean }) {
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
      <div className="flex w-full max-w-3xl items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-2 shadow-sm backdrop-blur-xl">
        {/* Logo hidden through tablet — the pill is too tight until desktop
            once the theme toggle, chevrons, links + Login are in. Shows at lg. */}
        <Link
          href="/"
          className="hidden shrink-0 origin-left px-2 text-sm font-semibold tracking-tight text-foreground transition-transform duration-200 ease-out hover:scale-110 lg:inline-block"
        >
          service<span className="text-primary">.com</span>
        </Link>
        {/* Theme toggle sits on the LEFT below lg (where there's no logo), so
            the links stay centered; on desktop it lives in the right cluster. */}
        <ThemeToggle className="shrink-0 lg:hidden" />
        {/* Mobile-only affordance: scroll the links row left. */}
        <button
          type="button"
          aria-label="Scroll links left"
          onClick={() => linksRef.current?.scrollBy({ left: -120, behavior: "smooth" })}
          className="grid size-7 shrink-0 place-items-center rounded-full text-foreground/70 transition-transform duration-200 ease-out hover:scale-125 hover:text-foreground md:hidden"
        >
          <ChevronLeft className="landing-nudge-left size-4" aria-hidden />
        </button>
        {/* Links: horizontally scrollable on mobile (scrollbar hidden), centered on desktop. */}
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
        {/* Mobile-only affordance: the links row scrolls sideways. */}
        <button
          type="button"
          aria-label="Scroll links right"
          onClick={() => linksRef.current?.scrollBy({ left: 120, behavior: "smooth" })}
          className="grid size-7 shrink-0 place-items-center rounded-full text-foreground/70 transition-transform duration-200 ease-out hover:scale-125 hover:text-foreground md:hidden"
        >
          <ChevronRight className="landing-nudge size-4" aria-hidden />
        </button>
        <div className="flex shrink-0 items-center gap-1">
          {/* Desktop keeps the toggle here on the right, beside Login. */}
          <ThemeToggle className="shrink-0 hidden lg:grid" />
          <Link
            href={authed ? "/search" : "/login"}
            className={cn(
              buttonVariants({ size: "sm" }),
              "origin-center rounded-full px-4 transition-transform duration-200 ease-out hover:scale-105",
            )}
          >
            <ChevronRight className="size-4" aria-hidden />
          </button>
        )}

        {/* Far right — auth-aware primary button (pinned) */}
        <Link
          href={authed ? "/search" : "/login"}
          className={cn(
            buttonVariants({ size: "sm" }),
            "origin-center shrink-0 rounded-full px-4 transition-transform duration-200 ease-out hover:scale-105",
          )}
        >
          {authed ? "Open app" : "Login"}
        </Link>
      </div>
    </nav>
  );
}
