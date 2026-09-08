// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * `ScrollZoomReveal` — a one-shot, threshold-triggered "scale up + fade in"
 * reveal for `/showcase` panels, in the spirit of Apple product pages: each
 * wrapped child starts slightly scaled-down and transparent, then eases up
 * to full size/opacity once it crosses ~25-30% into the viewport. Unlike a
 * continuous scroll-position scrub, this uses a single `IntersectionObserver`
 * per instance and *stops observing* the moment it reveals — it never
 * re-hides on scroll-out, which would read as flickery/broken on repeat
 * scrolling.
 *
 * IMPORTANT — backdrop-filter compositing: an earlier scroll-reveal in this
 * codebase (`components/landing/scroll-reveal.tsx`'s `useScrollMotion`, now
 * intentionally inert) broke `backdrop-filter` glass panels when a
 * scroll-driven transform landed on the *same* element as the
 * `backdrop-filter` — the transform forced a new compositing context that
 * changed how the blur sampled the backdrop behind it. To avoid repeating
 * that bug: this component's transform/opacity classes live on the *outer*
 * wrapper `<div>` this component renders, never on whatever glass/blur
 * element a caller puts inside `children` — so if a panel passed in here
 * uses `backdrop-filter` (e.g. `GlassPanel`'s `.liquid-glass`), that panel
 * must stay a plain, untransformed child of this wrapper, not merge its own
 * className onto this wrapper.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function ScrollZoomReveal({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setRevealed(true);
          observer.disconnect(); // one-shot — never re-hide on scroll-out
        }
      },
      { threshold: 0.28 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-700 ease-out",
        revealed ? "scale-100 opacity-100" : "scale-90 opacity-0",
        // Respect prefers-reduced-motion in CSS rather than by branching in
        // the effect: the panel renders fully visible/unscaled with no
        // transition, whatever the observer has (or hasn't) seen yet.
        "motion-reduce:scale-100 motion-reduce:opacity-100 motion-reduce:transition-none",
        className,
      )}
      data-revealed={revealed}
    >
      {children}
    </div>
  );
}
