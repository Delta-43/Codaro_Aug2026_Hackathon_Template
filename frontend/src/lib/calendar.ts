// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Calendar date math, all anchored to the user's timezone. Day boundaries,
 * week ranges, and month grids are computed as wall-clock local dates and
 * converted to true UTC instants (DST-aware) for the availability API. Never
 * do `+ 86400000` arithmetic, day length varies at DST.
 */

const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAY_NARROW = ["S", "M", "T", "W", "T", "F", "S"];
const pad = (n: number) => String(n).padStart(2, "0");

function zonedParts(instant: Date, timeZone: string) {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const map: Record<string, string> = {};
  for (const p of dtf.formatToParts(instant)) map[p.type] = p.value;
  return {
    year: +map.year,
    month: +map.month,
    day: +map.day,
    hour: +map.hour % 24,
    minute: +map.minute,
    second: +map.second,
  };
}

/** True UTC instant for a wall-clock time in `timeZone` (DST-aware). */
function wallToUtc(y: number, m: number, d: number, hh: number, mm: number, tz: string): Date {
  const guess = Date.UTC(y, m - 1, d, hh, mm, 0);
  const p = zonedParts(new Date(guess), tz);
  const asIfUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return new Date(guess - (asIfUtc - guess));
}

export interface CalDay {
  y: number;
  m: number; // 1-based
  d: number;
  dateStr: string; // YYYY-MM-DD
  weekday: number; // 0=Sun … 6=Sat
  weekdayShort: string; // "Mon"
  weekdayNarrow: string; // "M"
}

/** Build a CalDay from a plain calendar date, normalizing overflow. */
function makeDay(y: number, m: number, d: number): CalDay {
  const anchor = new Date(Date.UTC(y, m - 1, d, 12)); // noon avoids DST edge
  const yy = anchor.getUTCFullYear();
  const mm = anchor.getUTCMonth() + 1;
  const dd = anchor.getUTCDate();
  const wd = anchor.getUTCDay();
  return {
    y: yy,
    m: mm,
    d: dd,
    dateStr: `${yy}-${pad(mm)}-${pad(dd)}`,
    weekday: wd,
    weekdayShort: WEEKDAY_SHORT[wd],
    weekdayNarrow: WEEKDAY_NARROW[wd],
  };
}

function parse(dateStr: string): CalDay {
  const [y, m, d] = dateStr.split("-").map(Number);
  return makeDay(y, m, d);
}

export function addDays(dateStr: string, n: number): CalDay {
  const c = parse(dateStr);
  return makeDay(c.y, c.m, c.d + n);
}

export function todayStr(tz: string): string {
  const p = zonedParts(new Date(), tz);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

function startOfDayUtcIso(dateStr: string, tz: string): string {
  const c = parse(dateStr);
  return wallToUtc(c.y, c.m, c.d, 0, 0, tz).toISOString();
}

/** UTC [from, to) covering a single local day. */
export function dayRange(dateStr: string, tz: string): { fromUtc: string; toUtc: string } {
  return {
    fromUtc: startOfDayUtcIso(dateStr, tz),
    toUtc: startOfDayUtcIso(addDays(dateStr, 1).dateStr, tz),
  };
}

/** The Mon–Sun week (as CalDays) containing `dateStr`. */
export function weekOf(dateStr: string): CalDay[] {
  const c = parse(dateStr);
  const offsetToMonday = c.weekday === 0 ? 6 : c.weekday - 1;
  const monday = addDays(dateStr, -offsetToMonday);
  return Array.from({ length: 7 }, (_, i) => addDays(monday.dateStr, i));
}

export function weekRange(days: CalDay[], tz: string): { fromUtc: string; toUtc: string } {
  return {
    fromUtc: startOfDayUtcIso(days[0].dateStr, tz),
    toUtc: startOfDayUtcIso(addDays(days[days.length - 1].dateStr, 1).dateStr, tz),
  };
}

/** 6×7 month grid (leading/trailing days from adjacent months included). */
export function monthMatrix(year: number, month: number): CalDay[][] {
  const first = makeDay(year, month, 1);
  const offsetToMonday = first.weekday === 0 ? 6 : first.weekday - 1;
  const gridStart = addDays(first.dateStr, -offsetToMonday);
  const cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart.dateStr, i));
  const weeks: CalDay[][] = [];
  for (let i = 0; i < 6; i++) weeks.push(cells.slice(i * 7, i * 7 + 7));
  return weeks;
}

export function monthKey(year: number, month: number): string {
  return `${year}-${pad(month)}`;
}

export function isPastDay(dateStr: string, tz: string): boolean {
  return dateStr < todayStr(tz);
}

export function isToday(dateStr: string, tz: string): boolean {
  return dateStr === todayStr(tz);
}

// --- header labels ---------------------------------------------------------

export function monthLabel(year: number, month: number): string {
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(
    new Date(Date.UTC(year, month - 1, 1, 12)),
  );
}

export function weekLabel(days: CalDay[]): string {
  const a = new Date(Date.UTC(days[0].y, days[0].m - 1, days[0].d, 12));
  const b = new Date(Date.UTC(days[6].y, days[6].m - 1, days[6].d, 12));
  const fmt = (dt: Date, withMonth: boolean) =>
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: withMonth ? "short" : undefined,
    }).format(dt);
  const sameMonth = days[0].m === days[6].m;
  return `${fmt(a, !sameMonth)} – ${fmt(b, true)}`;
}

export function dayLabel(dateStr: string): string {
  const c = parse(dateStr);
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(Date.UTC(c.y, c.m - 1, c.d, 12)));
}
