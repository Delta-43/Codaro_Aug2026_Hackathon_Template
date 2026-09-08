// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import type { MonthDensityLevel } from "@/types/domain";
import { type CalDay, isPastDay, isToday } from "@/lib/calendar";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";

function DensityDots({ level }: { level: MonthDensityLevel }) {
  return (
    <span className="mt-0.5 flex h-1.5 items-center gap-0.5" aria-hidden>
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={cn("size-1 rounded-full", i <= level ? "bg-primary" : "bg-transparent")}
        />
      ))}
    </span>
  );
}

export function MonthView({
  weeks,
  densityByDate,
  currentMonth,
  tz,
  onPickDay,
}: {
  weeks: CalDay[][];
  densityByDate: Map<string, MonthDensityLevel>;
  currentMonth: number;
  tz: string;
  onPickDay: (dateStr: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 grid grid-cols-7 gap-1 text-center text-[10px] font-medium uppercase text-muted-foreground">
        {["M", "T", "W", "T", "F", "S", "S"].map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
      <div className="space-y-1">
        {weeks.map((week, wi) => (
          <div key={wi} className="grid grid-cols-7 gap-1">
            {week.map((day) => {
              const inMonth = day.m === currentMonth;
              const past = isPastDay(day.dateStr, tz);
              const today = isToday(day.dateStr, tz);
              const disabled = past || !inMonth;
              const level = inMonth && !past ? (densityByDate.get(day.dateStr) ?? 0) : 0;
              return (
                <button
                  key={day.dateStr}
                  type="button"
                  disabled={disabled}
                  onClick={() => onPickDay(day.dateStr)}
                  aria-label={day.dateStr}
                  className={cn(
                    "flex aspect-square flex-col items-center justify-center rounded-md text-sm transition-colors",
                    today ? "bg-primary/10 font-semibold text-primary" : "",
                    !inMonth
                      ? "text-muted-foreground/30"
                      : past
                        ? "text-muted-foreground/40"
                        : cn("text-foreground", buttonFx.tile),
                    disabled ? "cursor-default" : "",
                  )}
                >
                  <span>{day.d}</span>
                  <DensityDots level={level} />
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
        <span>Openness</span>
        <span className="flex items-center gap-0.5">
          <span className="size-1 rounded-full bg-primary/40" />
          <span>less</span>
        </span>
        <span className="flex items-center gap-0.5">
          <span className="size-1 rounded-full bg-primary" />
          <span className="size-1 rounded-full bg-primary" />
          <span className="size-1 rounded-full bg-primary" />
          <span>more</span>
        </span>
      </div>
    </div>
  );
}
