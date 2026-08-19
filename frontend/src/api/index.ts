/**
 * ============================================================================
 * THE API SEAM — now real HTTP to the FastAPI backend.
 * ============================================================================
 *
 * Every component/hook/page goes through these functions; none touch transport
 * details. Each returns the exact domain shape from @/types/domain and throws
 * `ApiError` with the backend's code, so the UI's error handling (inline "slot
 * was just taken", disabled-with-reason, retry) stays consistent across calls.
 *
 * Auth: the signed-in Supabase session's access token is attached as
 * `Authorization: Bearer <jwt>` on every call; the backend verifies it and
 * derives identity + RLS scope from it (never from the request body).
 */
import type {
  Booking,
  ClientReputation,
  Conversation,
  DayAvailability,
  EntitlementPlan,
  HeldEntitlement,
  ID,
  IsoUtc,
  Message,
  MonthDensityCell,
  OwnerBooking,
  OwnerDashboard,
  OwnerRequest,
  OwnerServiceSummary,
  Provider,
  ProviderReview,
  Quote,
  Resource,
  Service,
  Slot,
  WaitlistEntry,
  User,
  VerticalId,
} from "@/types/domain";

export type {
  ClientReputation,
  OwnerBooking,
  OwnerDashboard,
  OwnerRequest,
  OwnerServiceSummary,
  ProviderReview,
} from "@/types/domain";
import { ApiError, type ApiErrorCode } from "@/api/errors";
import { getAccessToken } from "@/lib/auth";

export { ApiError, isApiError } from "@/api/errors";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Query = Record<string, string | number | undefined | null>;

function qs(params: Query): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/** Map an HTTP status to an ApiError code when the backend didn't send one. */
function statusCode(status: number): ApiErrorCode {
  if (status === 404) return "NOT_FOUND";
  if (status === 400) return "INVALID_RANGE";
  return "NETWORK";
}

async function toApiError(res: Response, method: string, path: string): Promise<ApiError> {
  let code: ApiErrorCode = statusCode(res.status);
  let message = `${method} ${path} failed (${res.status})`;
  let details: Record<string, unknown> | undefined;
  try {
    const body = await res.json();
    const d = (body as { detail?: unknown })?.detail;
    if (Array.isArray(d)) {
      // FastAPI/Pydantic 422: [{loc, msg, type}, ...] — surface the first
      // problem instead of discarding the whole list as "an object".
      const first = d[0] as { msg?: string; loc?: unknown[] } | undefined;
      if (typeof first?.msg === "string") {
        code = "VALIDATION_ERROR";
        const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
        message = field && field !== "body" ? `${field}: ${first.msg}` : first.msg;
      }
    } else if (d && typeof d === "object") {
      // Backend's structured envelope: { code, message, details? }.
      const obj = d as { code?: string; message?: string; details?: Record<string, unknown> };
      if (typeof obj.code === "string") code = obj.code as ApiErrorCode;
      if (typeof obj.message === "string") message = obj.message;
      details = obj.details;
    } else if (typeof d === "string") {
      message = d; // FastAPI's plain HTTPException detail (401/403/etc.)
    }
  } catch {
    /* non-JSON body — keep the status-derived fallback */
  }
  return new ApiError(code, message, details);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    });
  } catch (e) {
    throw new ApiError("NETWORK", e instanceof Error ? e.message : "Network error.");
  }
  if (!res.ok) throw await toApiError(res, init?.method ?? "GET", path);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Like `request`, but for a `FormData` body — the browser must set its own
 *  multipart boundary, so `Content-Type` is deliberately omitted here. */
async function requestForm<T>(path: string, method: string, body?: FormData): Promise<T> {
  const token = await getAccessToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      body,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
  } catch (e) {
    throw new ApiError("NETWORK", e instanceof Error ? e.message : "Network error.");
  }
  if (!res.ok) throw await toApiError(res, method, path);
  return res.json() as Promise<T>;
}

const post = (path: string, body?: unknown) =>
  request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

const patch = (path: string, body: unknown) =>
  request(path, { method: "PATCH", body: JSON.stringify(body) });

const del = (path: string) => request(path, { method: "DELETE" });

// --- config / facets -------------------------------------------------------

/** Which search facets this deployment offers (`discovery.facets`), so the
 *  filter UI pivots with the config.
 *
 *  Reads `discovery` FIRST and falls back to `search`: `normalize()` mirrors the
 *  two, but the v1 `search.facets` mirror is deliberately trimmed to the three
 *  keys v1 declared — so reading it, as this did, made `availability` and
 *  `unitKind` unreachable no matter what the pivot file said. */
export type SearchFacets = {
  price: boolean;
  distance: boolean;
  rating: boolean;
  availability: boolean;
  unitKind: boolean;
};

export const DEFAULT_FACETS: SearchFacets = {
  price: true,
  distance: true,
  rating: true,
  availability: true,
  unitKind: false,
};

export function facetsFromConfig(cfg: unknown): SearchFacets {
  const c = cfg as {
    discovery?: { facets?: Partial<SearchFacets> };
    search?: { facets?: Partial<SearchFacets> };
  };
  const f = { ...(c?.search?.facets ?? {}), ...(c?.discovery?.facets ?? {}) };
  return {
    price: f.price ?? DEFAULT_FACETS.price,
    distance: f.distance ?? DEFAULT_FACETS.distance,
    rating: f.rating ?? DEFAULT_FACETS.rating,
    availability: f.availability ?? DEFAULT_FACETS.availability,
    unitKind: f.unitKind ?? DEFAULT_FACETS.unitKind,
  };
}

export async function getSearchFacets(): Promise<SearchFacets> {
  return facetsFromConfig(await request<unknown>("/config"));
}

/** The pivot's tenancy mode. `"single"` collapses the marketplace to one implicit
 *  business (the site itself): no provider browsing, the sole provider is resolved
 *  from `providerCode` and locked in automatically. Absent/`"multi"` (the default)
 *  keeps the multi-provider marketplace. Config passes through `GET /config`
 *  verbatim, so this reads a top-level key the backend never interprets. */
export type Tenancy = { mode: "single" | "multi"; providerCode: string | null };

/** Parse the tenancy block from a raw `/config` payload, so the shape/parse
 *  lives in one place. Defaults to the multi-provider marketplace. */
function tenancyFromConfig(cfg: unknown): Tenancy {
  const t = (cfg as { tenancy?: { mode?: string; providerCode?: string } })?.tenancy ?? {};
  return {
    mode: t.mode === "single" ? "single" : "multi",
    providerCode: t.providerCode ?? null,
  };
}

export async function getTenancy(): Promise<Tenancy> {
  return tenancyFromConfig(await request<unknown>("/config"));
}

/** The pivot's location settings. `origin` is the point search distances are
 *  measured from and `distanceUnit` the unit they render in — both were
 *  hardcoded to Warsaw/km in `lib/geo.ts` before v2 of the config. `timezone` is
 *  the business's own zone, used as the availability fallback for a visitor who
 *  has not signed in (who previously always got UTC). */
type LocationConfig = {
  origin: { city?: string; lat: number; lng: number } | null;
  distanceUnit: "km" | "mi";
  timezone: string;
};

function locationFromConfig(cfg: unknown): LocationConfig {
  const l =
    (cfg as {
      location?: {
        origin?: { city?: string; lat?: number; lng?: number } | null;
        distanceUnit?: string;
        timezone?: string;
      };
    })?.location ?? {};
  const o = l.origin;
  return {
    origin:
      o && typeof o.lat === "number" && typeof o.lng === "number"
        ? { city: o.city, lat: o.lat, lng: o.lng }
        : null,
    distanceUnit: l.distanceUnit === "mi" ? "mi" : "km",
    timezone: l.timezone || "UTC",
  };
}

/** The on/off spine from the pivot file. A false capability must hide the UI
 *  surface AND make the backend refuse the write — the backend half was wired
 *  first, so the client read none of this and showed surfaces that 404'd.
 *  Unknown keys pass through: the client only ever asks about ones it gates. */
export type Capabilities = Record<string, boolean>;

function capabilitiesFromConfig(cfg: unknown): Capabilities {
  const raw = (cfg as { capabilities?: Record<string, unknown> })?.capabilities ?? {};
  const out: Capabilities = {};
  for (const [key, value] of Object.entries(raw)) {
    if (typeof value === "boolean") out[key] = value;
  }
  return out;
}

/** The pivot file's `terms` block — the vocabulary the engine is configured with.
 *  Served since v1 and read by nothing: the UI rendered `config/verticals.ts`, a
 *  static three-vertical file, so pivoting `service` to "Plan" and `slot` to
 *  "Billing period" changed the seed data and left every label saying "Subject"
 *  and "session". Every key is optional — a term the config omits falls back to
 *  the static vertical's word rather than rendering an empty label. */
export type ConfigTerms = Partial<
  Record<
    | "provider"
    | "providers"
    | "service"
    | "services"
    | "resource"
    | "resources"
    | "slot"
    | "slots"
    | "booking"
    | "bookings"
    | "client"
    | "clients"
    | "party",
    string
  >
>;

/** The pivot file's `copy` block — whole sentences the UI shows at named moments.
 *  Same story as `terms`: served, never read. Optional per key for the same
 *  reason. `waitlistJoined` / `quoteRequested` / `depositDue` /
 *  `prerequisiteBlocked` belong to surfaces that have no backend yet; they are
 *  parsed here so the seam is ready, and deliberately not rendered. */
export type ConfigCopy = Partial<
  Record<
    | "landingTitle"
    | "landingSubtitle"
    | "confirmTitle"
    | "emptyStateSlots"
    | "emptyStateBookings"
    | "requestPending"
    | "waitlistJoined"
    | "quoteRequested"
    | "depositDue"
    | "prerequisiteBlocked",
    string
  >
>;

/** Keep only the string values, so a malformed config yields a *missing* key
 *  (which falls back) rather than `undefined` rendered as a label. */
function stringsOnly<T extends string>(raw: unknown): Partial<Record<T, string>> {
  const out: Partial<Record<T, string>> = {};
  if (!raw || typeof raw !== "object") return out;
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof value === "string" && value.trim() !== "") out[key as T] = value;
  }
  return out;
}

/** `metaFields.{entity}` — the no-migration extension point. The backend has
 *  validated these on write since v2 (a booking's `metadata` is checked against
 *  `metaFields.bookings`), but nothing ever RENDERED them, so a declared domain
 *  field had no input on any screen and could only be filled by curl. */
export type MetaField = {
  key: string;
  label: string;
  type: string;
  options?: string[];
  required?: boolean;
};
export type MetaFields = Record<string, MetaField[]>;

function metaFieldsFromConfig(cfg: unknown): MetaFields {
  const raw = (cfg as { metaFields?: Record<string, unknown> })?.metaFields ?? {};
  const out: MetaFields = {};
  for (const [entity, fields] of Object.entries(raw)) {
    if (!Array.isArray(fields)) continue;
    out[entity] = fields.filter(
      (f): f is MetaField =>
        !!f && typeof f === "object" && typeof (f as MetaField).key === "string",
    );
  }
  return out;
}

/** The marketplace's own terms (`tenancy`): whether a tenant must be verified to
 *  trade, and what the platform takes. Both were declared and shown nowhere. */
export type TenancyTerms = {
  selfOnboarding: boolean;
  verification: { required: boolean; credentials: string[] };
  commission: { enabled: boolean; rateBps: number; chargedOn: string };
};

function tenancyTermsFromConfig(cfg: unknown): TenancyTerms {
  const t =
    (cfg as {
      tenancy?: {
        selfOnboarding?: boolean;
        tenantVerification?: { required?: boolean; credentials?: unknown };
        commission?: { enabled?: boolean; rateBps?: number; chargedOn?: string };
      };
    })?.tenancy ?? {};
  const creds = t.tenantVerification?.credentials;
  return {
    selfOnboarding: t.selfOnboarding !== false,
    verification: {
      required: !!t.tenantVerification?.required,
      credentials: Array.isArray(creds) ? creds.filter((c): c is string => typeof c === "string") : [],
    },
    commission: {
      enabled: !!t.commission?.enabled,
      rateBps: Number(t.commission?.rateBps ?? 0),
      chargedOn: t.commission?.chargedOn ?? "completion",
    },
  };
}

/** Everything `AppProvider` needs from the pivot file, in ONE request. Boot used
 *  to call `/config` for tenancy alone; this keeps the round-trip count the same
 *  while also picking up the location and vocabulary blocks. */
export type PivotConfig = {
  tenancy: Tenancy;
  tenancyTerms: TenancyTerms;
  location: LocationConfig;
  capabilities: Capabilities;
  terms: ConfigTerms;
  copy: ConfigCopy;
  /** Declared domain fields per entity, so a form can render them. */
  metaFields: MetaFields;
  /** `discovery.facets` — which search dimensions this deployment offers. */
  facets: SearchFacets;
  /** `pricing.currency` — the deployment's default currency, so a first offer
   *  on an empty catalogue isn't created under a hardcoded fallback. */
  currency: string;
};

/** The all-fallbacks value used when `/config` is unreachable. Boot must not hang
 *  on the pivot file, and each caller was inlining its own copy of this. */
export const FALLBACK_PIVOT_CONFIG: PivotConfig = {
  tenancy: { mode: "multi", providerCode: null },
  tenancyTerms: {
    selfOnboarding: true,
    verification: { required: false, credentials: [] },
    commission: { enabled: false, rateBps: 0, chargedOn: "completion" },
  },
  metaFields: {},
  facets: DEFAULT_FACETS,
  location: { origin: null, distanceUnit: "km", timezone: "UTC" },
  // /config unreachable: leave every capability ON. The backend is still the
  // authority and refuses anything actually disabled.
  capabilities: {},
  // No terms/copy -> the static vertical's vocabulary, i.e. exactly the
  // pre-pivot behaviour.
  terms: {},
  copy: {},
  currency: "EUR",
};

/** The pure half of `getPivotConfig` — a raw `/config` payload in, the parsed
 *  shape out, no transport. Split out so `scripts/check_pivot_frontend.mts` can
 *  run every `pivots/*.json` through the SAME parsers the app uses, rather than
 *  a reimplementation that could drift from them. */
export function parsePivotConfig(cfg: unknown): PivotConfig {
  return {
    tenancy: tenancyFromConfig(cfg),
    location: locationFromConfig(cfg),
    tenancyTerms: tenancyTermsFromConfig(cfg),
    capabilities: capabilitiesFromConfig(cfg),
    terms: stringsOnly<keyof ConfigTerms>((cfg as { terms?: unknown })?.terms),
    copy: stringsOnly<keyof ConfigCopy>((cfg as { copy?: unknown })?.copy),
    metaFields: metaFieldsFromConfig(cfg),
    facets: facetsFromConfig(cfg),
    currency: currencyFromConfig(cfg),
  };
}

function currencyFromConfig(cfg: unknown): string {
  const c = (cfg as { pricing?: { currency?: unknown } })?.pricing?.currency;
  return typeof c === "string" && c.length === 3 ? c : FALLBACK_PIVOT_CONFIG.currency;
}

export async function getPivotConfig(): Promise<PivotConfig> {
  return parsePivotConfig(await request<unknown>("/config"));
}

/** Price a selection WITHOUT booking it, through the engine that will charge.
 *
 *  The confirm screen used to compute `priceMinorUnits * slots * party`, which
 *  is only the default pricing block's formula. On a tiered escape room that
 *  showed 45000 and charged 12000. Anything that displays a total must come
 *  from here. Throws the same ApiError an unbookable selection would raise. */
export function getQuote(q: {
  serviceId: ID;
  resourceId: ID;
  slotIds: ID[];
  partySize: number;
} & BookingShape): Promise<Quote> {
  return post("/bookings/quote", {
    serviceId: q.serviceId,
    resourceId: q.resourceId,
    slotIds: q.slotIds,
    partySize: q.partySize,
    // Priced, not just recorded: bands weight the head count, options add
    // lines, and a `subjectField` tier matches on the subject.
    partyBands: q.partyBands,
    options: q.options,
    subject: q.subject,
  }) as Promise<Quote>;
}

/** What this deployment sells as memberships/passes, and what the user holds.
 *  Returns an empty catalogue (not an error) when `entitlements` is off, so the
 *  caller hides the surface on `plans.length` without special-casing. */
export function getMyEntitlements(): Promise<{
  enabled: boolean;
  kind: string;
  plans: EntitlementPlan[];
  held: HeldEntitlement[];
  active: HeldEntitlement | null;
}> {
  return request("/me/entitlements");
}

/** Owner marks a loaned item handed back (`inventory.returnRequired`). Owner-only
 *  on the server: a customer able to self-certify could clear their own fee. */
export function markReturned(bookingId: ID): Promise<Booking> {
  return post(`/bookings/${bookingId}/return`, undefined) as Promise<Booking>;
}

/** Take a place in the queue for a full slot (`timing.waitlist`). Refused by the
 *  server when the slot still has room — booking it is strictly better. The
 *  party travels with the entry so a promotion books the seats actually needed. */
export function joinWaitlist(slotId: ID, partySize = 1): Promise<WaitlistEntry> {
  return post(`/slots/${slotId}/waitlist${qs({ party_size: partySize })}`, undefined) as Promise<WaitlistEntry>;
}

/** Owner records a blocking prerequisite as satisfied. */
export function satisfyPrerequisite(bookingId: ID, key: string): Promise<Booking> {
  return post(`/bookings/${bookingId}/prerequisites/${key}`, undefined) as Promise<Booking>;
}

/** Owner records money received. Omit `amount` to settle the outstanding balance. */
export function recordPayment(bookingId: ID, amount?: number): Promise<Booking> {
  return post(`/bookings/${bookingId}/pay${amount === undefined ? "" : `?amount=${amount}`}`, undefined) as Promise<Booking>;
}

// --- discovery -------------------------------------------------------------

export function searchProviders(q: {
  text?: string;
  categoryId?: string;
  near?: string;
}): Promise<Provider[]> {
  return request(`/providers${qs({ text: q.text, category_id: q.categoryId, near: q.near })}`);
}

export function getProvider(id: ID): Promise<Provider> {
  return request(`/providers/${id}`);
}

export function getProviderByCode(code: string): Promise<Provider> {
  return request(`/providers/by-code/${encodeURIComponent(code)}`);
}

export function followProvider(id: ID): Promise<User> {
  return post(`/providers/${id}/follow`) as Promise<User>;
}

export function unfollowProvider(id: ID): Promise<User> {
  return post(`/providers/${id}/unfollow`) as Promise<User>;
}

// --- services & resources --------------------------------------------------

export function getServices(providerId: ID): Promise<Service[]> {
  return request(`/services${qs({ provider_id: providerId })}`);
}

export function getService(id: ID): Promise<Service> {
  return request(`/services/${id}`);
}

export function getResources(serviceId: ID): Promise<Resource[]> {
  return request(`/resources${qs({ service_id: serviceId })}`);
}

// --- availability ----------------------------------------------------------

export function getAvailability(q: {
  serviceId: ID;
  resourceId?: ID;
  fromUtc: IsoUtc;
  toUtc: IsoUtc;
}): Promise<DayAvailability[]> {
  return request(
    `/availability${qs({ service_id: q.serviceId, resource_id: q.resourceId, from: q.fromUtc, to: q.toUtc })}`,
  );
}

export function getMonthDensity(q: {
  serviceId: ID;
  resourceId?: ID;
  month: string; // 'YYYY-MM'
}): Promise<MonthDensityCell[]> {
  return request(
    `/month-density${qs({ service_id: q.serviceId, resource_id: q.resourceId, month: q.month })}`,
  );
}

// --- bookings --------------------------------------------------------------

/** The parts of a booking the CONFIG decides whether to ask for at all.
 *  Sent identically by the quote and the create, because the price the customer
 *  sees has to be the price for the thing they are actually booking. */
export type BookingShape = {
  /** `booking.party.composition` — heads per band ({adult: 2, child: 1}). Must
   *  add up to `partySize`; the server weights them by `priceFactor`. */
  partyBands?: Record<string, number>;
  /** `booking.options` — {optionKey: true | "choiceKey"}. Prices are resolved
   *  server-side; a key or choice the config never declared is rejected. */
  options?: Record<string, string | boolean>;
  /** `booking.subject` — the pet/vehicle/child the booking is about. */
  subject?: Record<string, unknown>;
};

export function createBooking(input: {
  serviceId: ID;
  resourceId: ID;
  slotIds: ID[];
  partySize: number;
  /** Optional repeat (`recurrence`). `count` INCLUDES this booking, and the
   *  server clamps it to `recurrence.maxOccurrences` — the client never sets
   *  the ceiling. Later occurrences are best-effort and the response's
   *  `series.skipped` names any that could not be booked. */
  repeat?: { pattern: string; count: number };
  /** `metaFields.bookings` — domain fields the deployment declares. Merged
   *  UNDER the engine's own keys server-side, so a domain field can never
   *  rewrite a price. */
  metadata?: Record<string, unknown>;
} & BookingShape): Promise<Booking> {
  return post("/bookings", input) as Promise<Booking>;
}

export function getBookings(scope: "upcoming" | "past" | "all"): Promise<Booking[]> {
  return request(`/bookings${qs({ scope })}`);
}

export function getBooking(id: ID): Promise<Booking> {
  return request(`/bookings/${id}`);
}

export function rescheduleBooking(id: ID, newSlotIds: ID[]): Promise<Booking> {
  return post(`/bookings/${id}/reschedule`, { newSlotIds }) as Promise<Booking>;
}

export function cancelBooking(id: ID): Promise<Booking> {
  return post(`/bookings/${id}/cancel`) as Promise<Booking>;
}

export function leaveReview(id: ID, rating: number, text: string): Promise<Booking> {
  return post(`/bookings/${id}/review`, { rating, text }) as Promise<Booking>;
}

// --- messaging -------------------------------------------------------------
// The durable send/read/delete/list path; live delivery rides Supabase Realtime
// (see hooks/use-conversation-realtime). Identity is derived from the token.

/** The current user's conversations, most-recent first, enriched with the other
 *  party and an unread count. */
export function getConversations(): Promise<Conversation[]> {
  return request("/conversations");
}

/** A single thread with its other party + unread count (for the thread header). */
export function getConversation(id: ID): Promise<Conversation> {
  return request(`/conversations/${id}`);
}

/** Ordered messages in a thread (404s a non-participant via RLS). */
export function getMessages(id: ID): Promise<Message[]> {
  return request(`/conversations/${id}/messages`);
}

/** Send a message; the server stamps sender + delivered_at. Returns the row. */
export function sendMessage(id: ID, body: string, replyToId?: ID): Promise<Message> {
  return post(`/conversations/${id}/messages`, { body, replyToId }) as Promise<Message>;
}

/** Mark the other party's unread messages in this thread as read. */
export function markConversationRead(id: ID): Promise<{ conversationId: ID; readCount: number }> {
  return post(`/conversations/${id}/read`) as Promise<{ conversationId: ID; readCount: number }>;
}

/** Soft-delete one of the caller's own messages. Returns the updated (blanked) row. */
export function deleteMessage(id: ID, messageId: ID): Promise<Message> {
  return del(`/conversations/${id}/messages/${messageId}`) as Promise<Message>;
}

/** Find-or-create a thread with a provider. Client path: pass just `providerId`
 *  ("message this business"). Owner path: also pass the customer's `clientId`
 *  ("message this customer") — the caller must own the provider. */
export function startConversation(providerId: ID, clientId?: ID): Promise<Conversation> {
  return post("/conversations", { providerId, clientId }) as Promise<Conversation>;
}

// --- account ---------------------------------------------------------------

export function getCurrentUser(): Promise<User> {
  return request("/me");
}

export function updateUser(patch: Partial<User>): Promise<User> {
  return request("/me", { method: "PATCH", body: JSON.stringify(patch) });
}

export function uploadAvatar(file: File): Promise<User> {
  const form = new FormData();
  form.append("file", file);
  return requestForm<User>("/me/avatar", "POST", form);
}

export function deleteAvatar(): Promise<User> {
  return del("/me/avatar") as Promise<User>;
}

/** GDPR erasure — permanently delete the signed-in user's account and all their
 *  data. The caller should sign out and redirect afterwards. */
export function deleteAccount(): Promise<void> {
  return del("/me") as Promise<void>;
}

/** The signed-in customer's reputation as businesses see it (score + reviews
 *  providers left after completed bookings). */
export function getMyReputation(): Promise<ClientReputation> {
  return request("/me/reputation");
}

/** The currently-seeded vertical, so the app picks the matching base
 *  vocabulary at boot (the pivot config's `terms`/`copy` overlay on top). */
export async function getActiveVertical(): Promise<VerticalId> {
  const { verticalId } = await request<{ verticalId: VerticalId }>("/vertical");
  return verticalId;
}

// --- owner (admin) ---------------------------------------------------------
// Owner-gated writes; the backend stamps ownership from the token and RLS
// enforces it. Bodies are camelCase (the backend accepts them via CamelModel).

export function getMyProviders(): Promise<Provider[]> {
  return request("/providers/mine");
}

// --- business-mode aggregation (the five owner tabs) -----------------------

/** Dashboard: badge provider, the three glanceable numbers, this week's
 *  bookings, and the top pending requests — all scoped to the owner's own
 *  providers, aggregated server-side (/owner/dashboard). */
export function getOwnerDashboard(): Promise<OwnerDashboard> {
  return request("/owner/dashboard");
}

/** Services tab: each owned service with glanceable stats. */
export function getOwnerServices(): Promise<OwnerServiceSummary[]> {
  return request("/owner/services");
}

/** Requests tab: pending requests across the owner's providers, each with a
 *  client screening card. */
export function getOwnerRequests(): Promise<OwnerRequest[]> {
  return request("/owner/requests");
}

/** Calendar tab: confirmed/completed bookings in a window (defaults to the
 *  current month), sorted by start. */
export function getOwnerCalendar(q?: { fromUtc?: IsoUtc; toUtc?: IsoUtc }): Promise<OwnerBooking[]> {
  return request(`/owner/calendar${qs({ from: q?.fromUtc, to: q?.toUtc })}`);
}

/** Owner approves a pending request → confirmed (capacity re-checked). */
export function approveBooking(id: ID): Promise<Booking> {
  return post(`/bookings/${id}/approve`) as Promise<Booking>;
}

/** Owner declines a pending request → rejected. */
export function rejectBooking(id: ID): Promise<Booking> {
  return post(`/bookings/${id}/reject`) as Promise<Booking>;
}

/** Owner rates the customer after a completed booking (feeds their reputation). */
export function rateClient(
  bookingId: ID,
  rating: number,
  text = "",
): Promise<{ rating: number; text: string; createdAtUtc: IsoUtc | null }> {
  return post(`/bookings/${bookingId}/client-review`, { rating, text }) as Promise<{
    rating: number;
    text: string;
    createdAtUtc: IsoUtc | null;
  }>;
}

/** Recent public reviews for a provider (Profile tab). */
export function getProviderReviews(id: ID, limit = 8): Promise<ProviderReview[]> {
  return request(`/providers/${id}/reviews${qs({ limit })}`);
}

/** Upload/replace a business's avatar image; returns the updated Provider. */
export function uploadProviderAvatar(id: ID, file: File): Promise<Provider> {
  const form = new FormData();
  form.append("file", file);
  return requestForm<Provider>(`/providers/${id}/avatar`, "POST", form);
}

export function deleteProviderAvatar(id: ID): Promise<Provider> {
  return del(`/providers/${id}/avatar`) as Promise<Provider>;
}

/** Create the business itself (owner). Until this existed the console could
 *  create a service but not the provider that owns one, so a new owner's only
 *  route to a business was the seed. `providerCode` is what single-tenant
 *  deployments resolve their sole business by, so it is worth setting. */
export function createProvider(input: {
  name: string;
  publicCode?: string;
  categoryId?: string;
  tagline?: string;
  bio?: string;
  location?: { city: string; country: string; lat: number; lng: number };
}): Promise<Provider> {
  return post("/providers", input) as Promise<Provider>;
}

/** Create a bookable unit under a service (owner).
 *
 *  `serviceId`, `capacity`, `active` and `attributes` ride in `metadata`: the
 *  base tables are frozen, so everything but name/description lives there.
 *  Callers pass them flat and this assembles the shape the API expects. */
export function createResource(input: {
  serviceId: ID;
  name: string;
  description?: string;
  capacity: number;
  attributes?: { label: string; value: string }[];
}): Promise<Resource> {
  return post("/resources", {
    name: input.name,
    description: input.description,
    metadata: {
      service_id: input.serviceId,
      capacity: input.capacity,
      active: true,
      attributes: input.attributes ?? [],
    },
  }) as Promise<Resource>;
}

/** Open one slot on a resource (owner). `endsAt` defaults server-side to the
 *  service's `slotDurationMinutes`, and `capacity` to the resource's own, so
 *  the caller only has to say when. */
export function createSlot(input: {
  resourceId: ID;
  startsAt: IsoUtc;
  endsAt?: IsoUtc;
  capacity?: number;
}): Promise<Slot> {
  return post("/slots", input) as Promise<Slot>;
}

/** Open a run of slots back-to-back — what "add a day of availability" means.
 *
 *  Issued sequentially, not in parallel: `slot.create` enforces
 *  `timing.bufferMinutes` against the slots that already exist, so two
 *  concurrent creates can both pass a check the pair then violates. Returns
 *  what was opened and what the engine refused, rather than failing the batch —
 *  a run that collides with existing availability should still open the rest.
 */
export async function createSlotRun(input: {
  resourceId: ID;
  startsAt: IsoUtc;
  durationMinutes: number;
  count: number;
  capacity?: number;
}): Promise<{ created: Slot[]; rejected: { startsAt: IsoUtc; message: string }[] }> {
  const created: Slot[] = [];
  const rejected: { startsAt: IsoUtc; message: string }[] = [];
  let cursor = new Date(input.startsAt).getTime();
  for (let i = 0; i < input.count; i++) {
    const startsAt = new Date(cursor).toISOString();
    const endsAt = new Date(cursor + input.durationMinutes * 60_000).toISOString();
    try {
      created.push(await createSlot({ resourceId: input.resourceId, startsAt, endsAt, capacity: input.capacity }));
    } catch (e) {
      rejected.push({ startsAt, message: e instanceof ApiError ? e.message : "Could not open that time." });
    }
    cursor += input.durationMinutes * 60_000;
  }
  return { created, rejected };
}

export function deleteResource(id: ID): Promise<void> {
  return del(`/resources/${id}`) as Promise<void>;
}

export function createService(input: {
  providerId: ID;
  name: string;
  description?: string;
  bookingModel: "unit_selection" | "one_to_one" | "shared_capacity";
  slotDurationMinutes: number;
  minSlotsPerBooking: number;
  maxSlotsPerBooking: number;
  priceMinorUnits: number;
  currency: string;
  cancellationCutoffHours: number;
  autoApprove?: boolean;
  /** `metaFields.services` — the deployment's own declared fields, validated
   *  server-side against the same descriptors the form is built from. */
  metadata?: Record<string, unknown>;
}): Promise<Service> {
  return post("/services", input) as Promise<Service>;
}

/** Partial update of a service's editable fields (name + per-service rules). */
export function updateService(
  id: ID,
  patchBody: Partial<{
    name: string;
    description: string;
    slotDurationMinutes: number;
    maxSlotsPerBooking: number;
    priceMinorUnits: number;
    cancellationCutoffHours: number;
    autoApprove: boolean;
    metadata: Record<string, unknown>;
  }>,
): Promise<Service> {
  return patch(`/services/${id}`, patchBody) as Promise<Service>;
}

export function deleteService(id: ID): Promise<void> {
  return del(`/services/${id}`) as Promise<void>;
}

// --- dev convenience -------------------------------------------------------
// Makes the seams pokeable from the browser console. Dev only; harmless in prod.
if (typeof window !== "undefined") {
  (window as unknown as { codaro?: unknown }).codaro = {
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
    uploadAvatar,
    deleteAvatar,
    deleteAccount,
    getActiveVertical,
  };
}
