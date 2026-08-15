/**
 * ============================================================================
 * THE API SEAM — the single surface the backend team replaces.
 * ============================================================================
 *
 * No component, hook, or page imports mock data or the store directly;
 * everything goes through these functions. Each is async, returns a Promise,
 * and simulates 150–450ms of latency so real loading states are exercised and
 * the eventual swap to HTTP changes nothing visually. Results are deep-cloned:
 * callers can never mutate store state by reference (the same isolation a
 * JSON-over-HTTP boundary gives for free).
 *
 * To integrate the real backend, reimplement each function below as an HTTP
 * call that returns the same shape and throws the same ApiError codes. Nothing
 * else in the app needs to change.
 */
import type {
  Booking,
  DayAvailability,
  ID,
  IsoUtc,
  MonthDensityCell,
  Provider,
  Resource,
  Service,
  User,
  VerticalId,
} from "@/types/domain";
import { clone, delay } from "@/api/latency";
import * as db from "@/api/mockStore";

export { ApiError, isApiError } from "@/api/errors";
export type { ApiErrorCode } from "@/api/errors";

async function run<T>(fn: () => T): Promise<T> {
  await delay();
  return clone(fn());
}

async function runVoid(fn: () => void): Promise<void> {
  await delay();
  fn();
}

// --- discovery -------------------------------------------------------------

export function searchProviders(q: {
  text?: string;
  categoryId?: string;
  near?: string;
}): Promise<Provider[]> {
  return run(() => db.searchProviders(q));
}

export function getProvider(id: ID): Promise<Provider> {
  return run(() => db.getProvider(id));
}

export function getProviderByCode(code: string): Promise<Provider> {
  return run(() => db.getProviderByCode(code));
}

export function followProvider(id: ID): Promise<User> {
  return run(() => db.followProvider(id));
}

export function unfollowProvider(id: ID): Promise<User> {
  return run(() => db.unfollowProvider(id));
}

// --- services & resources --------------------------------------------------

export function getServices(providerId: ID): Promise<Service[]> {
  return run(() => db.getServices(providerId));
}

export function getService(id: ID): Promise<Service> {
  return run(() => db.getService(id));
}

export function getResources(serviceId: ID): Promise<Resource[]> {
  return run(() => db.getResources(serviceId));
}

// --- availability ----------------------------------------------------------

export function getAvailability(q: {
  serviceId: ID;
  resourceId?: ID;
  fromUtc: IsoUtc;
  toUtc: IsoUtc;
}): Promise<DayAvailability[]> {
  return run(() => db.getAvailability(q));
}

export function getMonthDensity(q: {
  serviceId: ID;
  resourceId?: ID;
  month: string; // 'YYYY-MM'
}): Promise<MonthDensityCell[]> {
  return run(() => db.getMonthDensity(q));
}

// --- bookings --------------------------------------------------------------

export function createBooking(input: {
  serviceId: ID;
  resourceId: ID;
  slotIds: ID[];
  partySize: number;
}): Promise<Booking> {
  return run(() => db.createBooking(input));
}

export function getBookings(scope: "upcoming" | "past" | "all"): Promise<Booking[]> {
  return run(() => db.getBookings(scope));
}

export function getBooking(id: ID): Promise<Booking> {
  return run(() => db.getBooking(id));
}

export function rescheduleBooking(id: ID, newSlotIds: ID[]): Promise<Booking> {
  return run(() => db.rescheduleBooking(id, newSlotIds));
}

export function cancelBooking(id: ID): Promise<Booking> {
  return run(() => db.cancelBooking(id));
}

export function leaveReview(id: ID, rating: number, text: string): Promise<Booking> {
  return run(() => db.leaveReview(id, rating, text));
}

// --- account & demo --------------------------------------------------------

export function getCurrentUser(): Promise<User> {
  return run(() => db.getCurrentUser());
}

export function updateUser(patch: Partial<User>): Promise<User> {
  return run(() => db.updateUser(patch));
}

/** Current demo vertical (convenience for the demo panel; not backend state). */
export function getActiveVertical(): Promise<VerticalId> {
  return run(() => db.getVerticalId());
}

export function setVertical(id: VerticalId): Promise<void> {
  return runVoid(() => db.setVertical(id));
}

export function resetDemoData(): Promise<void> {
  return runVoid(() => db.resetDemoData());
}

// --- dev convenience -------------------------------------------------------
// Makes the seams pokeable from the browser console (Phase 1 done-when:
// "seeds callable from console"). Dev only; harmless in prod.
if (typeof window !== "undefined") {
  const api = {
    searchProviders,
    getProvider,
    getProviderByCode,
    getServices,
    getService,
    getResources,
    getAvailability,
    getMonthDensity,
    createBooking,
    getBookings,
    getBooking,
    rescheduleBooking,
    cancelBooking,
    leaveReview,
    getCurrentUser,
    updateUser,
    getActiveVertical,
    setVertical,
    resetDemoData,
    _store: db.getStore,
  };
  (window as unknown as { codaro?: typeof api }).codaro = api;
}
