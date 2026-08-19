"use client";

/**
 * Brand link that smooth-scrolls the landing back to the very top. The landing
 * page scrolls *inside* its `<main>` container (not the window), so a plain
 * `href="/"` would hard-reload instead of gliding up. We find that scroll
 * container and animate it to the top; the `href="/"` stays as a no-JS
 * fallback. Used by the nav pill and the footer brand.
 */
import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";

export function ScrollTopLink({
  className,
  children,
  ariaLabel,
}: {
  className?: string;
  children: ReactNode;
  ariaLabel?: string;
}) {
  function toTop(e: MouseEvent<HTMLAnchorElement>) {
    const main = e.currentTarget.closest("main");
    if (main) {
      e.preventDefault();
      main.scrollTo({ top: 0, behavior: "smooth" });
    }
  }
  return (
    <Link href="/" aria-label={ariaLabel} onClick={toTop} className={className}>
      {children}
    </Link>
  );
}
