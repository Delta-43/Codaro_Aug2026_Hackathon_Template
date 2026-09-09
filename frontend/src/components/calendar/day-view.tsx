// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import type { DayAvailability, Service, Slot } from "@/types/domain";
import { formatMoney, formatTimeRange, zoneAbbrev } from "@/lib/format";
import { slotRemaining, slotSelectable } from "@/components/calendar/slot-pill";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

function statusLine(slot: Slot, remaining: number): string {
  switch (slot.status) {
    case "available":
      return slot.capacity > 1 ? `${remaining} of ${slot.capacity} available` : "Available";
    case "partially_booked":
      return `${remaining} of ${slot.capacity} left`;
    case "full":
      return "Full";
    case "blocked":
      return "Blocked";
    case "past":
      return "Past";
  }
}

export function DayView({
  availability,
  tz,
  service,
  isDaySlot,
  nameFor,
  selectedIds,
  onSelect,
  onWaitlist,
}: {
  availability: DayAvailability | undefined;
  tz: string;
  service: Service;
  isDaySlot: boolean;
  nameFor: (resourceId: string) => string;
  selectedIds: Set<string>;
  onSelect?: (slot: Slot) => void;
  /** Offered on FULL slots only, and only where the service runs a queue
   *  (`timing.waitlist`). Kept separate from `onSelect` on purpose: joining a
   *  queue is not booking, and conflating them would let a tap that means
   *  "notify me" read as a commitment. */
  onWaitlist?: (slot: Slot) => void;
}) {
  const slots = availability?.slots ?? [];
  if (slots.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">No times this day.</p>;
  }

  return (
    <div className="space-y-2">
      {slots.map((slot) => {
        const remaining = slotRemaining(slot);
        const selectable = slotSelectable(slot) && !!onSelect;
        const selected = selectedIds.has(slot.id);
        const body = (
          <>
            <div className="min-w-0">
              <div className="text-sm font-medium">
                {formatTimeRange(slot.startUtc, slot.endUtc, tz)}{" "}
                <span className="text-xs font-normal text-muted-foreground">
                  {zoneAbbrev(slot.startUtc, tz)}
                </span>
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {isDaySlot ? `${nameFor(slot.resourceId)} · ` : ""}
                {statusLine(slot, remaining)}
              </div>
            </div>
            <div className="shrink-0 text-sm font-medium">
              {formatMoney(service.priceMinorUnits, service.currency)}
            </div>
          </>
        );
        const className = cn(
          "flex items-center justify-between gap-3 rounded-xl border p-3",
          selected ? "border-primary ring-1 ring-primary" : "border-border",
          selectable ? "hover:bg-muted/50" : "opacity-60",
        );
        const waitlistable = slot.status === "full" && !!onWaitlist;
        return selectable ? (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect!(slot)}
            className={cn(className, "w-full text-left", buttonFx.surface)}
          >
            {body}
          </button>
        ) : waitlistable ? (
          <div key={slot.id} className={cn(className, "opacity-100")}>
            {body}
            <button
              type="button"
              onClick={() => onWaitlist!(slot)}
              className={cn(
                "shrink-0 rounded-lg border border-border px-2.5 py-1 text-xs font-medium transition-all hover:bg-muted",
                buttonFx.press,
              )}
            >
              Join waitlist
            </button>
          </div>
        ) : (
          <div key={slot.id} className={className}>
            {body}
          </div>
        );
      })}
    </div>
  );
}
