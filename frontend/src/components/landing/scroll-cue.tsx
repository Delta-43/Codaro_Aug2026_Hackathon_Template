"use client";

/**
 * A glass "Scroll" pill placed at the foot of each chapter. Clicking it snaps
 * to the next chapter (its section's next sibling). Paired with the page's
 * CSS scroll-snap so a small scroll also flicks to the next plate rather than
 * fading gradually.
 */
import type { MouseEvent } from "react";
import { ChevronDown } from "lucide-react";

export function ScrollCue({ label = "Scroll" }: { label?: string }) {
  function onClick(e: MouseEvent<HTMLButtonElement>) {
    const section = e.currentTarget.closest("section");
    const next = section?.nextElementSibling;
    next?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="mt-6 flex justify-center">
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-background/40 px-4 py-2 text-xs font-medium uppercase tracking-wide text-foreground/80 shadow-sm ring-1 ring-inset ring-white/15 backdrop-blur-2xl transition-colors hover:text-foreground"
      >
        {label}
        <ChevronDown className="size-4 animate-bounce" aria-hidden />
      </button>
    </div>
  );
}
