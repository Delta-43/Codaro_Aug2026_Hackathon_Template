const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
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

export const api = {
  listResources: () => request<Resource[]>("/resources"),
  createResource: (payload: Partial<Resource>) =>
    request<Resource[]>("/resources", { method: "POST", body: JSON.stringify(payload) }),

  listSlots: (resourceId?: string) =>
    request<Slot[]>(`/slots${resourceId ? `?resource_id=${resourceId}` : ""}`),
  slotOccupancy: (resourceId?: string) =>
    request<SlotOccupancy[]>(`/slots/occupancy${resourceId ? `?resource_id=${resourceId}` : ""}`),

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
