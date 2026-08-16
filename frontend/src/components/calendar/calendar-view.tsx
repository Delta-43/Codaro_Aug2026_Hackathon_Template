"use client";

/**
 * The availability centrepiece. Three zoom levels (Month · Week · Day, week
 * default), timezone-correct navigation that never pages before the current
 * period, and slot states sent by the API. Selection (Phase 6) is opt-in via
 * `onSelect`/`selectedIds`; when omitted the calendar is browse-only.
 */
import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { DayAvailability, MonthDensityLevel, Service, Slot } from "@/types/domain";
import { getAvailability, getMonthDensity, getResources } from "@/api";
import { useAsync } from "@/hooks/use-async";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { WeekView } from "@/components/calendar/week-view";
import { DayView } from "@/components/calendar/day-view";
import { MonthView } from "@/components/calendar/month-view";
import {
  addDays,
  dayLabel,
  dayRange,
  monthKey,
  monthLabel,
  monthMatrix,
  todayStr,
  weekLabel,
  weekOf,
  weekRange,
} from "@/lib/calendar";
import { zoneAbbrev } from "@/lib/format";
import { cn } from "@/lib/utils";

type Zoom = "month" | "week" | "day";

export function CalendarView({
  service,
  resourceId,
  tz,
  selectedIds,
  onSelect,
  reloadKey = 0,
}: {
  service: Service;
  resourceId: string | null;
  tz: string;
  selectedIds?: Set<string>;
  onSelect?: (slot: Slot) => void;
  /** Bump to force an availability refetch (e.g. after SLOT_UNAVAILABLE). */
  reloadKey?: number;
}) {
  const [zoom, setZoom] = useState<Zoom>("week");
  const [anchor, setAnchor] = useState<string>(() => todayStr(tz));

  const today = todayStr(tz);
  const days = useMemo(() => weekOf(anchor), [anchor]);
  const { y, m } = useMemo(() => {
    const [yy, mm] = anchor.split("-").map(Number);
    return { y: yy, m: mm };
  }, [anchor]);

  const resources = useAsync(() => getResources(service.id), [service.id]);
  const nameFor = (id: string) => resources.data?.find((r) => r.id === id)?.name ?? "";
  const isDaySlot = service.slotDurationMinutes >= 1440;

  const view = useAsync(async () => {
    if (zoom === "month") {
      const density = await getMonthDensity({
        serviceId: service.id,
        resourceId: resourceId ?? undefined,
        month: monthKey(y, m),
      });
      return { kind: "month" as const, density };
    }
    const range = zoom === "week" ? weekRange(days, tz) : dayRange(anchor, tz);
    const avail = await getAvailability({
      serviceId: service.id,
      resourceId: resourceId ?? undefined,
      fromUtc: range.fromUtc,
      toUtc: range.toUtc,
    });
    return { kind: zoom as "week" | "day", avail };
  }, [zoom, anchor, service.id, resourceId, reloadKey]);

  const selected = selectedIds ?? new Set<string>();

  // Navigation, clamped so you can view the current period but not go earlier.
  function go(dir: 1 | -1) {
    if (zoom === "week") setAnchor(addDays(anchor, dir * 7).dateStr);
    else if (zoom === "day") setAnchor(addDays(anchor, dir).dateStr);
    else {
      const d = new Date(Date.UTC(y, m - 1 + dir, 1, 12));
      setAnchor(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`);
    }
  }

  const [ty, tm] = today.split("-").map(Number);
  const prevDisabled =
    zoom === "week"
      ? weekOf(anchor)[0].dateStr <= weekOf(today)[0].dateStr
      : zoom === "day"
        ? anchor <= today
        : monthKey(y, m) <= monthKey(ty, tm);

  const label =
    zoom === "week" ? weekLabel(days) : zoom === "day" ? dayLabel(anchor) : monthLabel(y, m);

  // Group availability by local date for the week/day views.
  const byDate = useMemo(() => {
    const map = new Map<string, DayAvailability>();
    if (view.data && view.data.kind !== "month") {
      for (const d of view.data.avail) map.set(d.date, d);
    }
    return map;
  }, [view.data]);

  const densityByDate = useMemo(() => {
    const map = new Map<string, MonthDensityLevel>();
    if (view.data && view.data.kind === "month") {
      for (const c of view.data.density) map.set(c.date, c.density);
    }
    return map;
  }, [view.data]);

  return (
    <div>
      {/* Zoom control */}
      <div className="mb-3 inline-flex rounded-lg border border-border bg-card p-0.5">
        {(["month", "week", "day"] as Zoom[]).map((z) => (
          <button
            key={z}
            type="button"
            onClick={() => setZoom(z)}
            aria-pressed={zoom === z}
            className={cn(
              "rounded-md px-3 py-1 text-sm font-medium capitalize transition-colors",
              zoom === z
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {z}
          </button>
        ))}
      </div>

      {/* Navigation */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Previous"
            isDisabled={prevDisabled}
            onPress={() => go(-1)}
          >
            <ChevronLeft className="size-4" aria-hidden />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Next"
            onPress={() => go(1)}
          >
            <ChevronRight className="size-4" aria-hidden />
          </Button>
          <Button variant="ghost" size="sm" onPress={() => setAnchor(today)}>
            Today
          </Button>
        </div>
        <span className="truncate text-sm font-medium">{label}</span>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        Times in {tz} ({zoneAbbrev(new Date().toISOString(), tz)})
      </p>

      {/* Body */}
      {view.loading && !view.data ? (
        <CalendarSkeleton zoom={zoom} />
      ) : view.error ? (
        <div className="py-10 text-center">
          <p className="text-sm text-muted-foreground">Couldn&apos;t load availability.</p>
          <Button className="mt-2" onPress={view.reload}>
            Try again
          </Button>
        </div>
      ) : zoom === "month" ? (
        <MonthView
          weeks={monthMatrix(y, m)}
          densityByDate={densityByDate}
          currentMonth={m}
          tz={tz}
          onPickDay={(dateStr) => {
            setAnchor(dateStr);
            setZoom("day");
          }}
        />
      ) : zoom === "week" ? (
        <WeekView
          days={days}
          byDate={byDate}
          tz={tz}
          isDaySlot={isDaySlot}
          nameFor={nameFor}
          selectedIds={selected}
          onSelect={onSelect}
        />
      ) : (
        <DayView
          availability={byDate.get(anchor)}
          tz={tz}
          service={service}
          isDaySlot={isDaySlot}
          nameFor={nameFor}
          selectedIds={selected}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

function CalendarSkeleton({ zoom }: { zoom: Zoom }) {
  if (zoom === "day") {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (zoom === "month") {
    return <Skeleton className="h-72 w-full" />;
  }
  return (
    <div className="grid grid-cols-7 gap-1">
      {Array.from({ length: 7 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full" />
      ))}
    </div>
  );
}
