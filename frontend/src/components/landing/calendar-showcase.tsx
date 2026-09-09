// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Calendar showcase: the calendar chapter on a liquid-glass plate, same as the
 * other landing chapters, floating over the shared particle backdrop. A
 * synthetic cursor plays a short, one-time tour of the *real* app calendar:
 * it clicks Month and glides across a few open days, switches to Week then Day
 * lighting up example slots, picks one and books it on the real booking
 * control. When the tour finishes the calendar zooms out a little and an
 * "Book in three steps" note reveals underneath it, one line at a time.
 *
 * The show plays once each time the section enters view (it does not loop);
 * scrolling away and back replays it. The moment a visitor clicks any control
 * themselves the tour stops and the calendar is theirs to drive. Reduced-motion
 * visitors get a static calendar.
 *
 * The calendar is the genuine `MonthView` / `WeekView` / `DayView` fed static
 * demo data, so what visitors watch is exactly what they'll use.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import type { DayAvailability, MonthDensityLevel, Service, Slot } from "@/types/domain";
import { MonthView } from "@/components/calendar/month-view";
import { WeekView } from "@/components/calendar/week-view";
import { DayView } from "@/components/calendar/day-view";
import {
  dayLabel,
  isPastDay,
  isToday,
  monthLabel,
  monthMatrix,
  todayStr,
  weekLabel,
  weekOf,
} from "@/lib/calendar";
import { GlassPanel } from "@/components/landing/scroll-reveal";
import { buttonVariants } from "@/components/ui/button";
import { buttonFx } from "@/config/buttons";
import { formatTimeRange } from "@/lib/format";
import { cn } from "@/lib/utils";

const TZ = "Europe/Warsaw";
type Zoom = "Month" | "Week" | "Day";

const SERVICE: Service = {
  capabilities: {},
  unitKind: "time_slot",
  party: { mode: "individual", min: 1, max: null, composition: [], matchResourceCapacity: false },
  subject: { enabled: false, noun: "Subject", fields: [] },
  options: [],
  sequence: { enabled: false, steps: 1, minGapHours: 0, maxGapHours: null },
  paymentSchedule: [],
  locationModes: ["on_site"],
  locationDefault: "on_site",
  pricingModel: "fixed",
  rateUnit: "slot",
  paymentFlow: "none",
  billingCycle: "none",
  prerequisites: [],
  recurrence: { enabled: false, patterns: [], maxOccurrences: 1 },
  waitlist: { enabled: false },
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

// Dash-free, matching the rest of the landing copy.
const STEPS: [string, string][] = [
  ["Pick a resource", "Day availability and month density come off one occupancy view."],
  ["Hold a slot", "Book outright or send a request the owner approves. Config decides which."],
  ["Change your mind", "Reschedule and cancel obey the same per-service cutoff rules."],
];

function slot(date: string, hour: number, status: Slot["status"], booked: number): Slot {
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

// A few simple example slots per day, enough to make the calendar look lived-in
// for the tour: an open morning, a busy late-morning, a full noon, an open
// afternoon.
function buildAvailability(dates: string[]) {
  const byDate = new Map<string, DayAvailability>();
  for (const date of dates) {
    const slots = isPastDay(date, TZ)
      ? []
      : [
          slot(date, 9, "available", 1),
          slot(date, 11, "partially_booked", 3),
          slot(date, 13, "full", 4),
          slot(date, 16, "available", 0),
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

const HL = ["bg-primary/10", "text-primary"];
const sleep = (ms: number, ref: React.MutableRefObject<number | null>) =>
  new Promise<void>((res) => {
    ref.current = window.setTimeout(res, ms);
  });

export function CalendarShowcase() {
  const [zoom, setZoom] = useState<Zoom>("Month");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [booked, setBooked] = useState(false);
  const [finished, setFinished] = useState(false); // tour done → zoom out + reveal steps
  // Which of the three steps the tour is currently demonstrating (-1 before it
  // starts). On wide screens the steps sit beside the calendar and light up in
  // time with the cursor, so the note narrates the tour instead of arriving
  // after it.
  const [stage, setStage] = useState(-1);
  // `ms` travels with the position so each hop can time itself: a fixed
  // duration makes a 20px nudge take as long as a glide across the plate,
  // which is most of what read as robotic.
  const [cursor, setCursor] = useState({ x: 40, y: 40, ms: 620 });
  // Mirrors `cursor` for the tour's own maths, which runs outside React's
  // render cycle and would otherwise close over a stale position.
  const cursorRef = useRef({ x: 40, y: 40 });
  const [down, setDown] = useState(false);
  const [ready, setReady] = useState(false); // cursor has moved at least once
  const [inView, setInView] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [takenOver, setTakenOver] = useState(false);

  const sectionRef = useRef<HTMLElement>(null);
  const plateRef = useRef<HTMLDivElement>(null);
  const viewsRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<HTMLDivElement>(null);
  const scaleRef = useRef(1);
  const [fit, setFit] = useState<{ scale: number; h: number | null }>({ scale: 1, h: null });
  const timerRef = useRef<number | null>(null);
  const runIdRef = useRef(0);
  const takenOverRef = useRef(false);

  // Fit the whole plate to the viewport height so it's never clipped on short
  // screens (the page snap-scrolls, so a plate taller than the screen can't be
  // scrolled into full view). Measure the plate's natural, unscaled height and
  // scale it down only when it wouldn't fit; on tall screens the scale is 1 and
  // the plate keeps its full max-w-4xl width, matching the other chapters. The
  // ResizeObserver reruns it when the steps reveal grows the plate.
  useEffect(() => {
    const el = fitRef.current;
    if (!el) return;
    const recompute = () => {
      const natural = el.offsetHeight; // layout height, unaffected by the transform
      if (!natural) return;
      const avail = window.innerHeight - 56; // section py-6 + a small buffer
      const scale = Math.max(0.55, Math.min(1, avail / natural));
      const h = Math.round(natural * scale);
      // Sub-pixel churn from the ResizeObserver would otherwise re-render (and
      // visibly nudge) the plate for changes nobody asked to see.
      setFit((prev) =>
        Math.abs(prev.scale - scale) < 0.005 && prev.h !== null && Math.abs(prev.h - h) < 2
          ? prev
          : { scale, h },
      );
      scaleRef.current = scale;
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(el);
    window.addEventListener("resize", recompute);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", recompute);
    };
  }, []);

  const today = todayStr(TZ);
  const [y, m] = today.split("-").map(Number);
  const weeks = useMemo(() => monthMatrix(y, m), [y, m]);
  const density = useMemo(() => buildDensity(weeks, m), [weeks, m]);
  const weekDays = useMemo(() => weekOf(today), [today]);
  const byDate = useMemo(() => buildAvailability(weekDays.map((d) => d.dateStr)), [weekDays]);
  const dayAnchor = weekDays.find((d) => !isPastDay(d.dateStr, TZ))?.dateStr ?? today;
  const dayAvail = byDate.get(dayAnchor);
  // The slot the tour books: first genuinely selectable time on the anchor day.
  const bookSlot = dayAvail?.slots.find((s) => s.status === "available") ?? null;

  // A handful of in-month, bookable dates for the cursor to sweep across.
  const sweepDates = useMemo(() => {
    const out: string[] = [];
    for (const week of weeks) {
      for (const day of week) {
        if (day.m !== m || isPastDay(day.dateStr, TZ) || isToday(day.dateStr, TZ)) continue;
        out.push(day.dateStr);
      }
    }
    // ~5 spread across the month
    const step = Math.max(1, Math.floor(out.length / 5));
    return out.filter((_, i) => i % step === 0).slice(0, 5);
  }, [weeks, m]);

  const label = zoom === "Month" ? monthLabel(y, m) : zoom === "Week" ? weekLabel(weekDays) : dayLabel(dayAnchor);
  const selectedIds = useMemo(() => new Set(selectedId ? [selectedId] : []), [selectedId]);

  // A real visitor click on any control stops the tour and hands them the wheel.
  const takeOver = useCallback(() => {
    if (takenOverRef.current) return;
    takenOverRef.current = true;
    runIdRef.current++; // abandon the running sequence
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setTakenOver(true);
    setReady(false); // hide the synthetic cursor
    // Leave `finished` as-is: the steps stay/appear so the visitor keeps the
    // guidance while they drive.
  }, []);

  // Detect reduced-motion once, and watch whether the section is on screen.
  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const el = sectionRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        setInView(e.isIntersecting);
        // Leaving the section clears any take-over, so returning replays fresh.
        if (!e.isIntersecting) {
          takenOverRef.current = false;
          setTakenOver(false);
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // The autoplay tour. Plays once each time the section (re-)enters view, unless
  // motion is reduced or the visitor has taken over. Every await is guarded by a
  // run id + the take-over flag, so a pause/unmount/click abandons it cleanly.
  useEffect(() => {
    if (!inView || reduced || takenOverRef.current) return;

    // Fresh start on (re-)entering view.
    const myId = ++runIdRef.current;
    setSelectedId(null);
    setBooked(false);
    setFinished(false);
    setReady(false);
    setZoom("Month");

    const alive = () => runIdRef.current === myId && !takenOverRef.current;

    const q = (sel: string) => plateRef.current?.querySelector(sel) ?? null;
    const viewButtons = () =>
      Array.from(viewsRef.current?.querySelectorAll("button:not([disabled])") ?? []);

    // A target is only aimable if it's a real, on-screen, non-disabled element
    // whose centre falls inside the calendar plate. This is what stops the
    // cursor drifting to an empty corner: a bad/absent target is skipped and the
    // cursor simply stays put (hidden until the first genuine target).
    const aimAt = (el: Element | null): { x: number; y: number } | null => {
      const plate = plateRef.current;
      if (!plate || !el || !el.isConnected) return null;
      if (el instanceof HTMLButtonElement && el.disabled) return null;
      const pr = plate.getBoundingClientRect();
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return null;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      if (cx < pr.left || cx > pr.right || cy < pr.top || cy > pr.bottom) return null;
      // Screen distances are scaled by the fit transform; divide back to the
      // plate's local (unscaled) coordinate system the cursor is positioned in.
      const s = scaleRef.current || 1;
      return { x: (cx - pr.left) / s, y: (cy - pr.top) / s };
    };

    // Poll briefly for an element that a just-swapped view still has to render.
    async function waitFor(sel: string): Promise<Element | null> {
      for (let i = 0; i < 12; i++) {
        const el = q(sel);
        if (el) return el;
        if (!alive()) return null;
        await sleep(60, timerRef);
      }
      return null;
    }

    // Move to a *real* element (skips silently if it isn't there), optional
    // click bounce, optional transient highlight. Never moves to a phantom.
    async function point(
      el: Element | null,
      opts: { click?: boolean; hl?: boolean; hold?: number } = {},
    ) {
      // Only ever aim at a real, still-mounted, in-plate target, never a
      // phantom, never an empty corner.
      if (!alive()) return;
      const at = aimAt(el);
      if (!el || !at) return;

      // Time the hop by how far it actually is, the way a hand does: short
      // corrections are quick, long crossings take longer, both clamped so
      // nothing snaps or drags.
      const from = cursorRef.current;
      const dist = Math.hypot(at.x - from.x, at.y - from.y);
      const ms = Math.round(Math.min(760, Math.max(240, dist * 1.15)));
      cursorRef.current = at;
      setCursor({ ...at, ms });
      setReady(true);

      // Wait for the cursor to ARRIVE, plus a beat to settle. This used to be a
      // flat 400ms against a 620ms transition, so every click and highlight
      // fired while the pointer was still a third of the way short of its
      // target, hitting things it had visibly not reached.
      await sleep(ms + 90, timerRef);
      if (!alive() || !el.isConnected) return;
      if (opts.click) {
        setDown(true);
        await sleep(150, timerRef);
        setDown(false);
        if (!alive()) return;
      }
      if (opts.hl) el.classList.add(...HL);
      await sleep(opts.hold ?? 420, timerRef);
      if (opts.hl) el.classList.remove(...HL);
    }

    async function run() {
      setStage(-1);
      // Dwell times below are trimmed to pay for the longer, distance-timed
      // hops, so the tour reads smoother without running noticeably longer.
      await sleep(350, timerRef);
      if (!alive()) return;

      // 1) Month, sweep a few open days.
      setStage(0);
      await point(await waitFor('[data-demo-view="Month"]'), { click: true });
      for (const d of sweepDates.slice(0, 3)) {
        if (!alive()) return;
        await point(q(`[aria-label="${d}"]`), { hl: true, hold: 200 });
      }

      // 2) Week, light up the example slots.
      if (!alive()) return;
      setStage(1);
      await point(q('[data-demo-view="Week"]'), { click: true });
      setZoom("Week");
      await waitFor('[data-demo-view="Week"][aria-pressed="true"]');
      for (const b of viewButtons().slice(0, 3)) {
        if (!alive()) return;
        await point(b, { hl: true, hold: 190 });
      }

      // 3) Day, glide the times, then select one.
      if (!alive()) return;
      await point(q('[data-demo-view="Day"]'), { click: true });
      setZoom("Day");
      await waitFor('[data-demo-view="Day"][aria-pressed="true"]');
      const dayBtns = viewButtons();
      for (const b of dayBtns.slice(0, 2)) {
        if (!alive()) return;
        await point(b, { hl: true, hold: 190 });
      }
      let didSelect = false;
      setStage(2);
      if (bookSlot) {
        const target = await waitFor(`[data-demo-slot="${bookSlot.id}"]`);
        if (target) {
          await point(target, { click: true, hold: 300 });
          setSelectedId(bookSlot.id);
          didSelect = true;
          await sleep(430, timerRef);
        }
      }

      // 4) Book, only once the selection landed and the real button is on
      //    screen. The button only exists after a slot is picked, so the cursor
      //    never clicks it before it appears (and we never fake the confirm).
      if (!alive()) return;
      if (didSelect) {
        const bookBtn = await waitFor('[data-demo="book"]');
        if (bookBtn) {
          await point(bookBtn, { click: true, hold: 220 });
          setBooked(true);
          await sleep(1300, timerRef);
        }
      }

      // 5) Done, hide the cursor, zoom the calendar out, reveal the three steps
      //    underneath it (staggered via CSS). No loop; replays on re-entry.
      if (!alive()) return;
      setReady(false);
      setFinished(true);
    }

    void run();

    return () => {
      runIdRef.current++;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [inView, reduced, sweepDates, bookSlot, takenOver]);

  const showBookBar = zoom === "Day" && !!selectedId && !booked;
  // The tour finishing OR a visitor taking over both zoom the calendar out and
  // reveal the three-step note beneath it.
  const revealed = finished || takenOver;

  return (
    <section
      id="calendar"
      ref={sectionRef}
      className="relative flex min-h-screen snap-start snap-always flex-col items-center px-4 py-6 [justify-content:safe_center]"
    >
      {/* Liquid-glass plate, same material and width family as the other
          chapters, floating over the shared particle backdrop. Holds the real
          calendar and, once the tour ends (or a visitor takes over), the
          "Book in three steps" note beneath it. */}
      <div
        className="mx-auto w-full max-w-4xl transition-[height] duration-300 ease-out"
        style={{ height: fit.h ?? undefined }}
      >
        <div
          ref={fitRef}
          className="origin-top transition-transform duration-300 ease-out"
          style={{ transform: `scale(${fit.scale})` }}
        >
        <GlassPanel className="px-6 py-4 sm:px-10 sm:py-6">
          {/* Calendar on the glass; when the tour ends (or a visitor takes over)
              the "three steps" note reveals underneath it, full-width plates so
              nothing crowds or overlaps. The calendar stays compact so the whole
              chapter still fits one screen. */}
          {/* Two columns from `lg`: the calendar is only 20rem wide, so on a
              max-w-4xl plate it used to sit as a narrow strip in the middle of a
              mostly empty card. The steps take the space beside it instead of
              stacking underneath, which fills the plate AND keeps the chapter
              short enough that the fit-scale rarely has to shrink it. Below
              `lg` it stacks exactly as before. */}
          <div className="lg:grid lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-center lg:gap-10">
          <div ref={plateRef} className="relative mx-auto w-full max-w-[20rem]">
            {/* Segmented control */}
            <div className="mb-3 inline-flex rounded-lg border border-border bg-card p-0.5">
          {(["Month", "Week", "Day"] as Zoom[]).map((z) => (
            <button
              key={z}
              type="button"
              data-demo-view={z}
              onClick={() => {
                takeOver();
                setZoom(z);
              }}
              aria-pressed={zoom === z}
              className={cn(
                "cursor-pointer rounded-md px-3 py-1 text-sm font-medium transition-colors",
                zoom === z ? "bg-primary text-primary-foreground" : "text-muted-foreground",
              )}
            >
              {z}
            </button>
          ))}
        </div>

        {/* Header row */}
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

        {/* Views */}
        {/* Tall enough for Month, which is the tallest of the three: a 20rem
            column of `aspect-square` cells is ~322px once the weekday header and
            the openness legend are counted, and Day needs a touch more again. Without this the box sized to each
            view in turn, so the plate jumped ~50px every time the tour switched
            Month → Week → Day, and the fit-scale then rescaled the whole card on
            top of that. Week and Day simply sit in a taller box. */}
        <div ref={viewsRef} className="min-h-[22rem]">
          {zoom === "Month" ? (
            // Narrower, centred month grid: its cells are aspect-square, so a
            // narrower width makes the whole month shorter, bringing the plate
            // down to the same height as the Week/Day modes instead of towering
            // above them. Real layout (not a transform), so the tour cursor still
            // aims at the day cells correctly.
            <div className="mx-auto max-w-[13.5rem]">
              <MonthView
                weeks={weeks}
                densityByDate={density}
                currentMonth={m}
                tz={TZ}
                onPickDay={() => {
                  takeOver();
                  setZoom("Day");
                }}
              />
            </div>
          ) : zoom === "Week" ? (
            <WeekView
              days={weekDays}
              byDate={byDate}
              tz={TZ}
              isDaySlot={false}
              nameFor={() => "Resource A"}
              selectedIds={selectedIds}
              onSelect={(s) => {
                takeOver();
                setSelectedId(s.id);
              }}
            />
          ) : (
            <div className="[&_[data-demo-slot]]:contents">
              {/* wrap so the day rows can be targeted by slot id */}
              <DemoDayView
                availability={dayAvail}
                selectedIds={selectedIds}
                onSelect={(s) => {
                  takeOver();
                  setSelectedId(s.id);
                }}
              />
            </div>
          )}
        </div>

        {/* Booking control, the real button design; appears once a slot is
            picked, then flips to a confirmation, exactly like the app. */}
        {/* Tall enough for the confirmation panel, which is two lines and so
            taller than the button it replaces. Sized for the larger of the two
            states, or booking nudged the whole plate down by ~9px. */}
        <div className="mt-4 min-h-[4.25rem]">
          {booked ? (
            <div className="flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
                <CheckIcon />
              </span>
              <div className="min-w-0 text-sm">
                <p className="font-medium text-foreground">Date reserved</p>
                {bookSlot && (
                  <p className="truncate text-xs text-muted-foreground">
                    {formatTimeRange(bookSlot.startUtc, bookSlot.endUtc, TZ)} · Resource A
                  </p>
                )}
              </div>
            </div>
          ) : showBookBar ? (
            <button
              type="button"
              data-demo="book"
              onClick={() => {
                takeOver();
                setBooked(true);
              }}
              className={cn(buttonVariants({ size: "lg" }), buttonFx.pill, "w-full")}
            >
              Reserve this date
            </button>
          ) : (
            <p className="px-1 py-3 text-center text-xs text-muted-foreground">
              Pick a date to reserve.
            </p>
          )}
        </div>

        {/* Synthetic cursor */}
        {ready && !reduced && (
          <div
            aria-hidden
            className="pointer-events-none absolute left-0 top-0 z-30"
            style={{
              transform: `translate(${cursor.x}px, ${cursor.y}px)`,
              // Longer tail than the standard curve: the pointer leaves
              // decisively and settles gently, which is what reads as smooth.
              transition: `transform ${cursor.ms}ms cubic-bezier(0.4, 0, 0.15, 1)`,
            }}
          >
            <div className={cn("transition-transform duration-150", down ? "scale-90" : "scale-100")}>
              <CursorArrow />
              {down && (
                <span className="absolute left-0 top-0 -z-10 size-6 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-full bg-primary/40" />
              )}
            </div>
          </div>
        )}
          </div>

          {/* "Book in three steps", revealed under the calendar once the tour
              ends (or a visitor takes over). Grows in with the grid-rows trick;
              the heading, the bouncing down-arrow and each plate ease in one by
              one, Apple-style. Full-width interactive plates, stacked. */}
          <div
            className={cn(
              "grid transition-[grid-template-rows] duration-[900ms] ease-out",
              // Always open in the side column; the grow-in is for the stacked
              // layout, where collapsing keeps the plate short until the payoff.
              revealed ? "grid-rows-[1fr]" : "grid-rows-[0fr] lg:grid-rows-[1fr]",
            )}
          >
            {/* The clip exists only for the grid-rows grow-in, which runs when
                the note is stacked under the calendar. In the side column it is
                always open, and clipping there crops the step cards as they
                scale on hover. */}
            <div className="overflow-hidden lg:overflow-visible">
              <div className="w-full px-1 pt-4 text-center lg:pt-0 lg:text-left">
                <h3
                  className={cn(
                    "text-lg font-semibold tracking-tight text-foreground transition-all duration-[800ms] ease-out sm:text-xl",
                    "lg:translate-y-0 lg:opacity-100",
                    revealed ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
                  )}
                >
                  Book in three steps
                </h3>
                <div
                  className={cn(
                    "mt-2 flex justify-center transition-all duration-[800ms] ease-out lg:hidden",
                    revealed ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
                  )}
                  style={{ transitionDelay: revealed ? "150ms" : "0ms" }}
                >
                  <ChevronDown className="size-5 animate-bounce text-primary" aria-hidden />
                </div>
                <ol className="mx-auto mt-2 flex w-full max-w-lg flex-col gap-2 px-1 text-left lg:mx-0">
                  {STEPS.map(([title, body], i) => {
                    // Lit either because the tour has reached this step, or
                    // because the whole note was revealed at the end / on
                    // take-over. The staggered delay belongs only to the second
                    // case; a step the cursor just demonstrated should answer
                    // immediately.
                    const reached = stage >= i;
                    const lit = revealed || reached;
                    return (
                    <li
                      key={title}
                      className={cn(
                        "transition-all duration-[800ms] ease-out",
                        // In the side column the steps are present from the
                        // first frame: they are what fills the plate, and a
                        // column that stays blank until the tour reaches it
                        // leaves the card looking half-empty on arrival. When
                        // stacked they still ease in as the payoff.
                        "lg:translate-y-0 lg:opacity-100",
                        lit ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
                      )}
                      style={{ transitionDelay: lit && !reached ? `${300 + i * 450}ms` : "0ms" }}
                    >
                      <div
                        className={cn(
                          "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-2 transition-colors duration-500",
                          // The cursor and the note stay in step: whichever the
                          // tour is demonstrating is the one picked out here.
                          reached && !revealed
                            ? "border-primary/50 bg-primary/5"
                            : "border-border/60 bg-background/40",
                          buttonFx.plate,
                        )}
                      >
                        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                          {i + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-foreground">{title}</p>
                          <p className="text-xs leading-relaxed text-foreground/75">{body}</p>
                        </div>
                      </div>
                    </li>
                    );
                  })}
                </ol>
              </div>
            </div>
          </div>
          </div>
        </GlassPanel>
        </div>
      </div>
    </section>
  );
}

/** DayView, but each row carries `data-demo-slot` so the tour cursor can aim at
 *  a specific time. We render the real DayView and tag its rows after mount. */
function DemoDayView({
  availability,
  selectedIds,
  onSelect,
}: {
  availability: DayAvailability | undefined;
  selectedIds: Set<string>;
  onSelect: (s: Slot) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const slots = availability?.slots ?? [];
  useEffect(() => {
    // Tag each selectable row with its slot id (rows render in order).
    const btns = ref.current?.querySelectorAll("button") ?? [];
    const selectable = slots.filter((s) => s.status === "available" || s.status === "partially_booked");
    btns.forEach((b, i) => {
      if (selectable[i]) b.setAttribute("data-demo-slot", selectable[i].id);
    });
  });
  return (
    <div ref={ref}>
      <DayView
        availability={availability}
        tz={TZ}
        service={SERVICE}
        isDaySlot={false}
        nameFor={() => "Resource A"}
        selectedIds={selectedIds}
        onSelect={onSelect}
      />
    </div>
  );
}

function CursorArrow() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="drop-shadow-md">
      <path
        d="M5 3l14 7.5-6.2 1.8 3.3 6.4-2.6 1.3-3.3-6.4L5 20V3z"
        fill="var(--foreground)"
        stroke="var(--background)"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
