"use client";

/**
 * Shared "chapter" primitives for the landing page.
 *
 * - `useScrollMotion` drives the scroll-focus effect: whichever chapter is
 *   nearest the vertical centre of the viewport is crisp and fully opaque;
 *   chapters scrolling away toward the edges fade and blur slightly, so the
 *   visitor's attention is pulled to the section they're actually on. Honors
 *   `prefers-reduced-motion` (no fade/blur then).
 * - `GlassPanel` is the frosted-glass plate each chapter sits on.
 */
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function useScrollMotion<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [style, setStyle] = useState<CSSProperties>({});

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight || 1;
      const elCenter = rect.top + rect.height / 2;
      const dist = Math.abs(elCenter - vh / 2) / vh; // 0 at centre → ~0.5 at edge
      const d = Math.max(0, dist - 0.12); // 12% dead-zone: near-centre stays crisp
      const focus = Math.min(1, Math.max(0, 1 - d * 1.6));
      setStyle({
        opacity: 0.35 + 0.65 * focus,
        filter: `blur(${((1 - focus) * 3).toFixed(2)}px)`,
        willChange: "opacity, filter",
      });
    };

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };

    update();
    // Capture phase so we also catch scrolls from the page's inner scroll
    // container (<main> owns the scroll now, so `window` scroll never fires).
    window.addEventListener("scroll", onScroll, { passive: true, capture: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll, { capture: true } as EventListenerOptions);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return { ref, style };
}

export function GlassPanel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-white/30 bg-background/20 shadow-lg ring-1 ring-inset ring-white/20 backdrop-blur-md dark:border-white/12 dark:bg-background/15 dark:ring-white/10",
        className,
      )}
    >
      {children}
    </div>
  );
}
