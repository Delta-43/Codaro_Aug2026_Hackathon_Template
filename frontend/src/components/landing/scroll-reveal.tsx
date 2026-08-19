"use client";

/**
 * Shared "chapter" primitives for the landing page.
 *
 * - `useScrollMotion` used to dim each chapter as it scrolled away from centre.
 *   That opacity (applied to the chapter's wrapper) forced the plate into an
 *   isolated compositing group, which changed how its liquid-glass
 *   `backdrop-filter` sampled the page behind it — so those plates frosted the
 *   background differently (weaker) than the footer, which never dimmed. To make
 *   every plate blur the backdrop the *same*, footer-perfect way, the dimming is
 *   gone; the hook is now inert and just hands back a ref (kept so the call
 *   sites don't all have to change). See the pinned reference: all plates should
 *   frost the flecks like the dark-mode footer.
 * - `GlassPanel` is the frosted-glass plate each chapter sits on.
 */
import { useRef, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function useScrollMotion<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  // No dimming — a full-opacity plate keeps its backdrop-filter out of a
  // compositing group, so the glass frosts the background exactly like the footer.
  return { ref, style: {} as CSSProperties };
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
        // Liquid-glass plate — the footer's clean, uniform treatment used across
        // every chapter: highly translucent, blurred + saturated (via
        // `.liquid-glass`), a bright rim, and a single soft drop shadow. No
        // diagonal sheen or inner bevels, so the glass reads the same calm, flat
        // way in light and dark (it looks best in dark). `overflow-hidden` keeps
        // the fill/blur inside the rounded corners.
        "liquid-glass relative overflow-hidden rounded-[2rem] border border-white/40 bg-white/15 dark:border-white/15 dark:bg-white/[0.06]",
        "shadow-[0_10px_40px_-6px_rgba(0,0,0,0.25)]",
      )}
    >
      {/* Caller layout/padding (flex, gap, text-align, px/py) lands on the real
          content box; `relative` keeps it above the plate. */}
      <div className={cn("relative", className)}>{children}</div>
    </div>
  );
}
