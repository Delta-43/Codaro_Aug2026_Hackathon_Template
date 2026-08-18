"use client";

/**
 * Floating glass nav pill (à la the Haven reference) over the scene. Section
 * links smooth-scroll to the anchors; the primary button is auth-aware
 * (Login → /login, or Open app → /search when signed in). Links collapse on
 * mobile, leaving just the logo + button.
 */
import Link from "next/link";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { useTheme } from "next-themes";
import { ChevronRight, Moon, Sun } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      aria-label={isDark ? "Switch to day" : "Switch to night"}
      title={isDark ? "Day" : "Night"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="grid size-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {isDark ? <Moon className="size-4" aria-hidden /> : <Sun className="size-4" aria-hidden />}
    </button>
  );
}

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#calendar", label: "Calendar" },
  { href: "#reviews", label: "Reviews" },
];

function smoothScroll(e: MouseEvent<HTMLAnchorElement>, href: string) {
  e.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
}

export function NavBar({ authed }: { authed: boolean }) {
  const linksRef = useRef<HTMLDivElement>(null);

  return (
    <nav className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <div className="flex w-full max-w-3xl items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-2 shadow-sm backdrop-blur-xl">
        <Link
          href="/"
          className="inline-block shrink-0 origin-left px-2 text-sm font-semibold tracking-tight text-foreground transition-transform duration-200 ease-out hover:scale-110"
        >
          Service<span className="text-primary">.com</span>
        </Link>
        {/* Links: horizontally scrollable on mobile (scrollbar hidden), centered on desktop. */}
        <div
          ref={linksRef}
          className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] md:justify-center [&::-webkit-scrollbar]:hidden"
        >
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={(e) => smoothScroll(e, l.href)}
              className="shrink-0 origin-center whitespace-nowrap rounded-full px-3 py-1.5 text-sm text-muted-foreground transition-all duration-200 ease-out hover:scale-110 hover:bg-muted hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>
        {/* Mobile-only affordance: the links row scrolls sideways. */}
        <button
          type="button"
          aria-label="More links"
          onClick={() => linksRef.current?.scrollBy({ left: 120, behavior: "smooth" })}
          className="grid size-7 shrink-0 place-items-center rounded-full text-muted-foreground transition-transform duration-200 ease-out hover:scale-125 hover:text-foreground md:hidden"
        >
          <ChevronRight className="landing-nudge size-4" aria-hidden />
        </button>
        <div className="flex shrink-0 items-center gap-1">
          <ThemeToggle />
          <Link
            href={authed ? "/search" : "/login"}
            className={cn(
              buttonVariants({ size: "sm" }),
              "origin-center rounded-full px-4 transition-transform duration-200 ease-out hover:scale-105",
            )}
          >
            {authed ? "Open app" : "Login"}
          </Link>
        </div>
      </div>
    </nav>
  );
}
