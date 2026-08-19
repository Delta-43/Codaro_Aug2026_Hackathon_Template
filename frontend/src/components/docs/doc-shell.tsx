"use client";

/**
 * Chrome for /docs: a sticky header (back to the landing page + theme switch)
 * and a desktop table of contents that highlights whichever section is
 * currently under the header. Content itself is server-rendered and passed in.
 *
 * Jumping around a 13-section page is the main way this page is read, so the
 * shortcuts are handled rather than left to the browser (see
 * `useDocNavigation`): clicking one glides to the section, marks where you
 * landed, and keeps the URL copy-pasteable. All motion honors
 * `prefers-reduced-motion`.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

export type TocEntry = { id: string; label: string };

/** Landing flash on the heading you jumped to; see the <style> block below. */
const LAND_CLASS = "docs-land";
const LAND_MS = 1100;
/** Hard cap on the highlight lock, for browsers without `scrollend`. */
const SETTLE_MS = 1000;

export function DocShell({
  title,
  subtitle,
  sections,
  children,
}: {
  title: string;
  subtitle: string;
  sections: TocEntry[];
  children: React.ReactNode;
}) {
  const { rootRef, active } = useDocNavigation(sections);

  return (
    <div ref={rootRef} className="min-h-dvh bg-background">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3">
          <Link
            href="/"
            className="inline-flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden /> Home
          </Link>
          <span aria-hidden className="text-border">
            /
          </span>
          <span className="min-w-0 truncate text-sm font-medium text-foreground">Docs</span>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 pb-24 pt-10">
        <div className="max-w-3xl">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">
            Engine reference
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            {title}
          </h1>
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">{subtitle}</p>
        </div>

        <div className="mt-12 gap-12 lg:flex lg:items-start">
          {/* Desktop TOC. Sticks under the header; mobile gets the inline list
              rendered by the page instead. */}
          <nav
            aria-label="On this page"
            className="no-scrollbar sticky top-20 hidden max-h-[calc(100dvh-6rem)] w-56 shrink-0 overflow-y-auto lg:block"
          >
            <p className="px-3 pb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              On this page
            </p>
            <ul className="space-y-0.5">
              {sections.map((s) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    aria-current={active === s.id ? "true" : undefined}
                    className={cn(
                      // The pink rail slides between entries as the highlight
                      // moves, so the TOC tracks the glide rather than blinking.
                      "block rounded-lg border-l-2 px-3 py-1.5 text-sm transition-all duration-300 ease-out",
                      active === s.id
                        ? "border-l-primary bg-muted font-medium text-foreground"
                        : "border-l-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    )}
                  >
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="min-w-0 flex-1 space-y-12">{children}</div>
        </div>
      </div>

      <style>{`
        .${LAND_CLASS} {
          border-radius: 6px;
          animation: docs-land ${LAND_MS}ms ease-out;
        }
        /* box-shadow spread rather than padding, so the wash reaches past the
         * text box without nudging the layout mid-scroll. */
        @keyframes docs-land {
          0%, 25% {
            background-color: color-mix(in oklab, var(--primary) 16%, transparent);
            box-shadow: 0 0 0 6px color-mix(in oklab, var(--primary) 16%, transparent);
          }
          100% {
            background-color: transparent;
            box-shadow: 0 0 0 6px transparent;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .${LAND_CLASS} { animation: none; }
        }
      `}</style>
    </div>
  );
}

/**
 * Owns both halves of moving around the page:
 *
 * - **scroll-spy** — an IntersectionObserver over a band just below the sticky
 *   header, so the highlight tracks the section being read rather than the one
 *   at the top of the document.
 * - **shortcuts** — one delegated click handler for every in-page `#hash` link
 *   under the shell (sidebar, mobile chips, and cross-references inside the
 *   prose). It glides instead of jumping, flashes the heading it lands on, and
 *   syncs the URL with `replaceState` so copying the link works without
 *   stacking a history entry per click.
 */
function useDocNavigation(sections: TocEntry[]) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<string | null>(sections[0]?.id ?? null);
  // A smooth scroll crosses every section in between, which would flick the
  // highlight down the whole TOC. Clicking pins the destination and ignores the
  // observer until the scroll settles.
  const pinnedRef = useRef(false);

  useEffect(() => {
    const els = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => !!el);
    if (!els.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (pinnedRef.current) return;
        // Track every section's visibility, then pick the topmost visible one —
        // a single entry can't tell us that on its own.
        const visible = entries.filter((e) => e.isIntersecting);
        if (!visible.length) return;
        visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        setActive(visible[0].target.id);
      },
      // Band from just under the header down to 60% of the viewport.
      { rootMargin: "-72px 0px -40% 0px", threshold: 0 },
    );

    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let landTimer = 0;
    let settleTimer = 0;
    let release: (() => void) | null = null;

    const onClick = (e: MouseEvent) => {
      // Leave modified clicks alone — those are "open in a new tab".
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const link = (e.target as Element | null)?.closest?.("a");
      const href = link?.getAttribute("href");
      if (!href || !href.startsWith("#") || href.length < 2) return;

      const target = document.getElementById(href.slice(1));
      if (!target) return;

      e.preventDefault();
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      // `scroll-mt-*` on the sections keeps the sticky header off the heading.
      target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
      window.history.replaceState(null, "", href);

      setActive(target.id);
      pinnedRef.current = true;
      release?.();
      release = () => {
        window.removeEventListener("scrollend", release!);
        window.clearTimeout(settleTimer);
        pinnedRef.current = false;
        release = null;
      };
      // `scrollend` where it exists, a timeout everywhere else.
      window.addEventListener("scrollend", release, { once: true });
      settleTimer = window.setTimeout(() => release?.(), SETTLE_MS);

      // Land marker on the heading, and move focus there so keyboard and
      // screen-reader users end up where the scroll did.
      const heading = target.querySelector<HTMLElement>("h2, h3") ?? target;
      window.clearTimeout(landTimer);
      root.querySelectorAll(`.${LAND_CLASS}`).forEach((el) => el.classList.remove(LAND_CLASS));
      void heading.offsetWidth; // restart the animation on a repeat click
      heading.classList.add(LAND_CLASS);
      landTimer = window.setTimeout(() => heading.classList.remove(LAND_CLASS), LAND_MS);
      target.focus({ preventScroll: true });
    };

    root.addEventListener("click", onClick);
    return () => {
      root.removeEventListener("click", onClick);
      window.clearTimeout(landTimer);
      release?.();
    };
  }, []);

  return { rootRef, active };
}
