const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** Thrown for any non-2xx response. `detail` carries the backend's own message
 *  (FastAPI's HTTPException detail) so rule violations from `app/rules.py`
 *  -- "This slot is fully booked", "Cannot cancel within 24h" -- reach the UI
 *  verbatim instead of being flattened into a bare status code. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    // The body is usually {"detail": "..."}, but a proxy/500 can return HTML --
    // fall back to the status line rather than throwing inside the error path.
    let detail = `${init?.method ?? "GET"} ${path} failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON body -- keep the fallback */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export type Resource = { id: string; name: string; description?: string; metadata: Record<string, unknown> };
export type Slot = { id: string; resource_id: string; starts_at: string; ends_at: string; capacity: number };
// Shape of the `slot_occupancy` SQL view (supabase/schema.sql) -- keyed by
// slot_id, not id, since it's a view over slots joined with bookings.
export type SlotOccupancy = {
  slot_id: string;
  resource_id: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  booked_count: number;
  available_count: number;
};
export type Booking = {
  id: string;
  slot_id: string;
  client_email: string;
  status: "confirmed" | "cancelled" | "rescheduled";
  history: Array<{ status: string; at: string }>;
};
// Owner analytics, computed by the backend from slot_occupancy + bookings
// (GET /resources/{id}/analytics). bookings_by_status is aggregated from the
// rows, so its keys follow whatever statuses actually exist -- never hardcoded.
export type ResourceAnalytics = {
  total_slots: number;
  total_capacity: number;
  booked_count: number;
  available_count: number;
  occupancy_rate: number;
  bookings_by_status: Record<string, number>;
};

export const api = {
  listResources: () => request<Resource[]>("/resources"),
  createResource: (payload: Partial<Resource>) =>
    request<Resource[]>("/resources", { method: "POST", body: JSON.stringify(payload) }),
  updateResource: (id: string, patch: Partial<Resource>) =>
    request<Resource[]>(`/resources/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  resourceAnalytics: (id: string) => request<ResourceAnalytics>(`/resources/${id}/analytics`),

  listSlots: (resourceId?: string) =>
    request<Slot[]>(`/slots${resourceId ? `?resource_id=${resourceId}` : ""}`),
  slotOccupancy: (resourceId?: string) =>
    request<SlotOccupancy[]>(`/slots/occupancy${resourceId ? `?resource_id=${resourceId}` : ""}`),
  // ends_at is derived server-side from rules.slotDurationMinutes when omitted,
  // and capacity defaults from rules.maxBookingsPerSlot -- no magic numbers here.
  createSlot: (payload: {
    resource_id: string;
    starts_at: string;
    ends_at?: string;
    capacity?: number;
    metadata?: Record<string, unknown>;
  }) => request<Slot[]>("/slots", { method: "POST", body: JSON.stringify(payload) }),

  listBookings: (clientEmail?: string) =>
    request<Booking[]>(`/bookings${clientEmail ? `?client_email=${clientEmail}` : ""}`),
  createBooking: (payload: { slot_id: string; client_email: string }) =>
    request<Booking[]>("/bookings", { method: "POST", body: JSON.stringify(payload) }),
  cancelBooking: (id: string) => request<Booking[]>(`/bookings/${id}/cancel`, { method: "POST" }),
  rescheduleBooking: (id: string, newSlotId: string) =>
    request<Booking[]>(`/bookings/${id}/reschedule`, {
      method: "POST",
      body: JSON.stringify({ new_slot_id: newSlotId }),
    }),
};
