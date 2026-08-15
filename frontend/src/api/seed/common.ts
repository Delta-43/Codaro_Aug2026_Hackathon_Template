/**
 * Shared seed machinery. Per-vertical files (fleet.ts / oneToOne.ts /
 * group.ts) supply a VerticalSeedConfig; `assembleStore` turns it into a
 * fully-populated MockStore with realistic, date-relative availability and the
 * mandated edge cases and seed bookings.
 *
 * Determinism: everything derives from the current date and fixed inputs, so a
 * reseed at the same moment yields identical ids, references, and images. Slot
 * ids embed their UTC start ms, so they are stable within a run.
 *
 * Time: slot wall-clock hours are anchored to `baseTz` and converted to true
 * UTC instants (DST-aware). The seeded user's timezone equals `baseTz`, so the
 * demo opens showing local working hours; changing the timezone in Account
 * re-renders the same UTC instants at new local times.
 */
import type {
  Booking,
  BookingModel,
  Provider,
  Resource,
  Service,
  Slot,
  SlotStatus,
  User,
  VerticalId,
} from "@/types/domain";
import type { MockStore } from "@/api/storeTypes";

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------

const MINUTE_MS = 60_000;
const HOUR_MS = 3_600_000;

export const pad = (n: number): string => String(n).padStart(2, "0");

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// ---------------------------------------------------------------------------
// Deterministic, network-free imagery (inline SVG data URIs)
// ---------------------------------------------------------------------------
// The brief asks for deterministic placeholder image URLs; generating them as
// data URIs keeps the app fully offline and renders identically every time.

function svgUri(svg: string): string {
  return "data:image/svg+xml," + encodeURIComponent(svg.replace(/\s+/g, " ").trim());
}

function initials(name: string): string {
  const parts = name.replace(/[^A-Za-z0-9 ]/g, "").trim().split(/\s+/);
  const a = parts[0]?.[0] ?? "?";
  const b = parts.length > 1 ? parts[parts.length - 1][0] : (parts[0]?.[1] ?? "");
  return (a + b).toUpperCase();
}

export function avatarUri(seed: string, label: string): string {
  const hue = hashString(seed) % 360;
  const hue2 = (hue + 40) % 360;
  return svgUri(`
    <svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="hsl(${hue} 60% 55%)"/>
        <stop offset="1" stop-color="hsl(${hue2} 62% 42%)"/>
      </linearGradient></defs>
      <rect width="160" height="160" rx="80" fill="url(#g)"/>
      <text x="80" y="98" font-family="system-ui, sans-serif" font-size="62"
        font-weight="600" fill="white" text-anchor="middle">${initials(label)}</text>
    </svg>`);
}

export function coverUri(seed: string): string {
  const hue = hashString(seed) % 360;
  const hue2 = (hue + 60) % 360;
  return svgUri(`
    <svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="hsl(${hue} 55% 46%)"/>
        <stop offset="1" stop-color="hsl(${hue2} 58% 34%)"/>
      </linearGradient></defs>
      <rect width="960" height="360" fill="url(#g)"/>
      <circle cx="820" cy="70" r="180" fill="white" opacity="0.06"/>
      <circle cx="120" cy="320" r="220" fill="black" opacity="0.08"/>
    </svg>`);
}

export function tileUri(seed: string, label: string): string {
  const hue = hashString(seed) % 360;
  return svgUri(`
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="hsl(${hue} 45% 52%)"/>
        <stop offset="1" stop-color="hsl(${(hue + 30) % 360} 48% 38%)"/>
      </linearGradient></defs>
      <rect width="640" height="420" fill="url(#g)"/>
      <text x="32" y="392" font-family="system-ui, sans-serif" font-size="34"
        font-weight="600" fill="white" opacity="0.9">${label}</text>
    </svg>`);
}

// ---------------------------------------------------------------------------
// Timezone-correct wall-clock ↔ UTC helpers
// ---------------------------------------------------------------------------

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
    weekday: "short",
  });
  const map: Record<string, string> = {};
  for (const p of dtf.formatToParts(instant)) map[p.type] = p.value;
  return {
    year: +map.year,
    month: +map.month,
    day: +map.day,
    hour: +map.hour % 24, // Intl may report midnight as "24"
    minute: +map.minute,
    second: +map.second,
    weekday: WEEKDAY_SHORT.indexOf(map.weekday),
  };
}

/** True UTC instant for a wall-clock time in `timeZone` (DST-aware). */
export function zonedWallTimeToUtc(
  y: number,
  m: number,
  d: number,
  hour: number,
  minute: number,
  timeZone: string,
): Date {
  const guess = Date.UTC(y, m - 1, d, hour, minute, 0);
  const p = zonedParts(new Date(guess), timeZone);
  const asIfUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  const offset = asIfUtc - guess; // ms the zone is ahead of UTC at that instant
  return new Date(guess - offset);
}

export interface LocalDay {
  y: number;
  m: number;
  d: number;
  weekday: number; // 0=Sun … 6=Sat
  dateStr: string; // YYYY-MM-DD
}

/** Enumerate calendar days [today-back, today+forward] in `baseTz`. */
export function enumerateLocalDays(
  baseTz: string,
  back: number,
  forward: number,
): LocalDay[] {
  const today = zonedParts(new Date(), baseTz);
  const days: LocalDay[] = [];
  for (let i = -back; i <= forward; i++) {
    // Treat the local Y/M/D as a plain calendar date; add days via UTC noon so
    // no DST shift ever crosses a day boundary. Read the calendar fields back.
    const anchor = new Date(Date.UTC(today.year, today.month - 1, today.day + i, 12));
    const y = anchor.getUTCFullYear();
    const m = anchor.getUTCMonth() + 1;
    const d = anchor.getUTCDate();
    days.push({ y, m, d, weekday: anchor.getUTCDay(), dateStr: `${y}-${pad(m)}-${pad(d)}` });
  }
  return days;
}

/** The YYYY-MM-DD an instant falls on, in `baseTz`. */
export function localDateStr(iso: string, baseTz: string): string {
  const p = zonedParts(new Date(iso), baseTz);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

// ---------------------------------------------------------------------------
// Slot status derivation — the single place the rule lives (store reuses it).
// ---------------------------------------------------------------------------

export function deriveSlotStatus(
  slot: Pick<Slot, "capacity" | "bookedCount" | "endUtc">,
  nowMs: number,
): SlotStatus {
  if (new Date(slot.endUtc).getTime() <= nowMs) return "past";
  if (slot.capacity <= 0) return "blocked";
  if (slot.bookedCount >= slot.capacity) return "full";
  if (slot.bookedCount > 0) return "partially_booked";
  return "available";
}

// ---------------------------------------------------------------------------
// Config the per-vertical files provide
// ---------------------------------------------------------------------------

export interface SlotGridSpec {
  daysBack: number;
  daysForward: number;
  /** Weekdays (0=Sun…6=Sat) that have slots; omit for every day. */
  weekdays?: number[];
  /** Local wall-clock start times for each slot in a day. */
  startTimes: { hour: number; minute: number }[];
}

export interface ResourceSpec {
  name: string;
  description?: string;
  capacity: number;
  attributes: { label: string; value: string }[];
}

export interface DemoServiceSpec {
  name: string;
  description: string;
  slotDurationMinutes: number;
  minSlotsPerBooking: number;
  maxSlotsPerBooking: number;
  priceMinorUnits: number;
  cancellationCutoffHours: number;
  resources: ResourceSpec[];
  grid: SlotGridSpec;
}

export interface SimpleServiceSpec {
  name: string;
  description: string;
  slotDurationMinutes: number;
  priceMinorUnits: number;
  cancellationCutoffHours: number;
  minSlotsPerBooking: number;
  maxSlotsPerBooking: number;
  resource: ResourceSpec;
  grid: SlotGridSpec;
}

export interface ProviderSpec {
  name: string;
  tagline: string;
  bio: string;
  categoryId: string;
  city: string;
  country: string;
  lat: number;
  lng: number;
  publicCode: string;
  rating: number;
  reviewCount: number;
  links?: { label: string; url: string }[];
}

export interface VerticalSeedConfig {
  verticalId: VerticalId;
  bookingModel: BookingModel;
  currency: string;
  baseTz: string;
  categories: { id: string; label: string }[];
  providers: ProviderSpec[]; // index 0 is the locked-in demo provider
  demoServices: DemoServiceSpec[]; // 2–4, exercise the booking model
  simpleService: SimpleServiceSpec; // one per non-demo provider
}

// ---------------------------------------------------------------------------
// The seeded user
// ---------------------------------------------------------------------------

export function makeSeedUser(baseTz: string, followedProviderIds: string[]): User {
  return {
    id: "user_demo",
    displayName: "Mara Lindqvist",
    email: "mara@example.com",
    avatarUrl: avatarUri("user_demo", "Mara Lindqvist"),
    timezone: baseTz,
    verified: true,
    followedProviderIds,
  };
}

// ---------------------------------------------------------------------------
// The assembler
// ---------------------------------------------------------------------------

export function assembleStore(cfg: VerticalSeedConfig): MockStore {
  const nowMs = Date.now();
  let seq = 0;
  const nid = (prefix: string) => `${prefix}_${cfg.verticalId}_${seq++}`;

  const providers: Provider[] = [];
  const services: Service[] = [];
  const resources: Resource[] = [];
  const slots: Slot[] = [];
  const bookings: Booking[] = [];

  // --- providers ---------------------------------------------------------
  cfg.providers.forEach((p, i) => {
    providers.push({
      id: nid("prov"),
      name: p.name,
      avatarUrl: avatarUri(p.name, p.name),
      coverUrl: coverUri(p.name),
      tagline: p.tagline,
      bio: p.bio,
      categoryId: p.categoryId,
      location: { city: p.city, country: p.country, lat: p.lat, lng: p.lng },
      rating: p.rating,
      reviewCount: p.reviewCount,
      links: p.links ?? [],
      publicCode: p.publicCode,
      serviceIds: [],
    });
    void i;
  });

  const demoProvider = providers[0];

  // --- helper to add a service+resources+slots ---------------------------
  function addService(
    provider: Provider,
    spec: {
      name: string;
      description: string;
      slotDurationMinutes: number;
      minSlotsPerBooking: number;
      maxSlotsPerBooking: number;
      priceMinorUnits: number;
      cancellationCutoffHours: number;
      resources: ResourceSpec[];
      grid: SlotGridSpec;
    },
  ): Service {
    const service: Service = {
      id: nid("svc"),
      providerId: provider.id,
      name: spec.name,
      description: spec.description,
      imageUrl: tileUri(spec.name, spec.name),
      bookingModel: cfg.bookingModel,
      slotDurationMinutes: spec.slotDurationMinutes,
      minSlotsPerBooking: spec.minSlotsPerBooking,
      maxSlotsPerBooking: spec.maxSlotsPerBooking,
      priceMinorUnits: spec.priceMinorUnits,
      currency: cfg.currency,
      cancellationCutoffHours: spec.cancellationCutoffHours,
      resourceIds: [],
    };
    services.push(service);
    provider.serviceIds.push(service.id);

    spec.resources.forEach((r) => {
      const resource: Resource = {
        id: nid("res"),
        serviceId: service.id,
        name: r.name,
        description: r.description,
        imageUrl: tileUri(service.id + r.name, r.name),
        capacity: r.capacity,
        attributes: r.attributes,
        active: true,
      };
      resources.push(resource);
      service.resourceIds.push(resource.id);
      buildSlots(service, resource, spec.grid, cfg.baseTz).forEach((s) => slots.push(s));
    });

    return service;
  }

  // --- demo provider: rich services --------------------------------------
  cfg.demoServices.forEach((s) => addService(demoProvider, s));

  // --- other providers: one simple service each --------------------------
  providers.slice(1).forEach((provider) => {
    const t = cfg.simpleService;
    addService(provider, {
      name: t.name,
      description: t.description,
      slotDurationMinutes: t.slotDurationMinutes,
      minSlotsPerBooking: t.minSlotsPerBooking,
      maxSlotsPerBooking: t.maxSlotsPerBooking,
      priceMinorUnits: t.priceMinorUnits,
      cancellationCutoffHours: t.cancellationCutoffHours,
      resources: [t.resource],
      grid: t.grid,
    });
  });

  // --- edge cases on the primary demo service ----------------------------
  const primaryService = services.find((s) => s.providerId === demoProvider.id)!;
  const primaryResource = resources.find((r) => r.serviceId === primaryService.id)!;

  injectEdgeCases(slots, primaryService, cfg.baseTz, nowMs);

  // --- seeded bookings ---------------------------------------------------
  seedBookings({
    bookings,
    slots,
    service: primaryService,
    resource: primaryResource,
    provider: demoProvider,
    userId: "user_demo",
    cfg,
    nowMs,
    nid,
  });

  const user = makeSeedUser(cfg.baseTz, [providers[1]?.id].filter(Boolean) as string[]);

  return {
    verticalId: cfg.verticalId,
    user,
    providers,
    services,
    resources,
    slots,
    bookings,
  };
}

// ---------------------------------------------------------------------------
// Slot construction
// ---------------------------------------------------------------------------

function buildSlots(
  service: Service,
  resource: Resource,
  grid: SlotGridSpec,
  baseTz: string,
): Slot[] {
  const out: Slot[] = [];
  for (const day of enumerateLocalDays(baseTz, grid.daysBack, grid.daysForward)) {
    if (grid.weekdays && !grid.weekdays.includes(day.weekday)) continue;
    for (const t of grid.startTimes) {
      const start = zonedWallTimeToUtc(day.y, day.m, day.d, t.hour, t.minute, baseTz);
      const end = new Date(start.getTime() + service.slotDurationMinutes * MINUTE_MS);
      out.push({
        id: `slot_${service.id}_${resource.id}_${start.getTime()}`,
        serviceId: service.id,
        resourceId: resource.id,
        startUtc: start.toISOString(),
        endUtc: end.toISOString(),
        capacity: resource.capacity,
        bookedCount: 0,
        status: "available", // derived fresh at read time
      });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Edge cases: one full day, one blocked day, one 1-left slot (if capacity>1)
// ---------------------------------------------------------------------------

function injectEdgeCases(
  slots: Slot[],
  service: Service,
  baseTz: string,
  nowMs: number,
): void {
  const svcSlots = slots.filter((s) => s.serviceId === service.id);
  const futureDates = Array.from(
    new Set(
      svcSlots
        .filter((s) => new Date(s.startUtc).getTime() > nowMs)
        .map((s) => localDateStr(s.startUtc, baseTz)),
    ),
  ).sort();

  const fullDate = futureDates[6] ?? futureDates[1];
  const blockedDate = futureDates[11] ?? futureDates[2];
  const partialDate = futureDates[3] ?? futureDates[0];

  for (const s of svcSlots) {
    const date = localDateStr(s.startUtc, baseTz);
    if (date === fullDate) {
      s.bookedCount = s.capacity; // every slot full
    } else if (date === blockedDate) {
      s.capacity = 0; // closure / holiday
      s.bookedCount = 0;
    }
  }

  // "Exactly one left" only means something when capacity > 1 (shared_capacity).
  if (blockedDate !== partialDate && fullDate !== partialDate) {
    const partial = svcSlots.find(
      (s) => localDateStr(s.startUtc, baseTz) === partialDate && s.capacity > 1,
    );
    if (partial) partial.bookedCount = partial.capacity - 1;
  }
}

// ---------------------------------------------------------------------------
// Seeded bookings — covers every lifecycle state the brief mandates
// ---------------------------------------------------------------------------

function makeReference(seed: number): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no ambiguous chars
  let n = (seed * 2654435761) >>> 0;
  let out = "";
  for (let i = 0; i < 6; i++) {
    out += alphabet[n % alphabet.length];
    n = Math.floor(n / alphabet.length) + 7;
  }
  return `BK-${out}`;
}

function insertDedicatedSlot(
  slots: Slot[],
  service: Service,
  resource: Resource,
  startMs: number,
  bookedCount: number,
): Slot {
  const start = new Date(startMs);
  const end = new Date(startMs + service.slotDurationMinutes * MINUTE_MS);
  const slot: Slot = {
    id: `slot_${service.id}_${resource.id}_${startMs}`,
    serviceId: service.id,
    resourceId: resource.id,
    startUtc: start.toISOString(),
    endUtc: end.toISOString(),
    capacity: resource.capacity,
    bookedCount,
    status: "available",
  };
  slots.push(slot);
  return slot;
}

function seedBookings(args: {
  bookings: Booking[];
  slots: Slot[];
  service: Service;
  resource: Resource;
  provider: Provider;
  userId: string;
  cfg: VerticalSeedConfig;
  nowMs: number;
  nid: (p: string) => string;
}): void {
  const { bookings, slots, service, resource, provider, userId, cfg, nowMs, nid } = args;
  const dur = service.slotDurationMinutes;
  const cutoffMs = service.cancellationCutoffHours * HOUR_MS;
  const isShared = cfg.bookingModel === "shared_capacity";
  let refSeed = 1;

  const push = (b: Omit<Booking, "id" | "reference">, slotList: Slot[], consume: boolean) => {
    if (consume) for (const s of slotList) s.bookedCount = Math.min(s.capacity, s.bookedCount + b.partySize);
    bookings.push({ ...b, id: nid("bk"), reference: makeReference(refSeed++) });
  };

  const total = (slotCount: number, party: number) =>
    service.priceMinorUnits * slotCount * party;

  // 1) Upcoming, OUTSIDE cutoff → changeable.
  {
    const startMs = nowMs + cutoffMs + 5 * 24 * HOUR_MS;
    const party = isShared ? 2 : 1;
    const slot = insertDedicatedSlot(slots, service, resource, startMs, 0);
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: [slot.id],
        startUtc: slot.startUtc,
        endUtc: slot.endUtc,
        status: "confirmed",
        partySize: party,
        priceMinorUnits: total(1, party),
        currency: service.currency,
        createdAtUtc: new Date(nowMs - 3 * 24 * HOUR_MS).toISOString(),
        changeHistory: [],
      },
      [slot],
      true,
    );
  }

  // 2) Upcoming, INSIDE cutoff → locked (change/cancel disabled with reason).
  {
    const startMs = nowMs + Math.min(cutoffMs * 0.4, cutoffMs - HOUR_MS) + 30 * MINUTE_MS;
    const party = isShared ? 3 : 1;
    const slot = insertDedicatedSlot(slots, service, resource, Math.round(startMs), 0);
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: [slot.id],
        startUtc: slot.startUtc,
        endUtc: slot.endUtc,
        status: "confirmed",
        partySize: party,
        priceMinorUnits: total(1, party),
        currency: service.currency,
        createdAtUtc: new Date(nowMs - 24 * HOUR_MS).toISOString(),
        changeHistory: [],
      },
      [slot],
      true,
    );
  }

  // 3) Completed in the past, NO review.
  {
    const startMs = nowMs - 7 * 24 * HOUR_MS;
    const party = isShared ? 1 : 1;
    const slot = insertDedicatedSlot(slots, service, resource, startMs, 0);
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: [slot.id],
        startUtc: slot.startUtc,
        endUtc: slot.endUtc,
        status: "completed",
        partySize: party,
        priceMinorUnits: total(1, party),
        currency: service.currency,
        createdAtUtc: new Date(startMs - 6 * 24 * HOUR_MS).toISOString(),
        changeHistory: [],
      },
      [slot],
      true,
    );
  }

  // 4) Completed in the past, WITH review.
  {
    const startMs = nowMs - 16 * 24 * HOUR_MS;
    const slot = insertDedicatedSlot(slots, service, resource, startMs, 0);
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: [slot.id],
        startUtc: slot.startUtc,
        endUtc: slot.endUtc,
        status: "completed",
        partySize: 1,
        priceMinorUnits: total(1, 1),
        currency: service.currency,
        createdAtUtc: new Date(startMs - 5 * 24 * HOUR_MS).toISOString(),
        changeHistory: [],
        review: {
          rating: 5,
          text: "Exactly as described. Smooth from start to finish — would book again.",
          createdAtUtc: new Date(startMs + dur * MINUTE_MS + 2 * HOUR_MS).toISOString(),
        },
      },
      [slot],
      true,
    );
  }

  // 5) Cancelled (capacity released → not consumed).
  {
    const startMs = nowMs + cutoffMs + 12 * 24 * HOUR_MS;
    const slot = insertDedicatedSlot(slots, service, resource, startMs, 0);
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: [slot.id],
        startUtc: slot.startUtc,
        endUtc: slot.endUtc,
        status: "cancelled",
        partySize: 1,
        priceMinorUnits: total(1, 1),
        currency: service.currency,
        createdAtUtc: new Date(nowMs - 10 * 24 * HOUR_MS).toISOString(),
        cancelledAtUtc: new Date(nowMs - 9 * 24 * HOUR_MS).toISOString(),
        changeHistory: [],
      },
      [slot],
      false,
    );
  }

  // 6) Multi-slot booking (only where the model allows > 1 slot).
  if (service.maxSlotsPerBooking > 1) {
    const count = Math.min(3, service.maxSlotsPerBooking);
    const dayMs = dur * MINUTE_MS;
    const firstStart = nowMs - 12 * 24 * HOUR_MS;
    const multiSlots: Slot[] = [];
    for (let i = 0; i < count; i++) {
      multiSlots.push(
        insertDedicatedSlot(slots, service, resource, firstStart + i * dayMs, 0),
      );
    }
    push(
      {
        userId,
        providerId: provider.id,
        serviceId: service.id,
        resourceId: resource.id,
        slotIds: multiSlots.map((s) => s.id),
        startUtc: multiSlots[0].startUtc,
        endUtc: multiSlots[multiSlots.length - 1].endUtc,
        status: "completed",
        partySize: 1,
        priceMinorUnits: total(count, 1),
        currency: service.currency,
        createdAtUtc: new Date(firstStart - 4 * 24 * HOUR_MS).toISOString(),
        changeHistory: [],
      },
      multiSlots,
      true,
    );
  }
}
