"use client";

import type { DayAvailability, Slot } from "@/types/domain";
import { type CalDay, isPastDay, isToday } from "@/lib/calendar";
import { formatTime } from "@/lib/format";
import { SlotPill } from "@/components/calendar/slot-pill";
import { cn } from "@/lib/utils";

export function WeekView({
  days,
  byDate,
  tz,
  isDaySlot,
  nameFor,
  selectedIds,
  onSelect,
}: {
  days: CalDay[];
  byDate: Map<string, DayAvailability>;
  tz: string;
  isDaySlot: boolean;
  nameFor: (resourceId: string) => string;
  selectedIds: Set<string>;
  onSelect?: (slot: Slot) => void;
}) {
  // On a phone, seven columns squeeze below a usable width, so the week
  // horizontally scrolls (with a legible per-column minimum) instead of the pills
  // getting clipped. The negative margin lets it bleed to the section edges.
  return (
    <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
    <div className="grid min-w-[34rem] grid-cols-7 gap-1 md:min-w-0">
      {days.map((day) => {
        const past = isPastDay(day.dateStr, tz);
        const today = isToday(day.dateStr, tz);
        const slots = byDate.get(day.dateStr)?.slots ?? [];
        return (
          <div key={day.dateStr} className="min-w-0">
            <div
              className={cn(
                "mb-1 flex flex-col items-center rounded-md py-1 text-center",
                today
                  ? "bg-primary/10 text-primary"
                  : past
                    ? "text-muted-foreground/50"
                    : "text-muted-foreground",
              )}
            >
              <span className="text-[10px] font-medium uppercase">{day.weekdayNarrow}</span>
              <span className="text-sm font-semibold">{day.d}</span>
            </div>
            <div className="space-y-1">
              {slots.length === 0 ? (
                <div className="py-1 text-center text-[10px] text-muted-foreground/40">—</div>
              ) : (
                slots.map((slot) => (
                  <SlotPill
                    key={slot.id}
                    slot={slot}
                    label={isDaySlot ? nameFor(slot.resourceId) : formatTime(slot.startUtc, tz)}
                    selected={selectedIds.has(slot.id)}
                    onSelect={onSelect}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
    </div>
  );
}
