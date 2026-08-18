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
      const d = Math.max(0, dist - 0.28); // wide dead-zone: the panel you're on stays crisp
      const focus = Math.min(1, Math.max(0, 1 - d * 2.4));
      setStyle({
        // Gently dim panels scrolling away, but never blur them — all copy
        // stays legible/explicit even mid-scroll.
        opacity: 0.6 + 0.4 * focus,
        willChange: "opacity",
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
        // Liquid-glass plate (à la macOS): highly translucent, strong blur +
        // saturation, a bright rim plus layered inner highlights/shadows for a
        // beveled 3D glass depth rather than a flat frosted card.
        "liquid-glass relative rounded-[2rem] border border-white/40 bg-white/15 dark:border-white/15 dark:bg-white/[0.06]",
        "shadow-[0_10px_40px_-6px_rgba(0,0,0,0.25),inset_0_1px_1px_rgba(255,255,255,0.7),inset_0_-8px_24px_-12px_rgba(255,255,255,0.35)]",
        "dark:shadow-[0_10px_40px_-6px_rgba(0,0,0,0.6),inset_0_1px_1px_rgba(255,255,255,0.18),inset_0_-8px_24px_-14px_rgba(255,255,255,0.08)]",
      )}
    >
      {/* Specular sheen — a soft diagonal gloss, like light catching curved
          glass. Purely decorative, sits under the content. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] bg-gradient-to-br from-white/40 via-white/5 to-transparent dark:from-white/15"
      />
      {/* Bright top-edge highlight */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/70 to-transparent dark:via-white/30"
      />
      {/* Caller layout/padding (flex, gap, text-align, px/py) lands here on the
          real content box — and `relative` lifts it above the sheen. */}
      <div className={cn("relative", className)}>{children}</div>
    </div>
  );
}
