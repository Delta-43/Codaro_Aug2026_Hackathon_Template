/**
 * Render-time formatting. Every timestamp in state is UTC; these helpers are
 * the ONLY place it becomes a local string, always via `Intl` with an explicit
 * `timeZone` (the user's). No naive `new Date(string)` wall-clock maths, ever.
 * Times carry a timezone indicator so the viewer always knows the zone (§4).
 */

/** Epoch millis for a UTC ISO instant. */
export const ms = (iso: string) => new Date(iso).getTime();

/** e.g. "09:00" in the given zone (24h). */
export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** e.g. "09:00–10:00". */
export function formatTimeRange(startUtc: string, endUtc: string, timeZone: string): string {
  return `${formatTime(startUtc, timeZone)}–${formatTime(endUtc, timeZone)}`;
}

/** Short timezone indicator for `iso` in `timeZone`, e.g. "GMT+2" / "CEST". */
export function zoneAbbrev(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "short",
  }).formatToParts(new Date(iso));
  return parts.find((p) => p.type === "timeZoneName")?.value ?? "";
}

/** e.g. "Fri 14 Mar" (or with year when `withYear`). */
export function formatDate(
  iso: string,
  timeZone: string,
  opts: { weekday?: boolean; withYear?: boolean } = {},
): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: opts.weekday ? "short" : undefined,
    day: "numeric",
    month: "short",
    year: opts.withYear ? "numeric" : undefined,
  }).format(new Date(iso));
}

/** Currency from minor units, e.g. 4200 EUR → "€42.00".
 *
 *  The divisor is the CURRENCY's own exponent, not a hardcoded 100. Minor units
 *  are only hundredths in currencies that have two decimal places: JPY has none
 *  (¥4200 is 4200 minor units, not ¥42) and KWD has three, so every price on a
 *  pivot outside the two-decimal world rendered wrong by two orders of
 *  magnitude. `Intl` already knows each currency's exponent — which is also why
 *  `pricing.currencyExponent` stays a config-side declaration and is not plumbed
 *  through every call site to get this right. */
const exponentOf = (currency: string): number => {
  try {
    return (
      new Intl.NumberFormat("en-GB", { style: "currency", currency }).resolvedOptions()
        .maximumFractionDigits ?? 2
    );
  } catch {
    return 2; // an unknown/invalid code — assume the common case
  }
};

/** Minor units → the major amount a person types into a price field, and back.
 *  Same exponent rule as `formatMoney` — the owner's price editor did its own
 *  `/100` and `Math.round(x * 100)`, so on a zero-decimal currency it displayed
 *  a hundredth of the price and then SAVED a hundred times what was typed. */
export function toMajorUnits(minorUnits: number, currency: string): number {
  return minorUnits / 10 ** exponentOf(currency);
}

export function toMinorUnits(major: number, currency: string): number {
  return Math.round(major * 10 ** exponentOf(currency));
}

export function formatMoney(minorUnits: number, currency: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
  }).format(minorUnits / 10 ** exponentOf(currency));
}

/** Human duration from minutes: 60→"1h", 90→"1h 30m", 1440→"1 day", 4320→"3 days". */
export function formatDuration(minutes: number): string {
  if (minutes % 1440 === 0) {
    const days = minutes / 1440;
    return `${days} day${days === 1 ? "" : "s"}`;
  }
  if (minutes >= 60) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  return `${minutes} min`;
}

/** Total span of a multi-slot booking, in slot-count × per-slot minutes. */
export function formatSpan(slotCount: number, slotDurationMinutes: number): string {
  return formatDuration(slotCount * slotDurationMinutes);
}

/**
 * One-line "when" summary for a booking span. Same local day → date + time
 * range with zone; multi-day → date range. `endUtc` is exclusive (the instant
 * the last slot ends), so the last calendar day is `endUtc − 1ms` — this keeps
 * full-day slots from reading one day long.
 */
export function formatBookingWhen(startUtc: string, endUtc: string, timeZone: string): string {
  const lastInstant = new Date(ms(endUtc) - 1).toISOString();
  const sameDay = formatDate(startUtc, timeZone) === formatDate(lastInstant, timeZone);
  if (sameDay) {
    return `${formatDate(startUtc, timeZone, { weekday: true })} · ${formatTimeRange(
      startUtc,
      endUtc,
      timeZone,
    )} ${zoneAbbrev(startUtc, timeZone)}`;
  }
  return `${formatDate(startUtc, timeZone, { weekday: true })} – ${formatDate(lastInstant, timeZone, {
    weekday: true,
  })}`;
}

/** Hours from now until `iso` (negative if past). */
function hoursUntil(iso: string): number {
  return (ms(iso) - Date.now()) / 3_600_000;
}

/** The moment change/cancel closes: `start - cutoffHours`. */
function cutoffInstant(startUtc: string, cutoffHours: number): string {
  return new Date(ms(startUtc) - cutoffHours * 3_600_000).toISOString();
}

/** Policy sentence, e.g. "Free changes until Fri 14 Mar, 09:00 CEST". */
export function formatCutoffPolicy(
  startUtc: string,
  cutoffHours: number,
  timeZone: string,
): string {
  const at = cutoffInstant(startUtc, cutoffHours);
  return `Free changes until ${formatDate(at, timeZone, { weekday: true })}, ${formatTime(
    at,
    timeZone,
  )} ${zoneAbbrev(at, timeZone)}`;
}

/** True when now is inside the change/cancel cutoff window. */
export function isWithinCutoff(startUtc: string, cutoffHours: number): boolean {
  return hoursUntil(startUtc) <= cutoffHours;
}

/**
 * Compact relative label for an inbox timestamp, e.g. "now", "5m", "3h", "2d",
 * then an absolute date for anything older than a week. Zone-agnostic (it's an
 * elapsed span, not a wall-clock time), so no timezone is needed.
 */
export function timeAgo(iso: string, timeZone = "UTC"): string {
  const diffMs = Date.now() - ms(iso);
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d`;
  return formatDate(iso, timeZone);
}

/** A short calendar date in the VIEWER's own locale and zone — deliberately
 *  unlike `formatDate`, which pins en-GB and takes an explicit `timeZone`.
 *  Used for profile/member-since style dates where the exact zone is noise.
 *  Empty string for null or unparseable input, so callers can render it raw.
 *  Was duplicated byte-for-byte in owner/profile and the account page. */
export function whenLabel(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
  } catch {
    return "";
  }
}

/** The viewer's IANA zone, falling back to UTC where Intl is unavailable (SSR).
 *  Was defined three times across the owner pages. */
export function browserTz(): string {
  return typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
}
