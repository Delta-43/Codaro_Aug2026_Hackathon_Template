// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import type { Slot } from "@/types/domain";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function slotRemaining(slot: Slot): number {
  return Math.max(0, slot.capacity - slot.bookedCount);
}

/** Available / partially-booked slots can be selected; the rest are inert. */
export function slotSelectable(slot: Slot): boolean {
  return slot.status === "available" || slot.status === "partially_booked";
}

const STATUS_CLASS: Record<Slot["status"], string> = {
  available: "bg-primary/10 text-primary hover:bg-primary/20",
  partially_booked: "bg-amber-500/15 text-amber-700 hover:bg-amber-500/25 dark:text-amber-300",
  full: "bg-muted text-muted-foreground/70",
  blocked: "bg-muted text-muted-foreground/60",
  past: "bg-muted/50 text-muted-foreground/50",
};

/**
 * A slot pill for the week view. `label` is the primary text (start time for
 * hourly slots, resource name for day-length slots, the view decides). State
 * is derived from `slot.status`, which the API sends explicitly.
 */
export function SlotPill({
  slot,
  label,
  selected = false,
  onSelect,
}: {
  slot: Slot;
  label: string;
  selected?: boolean;
  onSelect?: (slot: Slot) => void;
}) {
  const remaining = slotRemaining(slot);
  const interactive = slotSelectable(slot) && !!onSelect;

  const sub =
    slot.status === "partially_booked"
      ? `${remaining} of ${slot.capacity} left`
      : slot.status === "full"
        ? "Full"
        : slot.status === "blocked"
          ? "Blocked"
          : null;

  const className = cn(
    "block w-full rounded-md px-1.5 py-1 text-left text-[11px] font-medium leading-tight transition-colors",
    STATUS_CLASS[slot.status],
    slot.status === "full" ? "line-through decoration-1" : "",
    selected ? "ring-2 ring-primary ring-offset-1 ring-offset-background" : "",
    interactive ? "" : "cursor-default",
  );

  const content = (
    <>
      <span className="block truncate">{label}</span>
      {sub ? <span className="block text-[10px] font-normal opacity-80">{sub}</span> : null}
    </>
  );

  if (interactive) {
    return (
      <button
        type="button"
        onClick={() => onSelect!(slot)}
        className={cn(className, "transition-all", buttonFx.press)}
      >
        {content}
      </button>
    );
  }
  return (
    <div className={className} aria-disabled>
      {content}
    </div>
  );
}
