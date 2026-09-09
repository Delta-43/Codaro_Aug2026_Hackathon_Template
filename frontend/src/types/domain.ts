// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

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

/** Runtime-switchable demo vertical.
 *
 *  This no longer maps 1:1 to a `BookingModel` — the backend reports the
 *  booking model per service (`Service.bookingModel`), and a vertical is now
 *  purely a UI vocabulary bundle (`src/config/verticals.ts`). `group`, for
 *  instance, shares `one_to_one` with `oneToOne` but speaks a different
 *  language and books without a date at all. Read the model off the service,
 *  never off the vertical id. */
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
  /** `capabilities` RESOLVED for this service — the global block with the
   *  service's own `metadata.capabilities` override merged in. Gate a surface on
   *  this, not on the global block from `/config`: the routers gate per service,
   *  so a service-level override is invisible to the global value. */
  capabilities: Record<string, boolean>;
  /** `pricing.model` — how the price is arrived at. `priceMinorUnits` above is
   *  only the BASE RATE; under anything but "fixed" it is not the price, so
   *  render a total from a `Quote`, never by multiplying this. */
  pricingModel: string;
  /** `pricing.rate.per` — what one unit of the base rate buys ("slot", "hour",
   *  "person", "booking", "unit"). */
  rateUnit: string;
  /** `pricing.chargePerPerson` — whether the base rate is multiplied by the
   *  party. Only used to PREVIEW a total when the engine's quote can't be
   *  reached; the quote stays authoritative. Optional: older backends omit it,
   *  and the engine's own default is true. */
  chargePerPerson?: boolean;
  /** `payments.flow` — when money is collected. One of the engine's five:
   *  "none" (no payment in the product at all), "prepay", "pay_on_site",
   *  "invoice_after", "split". NOT "deposit" — that is a `pricing.deposit`
   *  concern, and branching on it here matched nothing. */
  paymentFlow: string;
  /** `payments.billingCycle` — "none" for one-off, else "monthly"/"annual". */
  billingCycle: string;
  /** `prerequisites` — what must be satisfied before this can be confirmed. */
  prerequisites: Prerequisite[];
  /** `recurrence` — the repeat patterns this service offers, already gated on
   *  the capability, so `enabled` alone decides whether to show the control. */
  recurrence: { enabled: boolean; patterns: string[]; maxOccurrences: number };
  /** Whether full slots offer a queue (`timing.waitlist`), capability-gated. */
  waitlist: { enabled: boolean };
  /** `booking.unitKind` — what one bookable unit IS ("time_slot", "seat",
   *  "room", "asset", "class_capacity"…). Vocabulary, not behaviour. */
  unitKind: string;
  /** `booking.granularity` — how finely the customer picks WHEN. "none" means
   *  they pick nothing at all: they submit a request and the business assigns
   *  the date afterwards (`timing.confirmation: "request_approve"`). Behaviour,
   *  not vocabulary — the calendar must not render for a "none" service.
   *
   *  Optional, for two reasons: an older backend does not send it, and the
   *  landing page's static demo `Service` literal predates it. Every reader
   *  therefore tests `granularity === "none"` (undefined-safe) rather than
   *  branching on its absence. */
  granularity?: string;
  /** `timing.approvalWindowHours` — how long the business has to respond to a
   *  request. Optional: older backends do not send it. */
  approvalWindowHours?: number;
  /** `booking.party` — how many, and (with `composition`) of what kinds. A
   *  non-empty `composition` means the party splits into priced bands: the
   *  booking sends counts per band and the engine weights them. */
  party: {
    mode: string;
    min: number;
    max: number | null;
    composition: PartyBand[];
    matchResourceCapacity: boolean;
  };
  /** `booking.subject` — the pet/vehicle/child the booking is ABOUT. When
   *  enabled the fields are collected on the confirm screen and validated
   *  server-side; a missing required one is a rejection. */
  subject: { enabled: boolean; noun: string; fields: SubjectField[] };
  /** `booking.options` — paid extras. Descriptors only: the price of a chosen
   *  option is resolved server-side, never taken from the client. */
  options: BookingOption[];
  /** `booking.sequence` — a course/programme booked as N sessions with a gap
   *  between them, rather than one appointment. */
  sequence: { enabled: boolean; steps: number; minGapHours: number; maxGapHours: number | null };
  /** `payments.schedule` — when each part of the money falls due. Display-only
   *  (no PSP exists), but it is what the customer is agreeing to. */
  paymentSchedule: PaymentStep[];
  /** `location.modes` — on_site / at_customer / remote / delivery / pickup. */
  locationModes: string[];
  locationDefault: string;
  resourceIds: ID[];
}

/** One band of `booking.party.composition` — an adult, a child, a senior.
 *  `priceFactor` multiplies the base rate for each head in that band. */
export interface PartyBand {
  key: string;
  label: string;
  priceFactor?: number;
}

/** One field of `booking.subject.fields`. */
export interface SubjectField {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

/** One entry of `booking.options` — a paid extra. A "boolean" option is a
 *  toggle worth `priceMinorUnits`; a "select" option offers `choices`. */
export interface BookingOption {
  key: string;
  label: string;
  type: string;
  priceMinorUnits?: number;
  choices?: { key: string; label: string; priceMinorUnits?: number }[];
}

/** One step of `payments.schedule` — "25% deposit now, balance 48h before". */
export interface PaymentStep {
  key: string;
  label?: string;
  kind: string;
  value: number;
  dueOffsetHours?: number;
}

/** One entry of the config's `prerequisites` block. */
export interface Prerequisite {
  key: string;
  kind: string;
  label: string;
  appliesTo: string;
  required: boolean;
  blocksConfirmation: boolean;
}

/** A priced selection from `POST /bookings/quote` — the authoritative total.
 *  The engine that produces this is the one that charges, so the UI must show
 *  this number rather than recomputing it. */
export interface Quote {
  amountMinorUnits: number;
  currency: string;
  /** > 0 when `pricing.deposit` applies: the part due now. */
  depositMinorUnits: number;
  /** Why the total is what it is — base rate, tier, fees, cap adjustment. */
  breakdown: { label: string; amountMinorUnits: number }[];
  paymentFlow: string;
  /** The entitlement applied to this quote, or null. Shown so a discount is
   *  never silent — an unexplained lower price confuses as much as a surcharge. */
  entitlement: {
    key: string;
    label: string;
    discountBps: number;
    creditsRemaining: number | null;
  } | null;
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

// Not exported: the only external consumer (the landing calendar demo) moved
// to landing/, which keeps its own copy of this
// type. Kept here, unexported, since `Slot.status` below still needs it.
type SlotStatus =
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
  providerName: string;
  /** The provider's logo, embedded so a bookings list needn't fetch each one. */
  providerAvatarUrl?: string; // embedded by the API so a list needn't fetch each provider
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
  /** The return leg, or null when the service loans nothing. Non-null only
   *  where `inventory.returnRequired` — most deployments never see it. */
  loan: Loan | null;
  /** Present on the FIRST booking of a repeating series (`recurrence`), naming
   *  every occurrence that was booked and every one that could not be. */
  series?: BookingSeries;
  /** Blocking `prerequisites` still outstanding. Non-empty means this cannot be
   *  confirmed yet — the owner records each one as met. */
  prerequisitesPending: string[];
  prerequisitesMet: string[];
  /** What is owed and whether it is settled. Derived from `payments.flow`
   *  server-side, so it never drifts from the config after a pivot. */
  payment: PaymentState;
  /** What the customer chose where the config offered a choice. All three are
   *  null/empty on a deployment that declares no composition, options or
   *  subject — i.e. on most of them. */
  partyBands: Record<string, number> | null;
  /** Chosen `booking.options`, with the price the engine actually charged. */
  options: { key: string; label: string; amountMinorUnits: number }[];
  /** The `booking.subject` this booking is about, as validated on create. */
  subject: Record<string, unknown> | null;
  /** The deployment's own `metaFields.bookings` values, echoed back by the
   *  backend. Only declared keys appear; `{}` where none are declared. */
  metadata?: Record<string, unknown> | null;
}

/** Derived payment position on a booking (`payments.flow`). `state` is one of
 *  none | not_required | invoiced | deposit_due | due | paid. */
export interface PaymentState {
  flow: string;
  state: string;
  /** `payments.payer` — who is billed. "customer" on almost every deployment;
   *  "third_party" where someone other than the booker settles it (an estate,
   *  an insurer, an employer). Optional: older backends do not send it. */
  payer?: string;
  totalMinorUnits: number;
  depositMinorUnits: number;
  paidMinorUnits: number;
  outstandingMinorUnits: number;
  currency: string;
}

/** A place in a slot's queue (`timing.waitlist`). */
export interface WaitlistEntry {
  id: ID;
  slotId: ID;
  serviceId: ID | null;
  resourceId: ID | null;
  partySize: number;
  position: number;
  status: string;
  bookingId: ID | null;
  createdAtUtc: IsoUtc;
  /** How many are ahead — `position` is a join stamp, not a place in the queue. */
  peopleAhead?: number;
}

/** The return leg of a rentable booking (`inventory.returnRequired`). The
 *  overdue fee is computed server-side from the clock, never stored. */
export interface Loan {
  dueBackUtc: IsoUtc;
  returnedAtUtc: IsoUtc | null;
  daysOverdue: number;
  overdueFeeMinorUnits: number;
  overdueFeePerDayMinorUnits: number;
}

/** The outcome of a repeating booking request. `skipped` is not an error — an
 *  occurrence with no open slot is reported so the customer is never left
 *  believing they hold dates they do not. */
export interface BookingSeries {
  id: ID;
  pattern: string;
  requested: number;
  bookedIds: ID[];
  skipped: { startUtc: IsoUtc; reason: string }[];
}

/** A plan the deployment sells (`entitlements.plans[]`). */
export interface EntitlementPlan {
  key: string;
  label: string;
  priceMinorUnits: number | null;
  cycle: string;
  credits: number | null;
  discountBps: number;
}

/** A plan this customer actually holds. */
export interface HeldEntitlement {
  id: ID;
  planKey: string;
  label: string;
  status: string;
  discountBps: number;
  creditsTotal: number | null;
  creditsUsed: number;
  creditsRemaining: number | null;
  startsAt: IsoUtc | null;
  endsAt: IsoUtc | null;
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
  /** The reviewer's public profile photo; "" when they have none. */
  authorAvatarUrl?: string;
}

/** A customer's reputation as businesses see it (customer Profile tab). */
export interface ClientReputation {
  score: number;
  count: number;
  reviews: {
    author: string;
    /** The reviewing business's logo; "" when it has none. */
    authorAvatarUrl?: string;
    rating: number;
    text: string;
    createdAtUtc: IsoUtc | null;
  }[];
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
