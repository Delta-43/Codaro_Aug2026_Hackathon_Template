/**
 * The in-memory store and all mutation logic. These functions are synchronous
 * and operate on live references; the async seam in src/api/index.ts wraps them
 * with simulated latency and clones results so callers cannot mutate the store.
 *
 * The booking-mutation semantics enforced here are the contract the backend
 * must mirror exactly (see NOTEBOOK.md §3):
 *  - createBooking re-checks capacity at commit time (never trusts the UI).
 *  - Multi-slot bookings must be contiguous, same-resource, within min/max.
 *  - cancelBooking releases capacity on every slot.
 *  - rescheduleBooking is atomic: acquire new, only then release old.
 *  - Cutoff: no change/cancel inside cancellationCutoffHours of start.
 *  - A booking whose endUtc is in the past reads as completed, never confirmed.
 */
import type {
  Booking,
  BookingStatus,
  DayAvailability,
  ID,
  IsoUtc,
  MonthDensityCell,
  MonthDensityLevel,
  Provider,
  Resource,
  Service,
  Slot,
  User,
  VerticalId,
} from "@/types/domain";
import type { MockStore } from "@/api/storeTypes";
import { ApiError } from "@/api/errors";
import { deriveSlotStatus, localDateStr } from "@/api/seed/common";
import { DEFAULT_VERTICAL, getVertical } from "@/config/verticals";

// ---------------------------------------------------------------------------
// Store lifecycle
// ---------------------------------------------------------------------------

let store: MockStore = getVertical(DEFAULT_VERTICAL).seed();
let bookingSeq = 0;

export function getStore(): MockStore {
  return store;
}

export function resetDemoData(): void {
  store = getVertical(store.verticalId).seed();
}

export function setVertical(id: VerticalId): void {
  store = getVertical(id).seed();
}

export function getVerticalId(): VerticalId {
  return store.verticalId;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const HOUR_MS = 3_600_000;
const ms = (iso: IsoUtc) => new Date(iso).getTime();

/** Update a slot's derived status against the current moment, in place. */
function refreshStatus(slot: Slot): Slot {
  slot.status = deriveSlotStatus(slot, Date.now());
  return slot;
}

function serviceById(id: ID): Service {
  const s = store.services.find((x) => x.id === id);
  if (!s) throw new ApiError("NOT_FOUND", "That service no longer exists.");
  return s;
}

function slotById(id: ID): Slot | undefined {
  return store.slots.find((x) => x.id === id);
}

/** A booking that has finished reads as completed, never confirmed. */
function normalizeBooking(b: Booking): Booking {
  if (b.status === "confirmed" && ms(b.endUtc) <= Date.now()) {
    b.status = "completed";
  }
  return b;
}

function effectiveStatus(b: Booking): BookingStatus {
  if (b.status === "confirmed" && ms(b.endUtc) <= Date.now()) return "completed";
  return b.status;
}

function cutoffPassed(startUtc: IsoUtc, cutoffHours: number): boolean {
  return Date.now() >= ms(startUtc) - cutoffHours * HOUR_MS;
}

function newReference(): string {
  const a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let out = "";
  for (let i = 0; i < 6; i++) out += a[Math.floor(Math.random() * a.length)];
  return `BK-${out}`;
}

/**
 * Validate a set of slot ids as a bookable selection for a service/resource:
 * they exist, all belong to the service & resource, are neither past nor
 * blocked, are contiguous, and their count is within min/max. Returns the
 * slots in chronological order. `excludeBooking` lets a reschedule ignore the
 * capacity it currently holds so it can re-select an overlapping slot.
 */
function resolveSelection(
  service: Service,
  resourceId: ID,
  slotIds: ID[],
  partySize: number,
  excludeBooking?: Booking,
): Slot[] {
  if (slotIds.length === 0) {
    throw new ApiError("INVALID_RANGE", "Choose at least one time to continue.");
  }
  if (
    slotIds.length < service.minSlotsPerBooking ||
    slotIds.length > service.maxSlotsPerBooking
  ) {
    throw new ApiError(
      "INVALID_RANGE",
      service.maxSlotsPerBooking === 1
        ? "Only one slot can be booked at a time."
        : `Choose between ${service.minSlotsPerBooking} and ${service.maxSlotsPerBooking} consecutive slots.`,
    );
  }

  const slots = slotIds.map((id) => {
    const s = slotById(id);
    if (!s) throw new ApiError("NOT_FOUND", "One of those times is no longer available.");
    return s;
  });

  for (const s of slots) {
    if (s.serviceId !== service.id || s.resourceId !== resourceId) {
      throw new ApiError("INVALID_RANGE", "All times must be for the same option.");
    }
  }

  const ordered = [...slots].sort((a, b) => ms(a.startUtc) - ms(b.startUtc));

  // Contiguity: each slot starts exactly when the previous one ends.
  for (let i = 1; i < ordered.length; i++) {
    if (ms(ordered[i].startUtc) !== ms(ordered[i - 1].endUtc)) {
      throw new ApiError("INVALID_RANGE", "Selected times must be back-to-back with no gaps.");
    }
  }

  const now = Date.now();
  for (const s of ordered) {
    if (ms(s.endUtc) <= now) {
      throw new ApiError("SLOT_UNAVAILABLE", "That time has already passed.");
    }
    if (s.capacity <= 0) {
      throw new ApiError("SLOT_UNAVAILABLE", "That time is blocked and can't be booked.");
    }
    if (partySize > s.capacity) {
      throw new ApiError(
        "CAPACITY_EXCEEDED",
        `Only ${s.capacity} place${s.capacity === 1 ? "" : "s"} exist for that time.`,
      );
    }
    // Re-check remaining capacity at commit time. A reschedule may re-select a
    // slot it already holds, so credit back its own current hold.
    const heldBack =
      excludeBooking && excludeBooking.slotIds.includes(s.id) ? excludeBooking.partySize : 0;
    const remaining = s.capacity - s.bookedCount + heldBack;
    if (remaining < partySize) {
      throw new ApiError(
        "SLOT_UNAVAILABLE",
        "That time was just taken. We've refreshed availability.",
        { slotId: s.id },
      );
    }
  }

  return ordered;
}

function totalPrice(service: Service, slotCount: number, partySize: number): number {
  return service.priceMinorUnits * slotCount * partySize;
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export function searchProviders(q: {
  text?: string;
  categoryId?: string;
  near?: string;
}): Provider[] {
  const text = q.text?.trim().toLowerCase();
  const near = q.near?.trim().toLowerCase();
  const followed = new Set(store.user.followedProviderIds);

  const matches = store.providers.filter((p) => {
    if (q.categoryId && p.categoryId !== q.categoryId) return false;
    if (near && !p.location.city.toLowerCase().includes(near)) return false;
    if (text) {
      const hay = `${p.name} ${p.tagline} ${p.bio} ${p.location.city}`.toLowerCase();
      if (!hay.includes(text)) return false;
    }
    return true;
  });

  // Followed providers pin to the top; otherwise rank by rating.
  return matches.sort((a, b) => {
    const fa = followed.has(a.id) ? 1 : 0;
    const fb = followed.has(b.id) ? 1 : 0;
    if (fa !== fb) return fb - fa;
    return b.rating - a.rating;
  });
}

export function getProvider(id: ID): Provider {
  const p = store.providers.find((x) => x.id === id);
  if (!p) throw new ApiError("NOT_FOUND", "That provider could not be found.");
  return p;
}

export function getProviderByCode(code: string): Provider {
  const norm = code.trim().toLowerCase();
  const p = store.providers.find((x) => x.publicCode.toLowerCase() === norm);
  if (!p) throw new ApiError("NOT_FOUND", `No provider found for code "${code}".`);
  return p;
}

export function followProvider(id: ID): User {
  getProvider(id); // validates existence
  if (!store.user.followedProviderIds.includes(id)) {
    store.user.followedProviderIds.push(id);
  }
  return store.user;
}

export function unfollowProvider(id: ID): User {
  store.user.followedProviderIds = store.user.followedProviderIds.filter((x) => x !== id);
  return store.user;
}

// ---------------------------------------------------------------------------
// Services & resources
// ---------------------------------------------------------------------------

export function getServices(providerId: ID): Service[] {
  return store.services.filter((s) => s.providerId === providerId);
}

export function getService(id: ID): Service {
  return serviceById(id);
}

export function getResources(serviceId: ID): Resource[] {
  return store.resources.filter((r) => r.serviceId === serviceId && r.active);
}

// ---------------------------------------------------------------------------
// Availability
// ---------------------------------------------------------------------------

export function getAvailability(q: {
  serviceId: ID;
  resourceId?: ID;
  fromUtc: IsoUtc;
  toUtc: IsoUtc;
}): DayAvailability[] {
  const from = ms(q.fromUtc);
  const to = ms(q.toUtc);
  const tz = store.user.timezone;

  const relevant = store.slots.filter((s) => {
    if (s.serviceId !== q.serviceId) return false;
    if (q.resourceId && s.resourceId !== q.resourceId) return false;
    const start = ms(s.startUtc);
    return start >= from && start < to;
  });

  const byDate = new Map<string, Slot[]>();
  for (const s of relevant) {
    refreshStatus(s);
    const date = localDateStr(s.startUtc, tz);
    const list = byDate.get(date) ?? [];
    list.push(s);
    byDate.set(date, list);
  }

  return [...byDate.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([date, slots]) => {
      slots.sort((a, b) => ms(a.startUtc) - ms(b.startUtc));
      return {
        date,
        slots,
        totalCapacity: slots.reduce((n, s) => n + s.capacity, 0),
        totalBooked: slots.reduce((n, s) => n + s.bookedCount, 0),
      };
    });
}

export function getMonthDensity(q: {
  serviceId: ID;
  resourceId?: ID;
  month: string; // 'YYYY-MM'
}): MonthDensityCell[] {
  const [yStr, mStr] = q.month.split("-");
  const year = +yStr;
  const month = +mStr; // 1-based
  const tz = store.user.timezone;
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();

  // Accumulate remaining/total capacity per local date within the month.
  const remaining = new Map<string, number>();
  const total = new Map<string, number>();
  const now = Date.now();

  for (const s of store.slots) {
    if (s.serviceId !== q.serviceId) continue;
    if (q.resourceId && s.resourceId !== q.resourceId) continue;
    const date = localDateStr(s.startUtc, tz);
    if (!date.startsWith(q.month)) continue;
    total.set(date, (total.get(date) ?? 0) + s.capacity);
    const isOpen = ms(s.endUtc) > now && s.capacity > 0;
    const free = isOpen ? Math.max(0, s.capacity - s.bookedCount) : 0;
    remaining.set(date, (remaining.get(date) ?? 0) + free);
  }

  const cells: MonthDensityCell[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${q.month}-${String(d).padStart(2, "0")}`;
    const tot = total.get(date) ?? 0;
    const rem = remaining.get(date) ?? 0;
    let density: MonthDensityLevel = 0;
    if (tot > 0 && rem > 0) {
      const ratio = rem / tot;
      density = ratio < 0.34 ? 1 : ratio < 0.67 ? 2 : 3;
    }
    cells.push({ date, density });
  }
  return cells;
}

// ---------------------------------------------------------------------------
// Bookings
// ---------------------------------------------------------------------------

export function createBooking(input: {
  serviceId: ID;
  resourceId: ID;
  slotIds: ID[];
  partySize: number;
}): Booking {
  const service = serviceById(input.serviceId);
  const partySize = Math.max(1, Math.floor(input.partySize || 1));
  const ordered = resolveSelection(service, input.resourceId, input.slotIds, partySize);

  // Commit: consume capacity.
  for (const s of ordered) s.bookedCount += partySize;

  const booking: Booking = {
    id: `bk_rt_${Date.now()}_${bookingSeq++}`,
    reference: newReference(),
    userId: store.user.id,
    providerId: service.providerId,
    serviceId: service.id,
    resourceId: input.resourceId,
    slotIds: ordered.map((s) => s.id),
    startUtc: ordered[0].startUtc,
    endUtc: ordered[ordered.length - 1].endUtc,
    status: "confirmed",
    partySize,
    priceMinorUnits: totalPrice(service, ordered.length, partySize),
    currency: service.currency,
    createdAtUtc: new Date().toISOString(),
    changeHistory: [],
  };
  store.bookings.push(booking);
  return booking;
}

export function getBookings(scope: "upcoming" | "past" | "all"): Booking[] {
  const now = Date.now();
  const all = store.bookings.map(normalizeBooking);

  if (scope === "all") {
    return [...all].sort((a, b) => ms(b.startUtc) - ms(a.startUtc));
  }

  const isUpcoming = (b: Booking) => ms(b.endUtc) > now && effectiveStatus(b) !== "completed";
  if (scope === "upcoming") {
    return all.filter(isUpcoming).sort((a, b) => ms(a.startUtc) - ms(b.startUtc));
  }
  // past: completed, or anything whose slot has elapsed
  return all.filter((b) => !isUpcoming(b)).sort((a, b) => ms(b.startUtc) - ms(a.startUtc));
}

export function getBooking(id: ID): Booking {
  const b = store.bookings.find((x) => x.id === id);
  if (!b) throw new ApiError("NOT_FOUND", "That booking could not be found.");
  return normalizeBooking(b);
}

export function rescheduleBooking(id: ID, newSlotIds: ID[]): Booking {
  const booking = getBooking(id);
  const service = serviceById(booking.serviceId);

  if (effectiveStatus(booking) !== "confirmed") {
    throw new ApiError("CUTOFF_PASSED", "Only upcoming bookings can be moved.");
  }
  if (cutoffPassed(booking.startUtc, service.cancellationCutoffHours)) {
    throw new ApiError(
      "CUTOFF_PASSED",
      `Changes closed — within ${service.cancellationCutoffHours}h of the start.`,
    );
  }

  // Acquire the new slots first (validates + capacity-checks, crediting back
  // this booking's own current hold on any re-selected slot). Throws on fail
  // with nothing changed.
  const next = resolveSelection(
    service,
    booking.resourceId,
    newSlotIds,
    booking.partySize,
    booking,
  );

  // Release old, then take new. (Guarded so overlap nets out correctly.)
  for (const id2 of booking.slotIds) {
    const s = slotById(id2);
    if (s) s.bookedCount = Math.max(0, s.bookedCount - booking.partySize);
  }
  for (const s of next) s.bookedCount += booking.partySize;

  const fromStart = booking.startUtc;
  booking.slotIds = next.map((s) => s.id);
  booking.startUtc = next[0].startUtc;
  booking.endUtc = next[next.length - 1].endUtc;
  booking.priceMinorUnits = totalPrice(service, next.length, booking.partySize);
  booking.changeHistory.push({
    atUtc: new Date().toISOString(),
    fromStartUtc: fromStart,
    toStartUtc: booking.startUtc,
  });
  return booking;
}

export function cancelBooking(id: ID): Booking {
  const booking = getBooking(id);
  const service = serviceById(booking.serviceId);

  if (booking.status === "cancelled") return booking;
  if (effectiveStatus(booking) === "completed") {
    throw new ApiError("CUTOFF_PASSED", "Completed bookings can't be cancelled.");
  }
  if (cutoffPassed(booking.startUtc, service.cancellationCutoffHours)) {
    throw new ApiError(
      "CUTOFF_PASSED",
      `Changes closed — within ${service.cancellationCutoffHours}h of the start.`,
    );
  }

  booking.status = "cancelled";
  booking.cancelledAtUtc = new Date().toISOString();
  for (const id2 of booking.slotIds) {
    const s = slotById(id2);
    if (s) s.bookedCount = Math.max(0, s.bookedCount - booking.partySize);
  }
  return booking;
}

export function leaveReview(id: ID, rating: number, text: string): Booking {
  const booking = getBooking(id);
  if (effectiveStatus(booking) !== "completed") {
    throw new ApiError("NOT_FOUND", "Only completed bookings can be reviewed.");
  }
  const clamped = Math.min(5, Math.max(1, Math.round(rating)));
  booking.review = { rating: clamped, text: text.trim(), createdAtUtc: new Date().toISOString() };
  return booking;
}

// ---------------------------------------------------------------------------
// Account
// ---------------------------------------------------------------------------

export function getCurrentUser(): User {
  return store.user;
}

export function updateUser(patch: Partial<User>): User {
  const allowed: (keyof User)[] = ["displayName", "email", "timezone", "avatarUrl"];
  const next: Record<string, unknown> = {};
  for (const key of allowed) {
    const value = patch[key];
    if (value !== undefined) next[key] = value;
  }
  Object.assign(store.user, next);
  return store.user;
}
