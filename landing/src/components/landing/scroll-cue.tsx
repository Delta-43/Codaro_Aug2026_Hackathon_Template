"use client";

/**
 * A bare bouncing arrow at the foot of the first chapter. Clicking it snaps to
 * the next chapter (its section's next sibling). Paired with the page's CSS
 * scroll-snap so a small scroll also flicks to the next plate. No label — just
 * the arrow.
 */
import type { MouseEvent } from "react";
import { ChevronDown } from "lucide-react";

export function ScrollCue() {
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
        aria-label="Scroll to next section"
        className="grid size-10 place-items-center rounded-full text-foreground/70 transition-colors hover:text-foreground"
      >
        <ChevronDown className="size-6 animate-bounce" aria-hidden />
      </button>
    </div>
  );
}
