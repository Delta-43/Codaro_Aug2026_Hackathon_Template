"use client";

/**
 * Calendar demo chapter — the actual app calendar (real `MonthView` /
 * `WeekView` / `DayView`) fed static demo data, wrapped in a replica of the
 * calendar's own segmented control + header. The Month/Week/Day pills are live:
 * they switch the view, exactly like the app. No auth/context/data needed.
 * Paired with a short manual.
 */
import { useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import type { DayAvailability, MonthDensityLevel, Service, Slot, SlotStatus } from "@/types/domain";
import { MonthView } from "@/components/calendar/month-view";
import { WeekView } from "@/components/calendar/week-view";
import { DayView } from "@/components/calendar/day-view";
import {
  dayLabel,
  monthLabel,
  monthMatrix,
  todayStr,
  weekLabel,
  weekOf,
  isPastDay,
} from "@/lib/calendar";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { cn } from "@/lib/utils";

const TZ = "Europe/Warsaw";
type Zoom = "Month" | "Week" | "Day";

const SERVICE: Service = {
  // Landing-page fixture: nothing is disabled, so an empty block reads as ON.
  capabilities: {},
  id: "svc-demo",
  providerId: "prov-demo",
  name: "Demo service",
  description: "",
  bookingModel: "shared_capacity",
  slotDurationMinutes: 60,
  minSlotsPerBooking: 1,
  maxSlotsPerBooking: 3,
  priceMinorUnits: 2500,
  currency: "EUR",
  cancellationCutoffHours: 24,
  autoApprove: true,
  resourceIds: ["res-a"],
};

const STEPS = [
  "Pick a day — open days are highlighted, and the dots show how open each one is.",
  "Choose your slots — grab one, or several in a row for a longer booking.",
  "Set your party size and confirm — you get instant confirmation.",
];

function slot(date: string, hour: number, status: SlotStatus, booked: number): Slot {
  const hh = (h: number) => String(h).padStart(2, "0");
  return {
    id: `${date}-${hh(hour)}`,
    serviceId: SERVICE.id,
    resourceId: "res-a",
    startUtc: `${date}T${hh(hour)}:00:00Z`,
    endUtc: `${date}T${hh(hour + 1)}:00:00Z`,
    capacity: 4,
    bookedCount: booked,
    status,
  };
}

function buildDensity(weeks: ReturnType<typeof monthMatrix>, month: number) {
  const map = new Map<string, MonthDensityLevel>();
  for (const week of weeks) {
    for (const day of week) {
      if (day.m !== month) continue;
      map.set(day.dateStr, (((day.d * 7) % 3) + 1) as MonthDensityLevel);
    }
  }
  return map;
}

function buildAvailability(dates: string[]) {
  const byDate = new Map<string, DayAvailability>();
  for (const date of dates) {
    const slots = isPastDay(date, TZ)
      ? []
      : [
          slot(date, 7, "available", 1),
          slot(date, 9, "partially_booked", 3),
          slot(date, 12, "full", 4),
          slot(date, 14, "available", 0),
        ];
    byDate.set(date, {
      date,
      slots,
      totalCapacity: slots.length * 4,
      totalBooked: slots.reduce((n, s) => n + s.bookedCount, 0),
    });
  }
  return byDate;
}

export function CalendarDemo() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  const [zoom, setZoom] = useState<Zoom>("Month");

  const today = todayStr(TZ);
  const [y, m] = today.split("-").map(Number);
  const weeks = monthMatrix(y, m);
  const density = buildDensity(weeks, m);

  const weekDays = weekOf(today);
  const byDate = buildAvailability(weekDays.map((d) => d.dateStr));
  // Day view anchors on the first open day of the week (today or later).
  const dayAnchor = weekDays.find((d) => !isPastDay(d.dateStr, TZ))?.dateStr ?? today;

  const label =
    zoom === "Month" ? monthLabel(y, m) : zoom === "Week" ? weekLabel(weekDays) : dayLabel(dayAnchor);

  return (
    <section id="calendar" className="snap-start snap-always scroll-mt-24 px-4 pt-24 pb-10">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-6 sm:px-10">
          <div className="mb-4 flex justify-center">
            <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <CalendarDays className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground">
            The calendar your customers actually book on.
          </h2>
          <p className="mx-auto mt-2 max-w-md text-center text-sm text-foreground/80">
            Availability, density, and multi-slot booking — the real thing.
          </p>

          <div className="mt-6 grid items-start gap-6 md:grid-cols-2">
            {/* Real calendar views + the calendar's own header, replicated */}
            <div className="min-w-0 overflow-x-auto rounded-2xl border border-border/60 bg-card/80 p-3 shadow-sm backdrop-blur-md">
              <div className="mb-3 inline-flex rounded-lg border border-border bg-card p-0.5">
                {(["Month", "Week", "Day"] as Zoom[]).map((z) => (
                  <button
                    key={z}
                    type="button"
                    onClick={() => setZoom(z)}
                    aria-pressed={zoom === z}
                    className={cn(
                      "origin-bottom cursor-pointer rounded-md px-3 py-1 text-sm font-medium transition-all duration-200 ease-out hover:z-10 hover:scale-125 hover:-translate-y-0.5 hover:shadow-md",
                      zoom === z
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-primary hover:text-primary-foreground",
                    )}
                  >
                    {z}
                  </button>
                ))}
              </div>

              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1 text-muted-foreground">
                  <span className="grid size-7 place-items-center rounded-md border border-border">
                    <ChevronLeft className="size-4" aria-hidden />
                  </span>
                  <span className="grid size-7 place-items-center rounded-md border border-border">
                    <ChevronRight className="size-4" aria-hidden />
                  </span>
                  <span className="px-2 text-sm font-medium">Today</span>
                </div>
                <span className="truncate text-sm font-medium">{label}</span>
              </div>

              {zoom === "Month" ? (
                <MonthView
                  weeks={weeks}
                  densityByDate={density}
                  currentMonth={m}
                  tz={TZ}
                  onPickDay={() => setZoom("Day")}
                />
              ) : zoom === "Week" ? (
                <WeekView
                  days={weekDays}
                  byDate={byDate}
                  tz={TZ}
                  isDaySlot={false}
                  nameFor={() => "Studio A"}
                  selectedIds={new Set()}
                />
              ) : (
                <DayView
                  availability={byDate.get(dayAnchor)}
                  tz={TZ}
                  service={SERVICE}
                  isDaySlot={false}
                  nameFor={() => "Studio A"}
                  selectedIds={new Set()}
                />
              )}
            </div>

            {/* Short manual */}
            <div>
              <h3 className="text-center text-lg font-medium text-foreground">Booking, in three taps</h3>
              <ol className="mt-4 space-y-4">
                {STEPS.map((step, i) => (
                  <li key={i} className="group flex gap-3">
                    <span className="flex size-6 shrink-0 origin-center items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary shadow-sm transition-all duration-200 ease-out group-hover:scale-150 group-hover:-translate-y-0.5 group-hover:bg-primary group-hover:text-primary-foreground group-hover:shadow-lg">
                      {i + 1}
                    </span>
                    <p className="text-sm leading-relaxed text-foreground/80">{step}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </GlassPanel>
      </div>
    </section>
  );
}
