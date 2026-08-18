/**
 * ============================================================================
 * DOMAIN CONTRACT — the single source of truth shared with the backend team.
 * ============================================================================
 *
 * This file is the contract. The backend will produce and consume exactly
 * these shapes over HTTP. The floor rule from the brief applies: you may ADD
 * fields, never REMOVE them. Nothing here names a vertical ("car", "dog",
 * "yoga"); the codebase knows only Provider / Service / Resource / Slot /
 * Booking / User. Vertical-specific language lives in src/config/verticals.ts.
 *
 * TIME RULES (enforced everywhere):
 *  - Every timestamp in state and in the API layer is UTC ISO 8601 with 'Z'.
 *  - Convert to the user's timezone ONLY at render time, using User.timezone.
 *  - Never build a Date from a naive string; never do `+ 86400000` date maths.
 */

export type ID = string;

/** ISO 8601, always UTC, always with a trailing 'Z'. Never store local time. */
export type IsoUtc = string;

/** Runtime-switchable demo vertical. Maps 1:1 to a BookingModel. */
export type VerticalId = "fleet" | "oneToOne" | "group";

export type BookingModel =
  | "unit_selection" // many distinct resources, capacity 1 each; user picks the unit
  | "one_to_one" // single resource, capacity 1
  | "shared_capacity"; // single resource, capacity > 1; user picks party size

export interface Provider {
  id: ID;
  name: string;
  avatarUrl: string;
  coverUrl?: string;
  tagline: string;
  bio: string;
  categoryId: string;
  location: { city: string; country: string; lat: number; lng: number };
  rating: number; // 0–5
  reviewCount: number;
  priceFromMinorUnits: number | null; // cheapest service; null when none priced
  currency: string; // ISO 4217 for priceFromMinorUnits ("" when none)
  links: { label: string; url: string }[];
  publicCode: string; // e.g. "HERTZ-4471" — used by code entry and QR scan
  serviceIds: ID[];
}

export interface Service {
  id: ID;
  providerId: ID;
  name: string;
  description: string;
  imageUrl?: string;
  bookingModel: BookingModel;
  slotDurationMinutes: number; // provider-configurable: 30, 60, 1440 (full day)…
  minSlotsPerBooking: number; // 1 for most; fleet may require 1
  maxSlotsPerBooking: number; // 1 = single slot; >1 enables consecutive-range booking
  priceMinorUnits: number; // per slot
  currency: string; // ISO 4217
  cancellationCutoffHours: number; // no change/cancel inside this window
  autoApprove: boolean; // false → new bookings land as pending requests
  resourceIds: ID[];
}

export interface Resource {
  id: ID;
  serviceId: ID;
  name: string; // "Unit 4471", "Studio A", "Ana Ruiz"
  description?: string;
  imageUrl?: string;
  capacity: number; // seats per slot. 1 for unit_selection & one_to_one
  attributes: { label: string; value: string }[]; // spec rows shown on the resource card
  active: boolean;
}

export type SlotStatus =
  | "available"
  | "partially_booked"
  | "full"
  | "blocked"
  | "past";

export interface Slot {
  id: ID;
  serviceId: ID;
  resourceId: ID;
  startUtc: IsoUtc;
  endUtc: IsoUtc;
  capacity: number;
  bookedCount: number;
  status: SlotStatus; // derived, but sent explicitly — the UI never recomputes it
}

export type BookingStatus =
  | "confirmed"
  | "cancelled"
  | "completed"
  | "pending" // awaiting owner approval on a manual-approve service
  | "rejected"; // owner declined the request

export interface Booking {
  id: ID;
  reference: string; // human-readable, e.g. "BK-7QK2M9"
  userId: ID;
  providerId: ID;
  serviceId: ID;
  providerName: string; // embedded by the API so a list needn't fetch each provider
  serviceName: string; // embedded by the API so a list needn't fetch each service
  resourceId: ID;
  slotIds: ID[]; // >1 for multi-slot / multi-day bookings
  startUtc: IsoUtc; // first slot start
  endUtc: IsoUtc; // last slot end
  status: BookingStatus;
  partySize: number; // 1 unless shared_capacity
  priceMinorUnits: number; // total
  currency: string;
  createdAtUtc: IsoUtc;
  cancelledAtUtc?: IsoUtc;
  changeHistory: { atUtc: IsoUtc; fromStartUtc: IsoUtc; toStartUtc: IsoUtc }[];
  review?: { rating: number; text: string; createdAtUtc: IsoUtc };
}

export interface User {
  id: ID;
  displayName: string;
  email: string;
  avatarUrl: string;
  timezone: string; // IANA, e.g. "Europe/Warsaw"
  verified: boolean;
  followedProviderIds: ID[];
}

export interface DayAvailability {
  date: string; // 'YYYY-MM-DD' in the user's timezone
  slots: Slot[];
  totalCapacity: number;
  totalBooked: number;
}

/** Coarse per-day openness used by the month grid. 0 none … 3 wide open. */
export type MonthDensityLevel = 0 | 1 | 2 | 3;

export interface MonthDensityCell {
  date: string; // 'YYYY-MM-DD'
  density: MonthDensityLevel;
}

// --- business mode (owner) — additive, owner-only shapes -------------------
// These mirror the backend's /owner/* aggregation envelopes and the owner-only
// clientEmail on bookings. They are not part of the customer contract.

/** A booking as the owner sees it — the standard Booking plus who booked. */
export interface OwnerBooking extends Booking {
  clientEmail?: string;
}

/** Screening card for a client requesting a booking (Requests tab).
 *  Not exported: only reached through `OwnerRequest.client`. */
interface RequestClient {
  id: ID;
  displayName: string;
  email: string;
  avatarUrl: string;
  memberSinceUtc: IsoUtc | null;
  totalBookings: number;
  bookingsWithProvider: number;
  cancelledWithProvider: number;
  rating: number | null; // reputation from businesses; null when never rated
  reviewCount: number;
}

/** A pending request enriched for the Requests tab. */
export interface OwnerRequest extends OwnerBooking {
  client: RequestClient;
  serviceName: string;
  providerName: string;
}

/** One service with its glanceable owner stats (Services tab). */
export interface OwnerServiceSummary extends Service {
  providerName: string;
  stats: {
    upcomingBookings: number;
    pastBookings: number;
    totalBookings: number;
    pendingRequests: number;
    revenueMinorUnits: number;
    currency: string;
    avgRating: number;
    reviewCount: number;
  };
}

/** The Dashboard aggregation envelope. */
export interface OwnerDashboard {
  provider: Provider | null;
  providers: Provider[];
  glance: {
    upcomingBookings: {
      total: number;
      byService: { serviceId: ID; serviceName: string; count: number }[];
    };
    clientSatisfaction: {
      currentRating: number;
      reviewCount: number;
      deltaPct: number;
      basis: string;
    };
    revenue: {
      minorUnits: number;
      currency: string;
      byCurrency: { currency: string; minorUnits: number }[];
      bookingCount: number;
      period: string; // 'YYYY-MM'
    };
  };
  weekBookings: OwnerBooking[];
  requests: OwnerRequest[];
  pendingCount: number;
}

/** A public review with best-effort author (Profile tab). */
export interface ProviderReview {
  rating: number;
  text: string;
  createdAtUtc: IsoUtc;
  author: string;
}

/** A customer's reputation as businesses see it (customer Profile tab). */
export interface ClientReputation {
  score: number;
  count: number;
  reviews: { author: string; rating: number; text: string; createdAtUtc: IsoUtc | null }[];
}

// --- messaging — 1:1 conversations between a client and a provider ----------
// A new entity riding on the neutral spine; both personas share these shapes.

/** One inbox row: the current user's thread with the other party. */
export interface Conversation {
  id: ID;
  providerId: ID;
  /** Who the current user is talking to — the business (for a client) or the
   *  customer (for an owner). Resolved server-side across the RLS boundary. */
  otherParty: { id: ID; name: string; avatarUrl: string | null };
  lastMessagePreview: string | null;
  lastMessageAtUtc: IsoUtc | null;
  unreadCount: number;
}

/** One message in a thread. `mine` is derived server-side from the viewer, so
 *  the UI aligns bubbles without knowing ids. A soft-deleted message keeps its
 *  envelope but blanks `body` (render the placeholder from `deletedAtUtc`). */
export interface Message {
  id: ID;
  conversationId: ID;
  senderId: ID;
  body: string;
  replyToId: ID | null;
  createdAtUtc: IsoUtc;
  deliveredAtUtc: IsoUtc | null;
  readAtUtc: IsoUtc | null;
  deletedAtUtc: IsoUtc | null;
  mine: boolean;
}
