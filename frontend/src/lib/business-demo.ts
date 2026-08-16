/**
 * Demo content generators for business mode + user profiles.
 *
 * Everything is DETERMINISTIC — seeded off a stable key (the use case + entity
 * id) — so a given business/user always renders the same numbers, requests and
 * reviews across tabs and refreshes. The *what* (vocabulary, business identity,
 * service names, review copy) comes from the active `UseCase`
 * (`config/useCases.ts`); this file only turns that into shaped, seeded demo
 * data. Swap these for real API calls as the backend grows the endpoints.
 */
import type { UseCase } from "@/config/useCases";

// --- deterministic RNG ------------------------------------------------------

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(a: number): () => number {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function rng(seed: string): () => number {
  return mulberry32(hashStr(seed));
}

function pick<T>(r: () => number, arr: readonly T[]): T {
  return arr[Math.floor(r() * arr.length)];
}

function int(r: () => number, min: number, max: number): number {
  return Math.floor(r() * (max - min + 1)) + min;
}

// --- deterministic initials avatar (data URI) -------------------------------

const AVATAR_HUES = [3, 28, 46, 152, 190, 220, 260, 320];

/** A small initials avatar as an inline SVG data URI (no network, theme-safe). */
export function avatarDataUri(name: string): string {
  const r = rng(name);
  const hue = pick(r, AVATAR_HUES);
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="hsl(${hue} 70% 62%)"/>
<stop offset="1" stop-color="hsl(${(hue + 40) % 360} 68% 48%)"/></linearGradient></defs>
<rect width="96" height="96" rx="48" fill="url(#g)"/>
<text x="48" y="49" dominant-baseline="central" text-anchor="middle" font-family="Outfit, ui-sans-serif, system-ui, sans-serif" font-size="38" font-weight="600" fill="#fff">${initials}</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// --- shapes -----------------------------------------------------------------

export interface Metric {
  key: string;
  label: string;
  value: string;
  sub?: string;
  tone: "up" | "down" | "neutral";
  help: string;
}

export interface DemoRequest {
  id: string;
  clientName: string;
  avatarUrl: string;
  rating: number;
  memberMonths: number;
  bookingsWithYou: number;
  serviceLabel: string;
  whenLabel: string;
  partySize: number;
  note: string;
  flagged: boolean;
}

export type DemoBookingStatus = "confirmed" | "completed" | "pending";

export interface DemoBooking {
  id: string;
  title: string;
  client: string;
  serviceLabel: string;
  startUtc: string;
  endUtc: string;
  status: DemoBookingStatus;
  partySize: number;
  priceMinorUnits: number;
  currency: string;
}

export interface DemoReview {
  id: string;
  author: string;
  avatarUrl: string;
  rating: number;
  text: string;
  whenLabel: string;
}

export interface DemoMedia {
  id: string;
  title: string;
  scene: string;
  kind: "photo" | "video";
}

// --- local wall-clock → UTC (DST-aware), so demo times land on nice hours ---

function wallToUtcIso(dateStr: string, hour: number, minute: number, tz: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const guess = Date.UTC(y, m - 1, d, hour, minute, 0);
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const map: Record<string, string> = {};
  for (const p of dtf.formatToParts(new Date(guess))) map[p.type] = p.value;
  const asIfUtc = Date.UTC(+map.year, +map.month - 1, +map.day, +map.hour % 24, +map.minute, +map.second);
  return new Date(guess - (asIfUtc - guess)).toISOString();
}

function todayStr(tz: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function shiftDay(dateStr: string, n: number): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + n, 12));
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}-${String(
    dt.getUTCDate(),
  ).padStart(2, "0")}`;
}

// --- generators -------------------------------------------------------------

const serviceNames = (uc: UseCase) => uc.services.map((s) => s.name);
const currencyOf = (uc: UseCase) => uc.services[0]?.currency ?? "EUR";

/** The three glanceable dashboard numbers. */
export function businessMetrics(uc: UseCase, seed: string): Metric[] {
  const r = rng(`${seed}:metrics`);
  const a = int(r, 3, 11);
  const b = int(r, 2, 9);
  const c = int(r, 1, 6);
  const total = a + b + c;
  const satisfaction = int(r, -9, 12);
  const revenue = int(r, 22, 96) * 100 + int(r, 0, 99);
  const currency = currencyOf(uc);
  const money = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(revenue);

  return [
    {
      key: "upcoming",
      label: "Upcoming bookings",
      value: String(total),
      sub: `${a} · ${b} · ${c} across ${uc.services.length} offers`,
      tone: "neutral",
      help: `Confirmed ${uc.bookingUnit} in the next 30 days, broken down by offer. Tap a booking in the calendar to manage it.`,
    },
    {
      key: "satisfaction",
      label: "Client satisfaction",
      value: `${satisfaction >= 0 ? "+" : ""}${satisfaction}%`,
      sub: "vs last month",
      tone: satisfaction >= 0 ? "up" : "down",
      help: "Month-over-month change blended from new review scores and how often your offers get booked after being viewed. Above zero means clients are happier and booking more.",
    },
    {
      key: "revenue",
      label: "Revenue this month",
      value: money,
      sub: "confirmed this cycle",
      tone: "up",
      help: `Total value of confirmed bookings for the current calendar month, before fees. Currency follows the offer (${currency}).`,
    },
  ];
}

export function demoRequests(uc: UseCase, seed: string): DemoRequest[] {
  const r = rng(`${seed}:requests`);
  const names = uc.clientNames;
  const labels = serviceNames(uc);
  const n = int(r, 3, 5);
  const whenOpts = ["Today", "Tomorrow", "This Thu", "This weekend", "Next Mon"];
  const out: DemoRequest[] = [];
  const used = new Set<string>();
  for (let i = 0; i < n; i++) {
    let name = pick(r, names);
    let guard = 0;
    while (used.has(name) && guard++ < 8) name = pick(r, names);
    used.add(name);
    const rating = Math.round((3.4 + r() * 1.6) * 10) / 10;
    out.push({
      id: `req-${i}`,
      clientName: name,
      avatarUrl: avatarDataUri(name),
      rating,
      memberMonths: int(r, 1, 46),
      bookingsWithYou: int(r, 0, 9),
      serviceLabel: pick(r, labels),
      whenLabel: pick(r, whenOpts),
      partySize: uc.partyNoun ? int(r, 1, 8) : 1,
      note: pick(r, uc.requestNotes),
      flagged: rating < 3.8 && r() > 0.55,
    });
  }
  return out;
}

/** Bookings spread across a ~3 week window around today (for month/week/day). */
export function demoBookings(uc: UseCase, seed: string, tz: string): DemoBooking[] {
  const r = rng(`${seed}:bookings`);
  const labels = serviceNames(uc);
  const today = todayStr(tz);
  const currency = currencyOf(uc);
  const multiDay = uc.bookingUnit === "stays" || uc.bookingUnit === "rentals" || uc.bookingUnit === "hires";
  const out: DemoBooking[] = [];
  for (let offset = -6; offset <= 13; offset++) {
    const perDay = offset < 0 ? int(r, 0, 1) : int(r, 0, 3);
    for (let k = 0; k < perDay; k++) {
      const hour = int(r, 8, 19);
      const spanDays = multiDay ? pick(r, [0, 0, 1, 2]) : 0;
      const dateStr = shiftDay(today, offset);
      const startUtc = wallToUtcIso(dateStr, hour, 0, tz);
      const endUtc = wallToUtcIso(shiftDay(dateStr, spanDays), (hour + (spanDays ? 0 : 1)) % 24, 0, tz);
      const party = uc.partyNoun ? int(r, 1, 12) : 1;
      const price = int(r, 25, 180) * 100;
      out.push({
        id: `bk-${offset}-${k}`,
        title: pick(r, labels),
        client: pick(r, uc.clientNames),
        serviceLabel: pick(r, labels),
        startUtc,
        endUtc,
        status: offset < 0 ? "completed" : "confirmed",
        partySize: party,
        priceMinorUnits: price * (uc.partyNoun ? party : 1),
        currency,
      });
    }
  }
  return out;
}

export function demoReviews(uc: UseCase, seed: string): DemoReview[] {
  const r = rng(`${seed}:reviews`);
  const whenOpts = ["2 days ago", "last week", "3 weeks ago", "last month", "2 months ago"];
  return uc.reviewLines.map((text, i) => {
    const author = uc.clientNames[(i + 2) % uc.clientNames.length];
    return {
      id: `rev-${i}`,
      author,
      avatarUrl: avatarDataUri(author),
      rating: Math.round((4.2 + r() * 0.8) * 10) / 10,
      text,
      whenLabel: pick(r, whenOpts),
    };
  });
}

export function demoGallery(uc: UseCase): DemoMedia[] {
  return uc.galleryTitles.map((title, i) => ({
    id: `ph-${i}`,
    title,
    scene: uc.scenes[i % uc.scenes.length],
    kind: "photo" as const,
  }));
}

export function demoVideos(uc: UseCase): DemoMedia[] {
  return uc.videoTitles.map((title, i) => ({
    id: `vid-${i}`,
    title,
    scene: uc.scenes[(i + 1) % uc.scenes.length],
    kind: "video" as const,
  }));
}

export function demoSocial(uc: UseCase) {
  return uc.social;
}

export function demoBio(uc: UseCase): string {
  return uc.business.bio;
}

/** Per-service glanceable stats for the Services overview (mock until wired). */
export interface ServiceStats {
  upcoming: number;
  pastTotal: number;
  rating: number;
  marginPct: number;
}

export function serviceStats(seed: string): ServiceStats {
  const r = rng(`${seed}:svc`);
  return {
    upcoming: int(r, 0, 14),
    pastTotal: int(r, 12, 420),
    rating: Math.round((4.1 + r() * 0.9) * 10) / 10,
    marginPct: int(r, 28, 68),
  };
}

// --- customer side: the user's own rating + reviews left by businesses -------

const REVIEWER_BUSINESSES = [
  "Ibiza Car Rentals",
  "Azure Bay Hotel",
  "The Glasshouse",
  "Lumen Studio",
  "Bright Minds Tutoring",
  "FreshNest Cleaning",
];

const USER_REVIEW_LINES = [
  "Punctual, friendly and left everything spotless. A pleasure to host.",
  "Clear communicator and easy to work with — welcome back any time.",
  "Respectful of our space and prompt with everything. Highly rated.",
  "Great guest — no issues at all, would happily book again.",
  "Reliable and considerate. Exactly the kind of customer we love.",
];

export interface UserRating {
  score: number;
  count: number;
  reviews: DemoReview[];
}

/** A customer's reputation as seen by businesses (deterministic per user). */
export function userRating(seed: string): UserRating {
  const r = rng(`${seed}:userrep`);
  const count = int(r, 3, 40);
  const reviews = USER_REVIEW_LINES.slice(0, int(r, 3, USER_REVIEW_LINES.length)).map((text, i) => {
    const author = REVIEWER_BUSINESSES[(i + int(r, 0, 3)) % REVIEWER_BUSINESSES.length];
    return {
      id: `urev-${i}`,
      author,
      avatarUrl: avatarDataUri(author),
      rating: Math.round((4.3 + r() * 0.7) * 10) / 10,
      text,
      whenLabel: pick(r, ["last week", "2 weeks ago", "last month", "2 months ago"]),
    };
  });
  const score = Math.round((4.4 + r() * 0.6) * 10) / 10;
  return { score, count, reviews };
}
