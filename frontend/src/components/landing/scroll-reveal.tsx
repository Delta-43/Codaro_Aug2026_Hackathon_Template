"use client";

/**
 * `GlassPanel` — the frosted-glass plate the login form sits on. Frozen copy
 * of landing/'s component (see docs/issues/97-...); trimmed to just this,
 * since login/page.tsx doesn't need the landing-only `useScrollMotion` hook
 * that ships alongside it there.
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

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
