/**
 * ============================================================================
 * THE API SEAM — now real HTTP to the FastAPI backend.
 * ============================================================================
 *
 * Every component/hook/page goes through these functions; none touch transport
 * details. Each returns the exact domain shape from @/types/domain and throws
 * `ApiError` with the backend's code, so the UI's error handling (inline "slot
 * was just taken", disabled-with-reason, retry) is unchanged from the mock era.
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
  Resource,
  Service,
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
    if (d && typeof d === "object") {
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

/** Which search facets the current catalog supports — derived server-side from
 *  the seeded data (`GET /config` → `search.facets`), so the filter UI pivots
 *  automatically. Defaults to all-on if the field is absent (older backend). */
export type SearchFacets = { price: boolean; distance: boolean; rating: boolean };

export async function getSearchFacets(): Promise<SearchFacets> {
  const cfg = await request<{ search?: { facets?: Partial<SearchFacets> } }>("/config");
  const f = cfg.search?.facets ?? {};
  return { price: f.price ?? true, distance: f.distance ?? true, rating: f.rating ?? true };
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

/** Everything `AppProvider` needs from the pivot file, in ONE request. Boot used
 *  to call `/config` for tenancy alone; this keeps the round-trip count the same
 *  while also picking up the location block. */
export type PivotConfig = {
  tenancy: Tenancy;
  location: LocationConfig;
  capabilities: Capabilities;
};

export async function getPivotConfig(): Promise<PivotConfig> {
  const cfg = await request<unknown>("/config");
  return {
    tenancy: tenancyFromConfig(cfg),
    location: locationFromConfig(cfg),
    capabilities: capabilitiesFromConfig(cfg),
  };
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

export function createBooking(input: {
  serviceId: ID;
  resourceId: ID;
  slotIds: ID[];
  partySize: number;
}): Promise<Booking> {
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

// --- account & demo --------------------------------------------------------

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

export async function getActiveVertical(): Promise<VerticalId> {
  const { verticalId } = await request<{ verticalId: VerticalId }>("/demo/vertical");
  return verticalId;
}

export async function setVertical(id: VerticalId): Promise<void> {
  await post("/demo/vertical", { id });
}

export async function resetDemoData(): Promise<void> {
  await post("/demo/reset");
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
    setVertical,
    resetDemoData,
  };
}
