"use client";

/**
 * Business bookings calendar with the three standard views (month / week / day),
 * week as the default — matching the customer calendar's language but laid out
 * for a provider glancing across everything on their plate. Bookings can stack;
 * clicking one calls `onOpen`. Date math is delegated to `lib/calendar` (tz-aware,
 * DST-safe); times render via `lib/format`.
 */
import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { DemoBooking } from "@/lib/business-demo";
import {
  addDays,
  dayLabel,
  isToday,
  monthLabel,
  monthMatrix,
  todayStr,
  weekLabel,
  weekOf,
  type CalDay,
} from "@/lib/calendar";
import { formatTime } from "@/lib/format";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

type View = "month" | "week" | "day";

const STATUS_DOT: Record<DemoBooking["status"], string> = {
  confirmed: "bg-primary",
  completed: "bg-muted-foreground",
  pending: "bg-amber-500",
};
const STATUS_PILL: Record<DemoBooking["status"], string> = {
  confirmed: "border-primary/30 bg-primary/10 text-primary",
  completed: "border-border bg-muted text-muted-foreground",
  pending: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

function localDateStr(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

export function BookingCalendar({
  bookings,
  timezone,
  onOpen,
  defaultView = "week",
  compact = false,
}: {
  bookings: DemoBooking[];
  timezone: string;
  onOpen?: (b: DemoBooking) => void;
  defaultView?: View;
  compact?: boolean;
}) {
  const [view, setView] = useState<View>(defaultView);
  const [anchor, setAnchor] = useState<string>(() => todayStr(timezone));

  // Group bookings by local day, each list sorted by start.
  const byDay = useMemo(() => {
    const map = new Map<string, DemoBooking[]>();
    for (const b of bookings) {
      const key = localDateStr(b.startUtc, timezone);
      (map.get(key) ?? map.set(key, []).get(key)!).push(b);
    }
    for (const list of map.values()) list.sort((a, b) => a.startUtc.localeCompare(b.startUtc));
    return map;
  }, [bookings, timezone]);

  function shift(dir: -1 | 1) {
    if (view === "day") setAnchor(addDays(anchor, dir).dateStr);
    else if (view === "week") setAnchor(addDays(anchor, dir * 7).dateStr);
    else {
      const [y, m] = anchor.split("-").map(Number);
      const nm = new Date(Date.UTC(y, m - 1 + dir, 1, 12));
      setAnchor(
        `${nm.getUTCFullYear()}-${String(nm.getUTCMonth() + 1).padStart(2, "0")}-01`,
      );
    }
  }

  const [ay, am] = anchor.split("-").map(Number);
  const week = weekOf(anchor);
  const title =
    view === "day" ? dayLabel(anchor) : view === "week" ? weekLabel(week) : monthLabel(ay, am);

  return (
    <div className="rounded-2xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2.5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => shift(-1)}
            aria-label="Previous"
            className={cn("grid size-7 place-items-center rounded-lg text-muted-foreground transition-all hover:bg-muted hover:text-foreground", buttonFx.press)}
          >
            <ChevronLeft className="size-4" aria-hidden />
          </button>
          <button
            onClick={() => setAnchor(todayStr(timezone))}
            className={cn(buttonFx.heading, "min-w-0 truncate px-1 text-sm font-semibold")}
            title="Jump to today"
          >
            {title}
          </button>
          <button
            onClick={() => shift(1)}
            aria-label="Next"
            className={cn("grid size-7 place-items-center rounded-lg text-muted-foreground transition-all hover:bg-muted hover:text-foreground", buttonFx.press)}
          >
            <ChevronRight className="size-4" aria-hidden />
          </button>
        </div>
        <Segmented view={view} onChange={setView} />
      </div>

      {view === "month" && (
        <MonthView
          year={ay}
          month={am}
          byDay={byDay}
          timezone={timezone}
          onPickDay={(d) => {
            setAnchor(d);
            setView("day");
          }}
        />
      )}
      {view === "week" && (
        <WeekView days={week} byDay={byDay} timezone={timezone} onOpen={onOpen} compact={compact} />
      )}
      {view === "day" && (
        <DayView dateStr={anchor} items={byDay.get(anchor) ?? []} timezone={timezone} onOpen={onOpen} />
      )}
    </div>
  );
}

function Segmented({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const opts: View[] = ["month", "week", "day"];
  return (
    <div className="flex shrink-0 items-center gap-0.5 rounded-lg bg-muted p-0.5 text-xs font-medium">
      {opts.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          aria-pressed={view === o}
          className={cn(
            "shrink-0 rounded-md px-2 py-1 capitalize transition-all",
            buttonFx.press,
            view === o ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-primary",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

function MonthView({
  year,
  month,
  byDay,
  timezone,
  onPickDay,
}: {
  year: number;
  month: number;
  byDay: Map<string, DemoBooking[]>;
  timezone: string;
  onPickDay: (dateStr: string) => void;
}) {
  const weeks = monthMatrix(year, month);
  return (
    <div className="p-2">
      <div className="grid grid-cols-7 text-center text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
          <div key={i} className="py-1">
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {weeks.flat().map((c) => {
          const items = byDay.get(c.dateStr) ?? [];
          const inMonth = c.m === month;
          return (
            <button
              key={c.dateStr}
              onClick={() => onPickDay(c.dateStr)}
              className={cn(
                "flex min-h-[52px] flex-col items-stretch gap-0.5 rounded-lg border border-transparent p-1 text-left transition-colors hover:border-border",
                buttonFx.tile,
                !inMonth && "opacity-40",
              )}
            >
              <span
                className={cn(
                  "text-[11px] font-medium",
                  isToday(c.dateStr, timezone)
                    ? "grid size-5 place-items-center justify-self-start rounded-full bg-primary text-primary-foreground"
                    : "text-muted-foreground",
                )}
              >
                {c.d}
              </span>
              <div className="flex flex-wrap gap-0.5">
                {items.slice(0, 3).map((b) => (
                  <span key={b.id} className={cn("size-1.5 rounded-full", STATUS_DOT[b.status])} />
                ))}
              </div>
              {items.length > 3 ? (
                <span className="text-[9px] text-muted-foreground">+{items.length - 3}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function WeekView({
  days,
  byDay,
  timezone,
  onOpen,
  compact,
}: {
  days: CalDay[];
  byDay: Map<string, DemoBooking[]>;
  timezone: string;
  onOpen?: (b: DemoBooking) => void;
  compact?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[560px] grid-cols-7">
        {days.map((c) => {
          const items = byDay.get(c.dateStr) ?? [];
          const today = isToday(c.dateStr, timezone);
          return (
            <div key={c.dateStr} className="min-w-0 border-l border-border first:border-l-0">
              <div
                className={cn(
                  "flex flex-col items-center gap-0.5 border-b border-border py-1.5",
                  today && "bg-primary/5",
                )}
              >
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {c.weekdayShort}
                </span>
                <span
                  className={cn(
                    "grid size-6 place-items-center rounded-full text-xs font-semibold",
                    today ? "bg-primary text-primary-foreground" : "text-foreground",
                  )}
                >
                  {c.d}
                </span>
              </div>
              <div
                className={cn(
                  "flex flex-col gap-1 p-1",
                  compact ? "min-h-[120px]" : "min-h-[220px]",
                )}
              >
                {items.length === 0 ? (
                  <span className="mt-2 text-center text-[10px] text-muted-foreground/60">—</span>
                ) : (
                  items.map((b) => (
                    <button
                      key={b.id}
                      onClick={() => onOpen?.(b)}
                      className={cn(
                        "rounded-md border px-1.5 py-1 text-left text-[10px] leading-tight transition-all",
                        buttonFx.press,
                        STATUS_PILL[b.status],
                      )}
                    >
                      <span className="block font-semibold tabular-nums">
                        {formatTime(b.startUtc, timezone)}
                      </span>
                      {!compact && <span className="block truncate">{b.title}</span>}
                    </button>
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

function DayView({
  dateStr,
  items,
  timezone,
  onOpen,
}: {
  dateStr: string;
  items: DemoBooking[];
  timezone: string;
  onOpen?: (b: DemoBooking) => void;
}) {
  if (items.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted-foreground">
        Nothing booked on {dayLabel(dateStr)}.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((b) => (
        <li key={b.id}>
          <button
            onClick={() => onOpen?.(b)}
            className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
          >
            <span className={cn("h-8 w-1 shrink-0 rounded-full", STATUS_DOT[b.status])} />
            <span className="w-16 shrink-0 text-sm font-semibold tabular-nums">
              {formatTime(b.startUtc, timezone)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{b.title}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {b.client}
                {b.partySize > 1 ? ` · party of ${b.partySize}` : ""}
              </span>
            </span>
            <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[11px] capitalize", STATUS_PILL[b.status])}>
              {b.status}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
