"use client";

import type { DayAvailability, Service, Slot } from "@/types/domain";
import { formatMoney, formatTimeRange, zoneAbbrev } from "@/lib/format";
import { slotRemaining, slotSelectable } from "@/components/calendar/slot-pill";
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
}: {
  availability: DayAvailability | undefined;
  tz: string;
  service: Service;
  isDaySlot: boolean;
  nameFor: (resourceId: string) => string;
  selectedIds: Set<string>;
  onSelect?: (slot: Slot) => void;
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
        return selectable ? (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect!(slot)}
            className={cn(className, "w-full text-left")}
          >
            {body}
          </button>
        ) : (
          <div key={slot.id} className={className}>
            {body}
          </div>
        );
      })}
    </div>
  );
}
