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
import { ApiError, type ApiErrorCode } from "@/api/errors";
import { getAccessToken } from "@/lib/auth";

export { ApiError, isApiError } from "@/api/errors";
export type { ApiErrorCode } from "@/api/errors";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
    res = await fetch(`${BASE}${path}`, {
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

const post = (path: string, body?: unknown) =>
  request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

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

// --- account & demo --------------------------------------------------------

export function getCurrentUser(): Promise<User> {
  return request("/me");
}

export function updateUser(patch: Partial<User>): Promise<User> {
  return request("/me", { method: "PATCH", body: JSON.stringify(patch) });
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

/** Owner analytics for one resource, computed server-side from occupancy +
 *  bookings (snake_case — it's an aggregate, not a domain entity). */
export type ResourceAnalytics = {
  total_slots: number;
  total_capacity: number;
  booked_count: number;
  available_count: number;
  occupancy_rate: number;
  bookings_by_status: Record<string, number>;
};

export function getResourceAnalytics(id: ID): Promise<ResourceAnalytics> {
  return request(`/resources/${id}/analytics`);
}

/** Bookings on one of the owner's resources — the standard Booking plus the
 *  client email (owner-only). */
export type OwnerBooking = Booking & { clientEmail?: string };

export function getResourceBookings(id: ID): Promise<OwnerBooking[]> {
  return request(`/resources/${id}/bookings`);
}

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
}): Promise<Service> {
  return post("/services", input) as Promise<Service>;
}

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

/** Create one slot. `startsAt` is UTC ISO; the backend derives `ends_at` from
 *  the service's slot duration and defaults capacity from the resource. */
export function createSlot(input: {
  resourceId: ID;
  startsAt: IsoUtc;
  capacity?: number;
}): Promise<unknown> {
  return post("/slots", {
    resource_id: input.resourceId,
    starts_at: input.startsAt,
    capacity: input.capacity,
  });
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
    getActiveVertical,
    setVertical,
    resetDemoData,
  };
}
