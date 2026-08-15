"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Term, useDomain } from "@/lib/domain";
import { ApiError, api, type Booking, type Resource, type Slot, type SlotOccupancy } from "@/lib/api";
import { clearClientEmail, getClientEmail } from "@/lib/session";
import { formatSlotTime, hoursUntil } from "@/lib/format";

export default function CustomerDashboard() {
  const { copy, rules } = useDomain();
  const router = useRouter();

  const [email, setEmail] = useState<string | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [occupancy, setOccupancy] = useState<SlotOccupancy[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // `slots` is loaded alongside `occupancy` because a booking only carries a
  // slot_id -- and once a slot is full it drops out of the "available" set, so
  // occupancy alone can't label the user's own bookings.
  const reload = useCallback(async (who: string) => {
    const [r, s, o, b] = await Promise.all([
      api.listResources(),
      api.listSlots(),
      api.slotOccupancy(),
      api.listBookings(who)
    ]);
    setResources(r);
    setSlots(s);
    setOccupancy(o);
    setBookings(b);
  }, []);

  useEffect(() => {
    const who = getClientEmail();
    if (!who) {
      router.replace("/");
      return;
    }
    setEmail(who);
    reload(who)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [reload, router]);

  async function act(id: string, fn: () => Promise<unknown>, successMessage: string) {
    if (!email) return;
    setBusyId(id);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await reload(email);
      setNotice(successMessage);
    } catch (e) {
      // ApiError.detail is the backend's own rule message, e.g.
      // "Cannot cancel/reschedule within 24h of the slot start."
      setError(e instanceof ApiError ? e.detail : (e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  const resourceName = (id: string) => resources.find((r) => r.id === id)?.name ?? "Unknown";
  const slotById = (id: string) => slots.find((s) => s.id === id);

  const activeBookings = bookings.filter((b) => b.status !== "cancelled");
  const bookedSlotIds = new Set(activeBookings.map((b) => b.slot_id));

  // Only offer slots that have room and that this visitor hasn't already taken.
  const available = occupancy
    .filter((s) => s.available_count > 0 && !bookedSlotIds.has(s.slot_id))
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));

  const cancelWindow = rules.cancellationWindowHours;

  if (loading) return <main className="mx-auto max-w-3xl p-8 text-sm text-gray-500">Loading...</main>;

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">
          <Term term="client" /> dashboard
        </h1>
        <p className="text-sm text-gray-500">
          {email}{" "}
          <button
            onClick={() => {
              clearClientEmail();
              router.push("/");
            }}
            className="ml-2 underline hover:text-gray-800"
          >
            switch
          </button>
        </p>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p className="mt-4 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
          {notice}
        </p>
      )}

      <section className="mt-8">
        <h2 className="text-lg font-medium">
          Your <Term term="booking" plural />
        </h2>
        {activeBookings.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">{copy.emptyStateBookings}</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {activeBookings.map((b) => {
              const slot = slotById(b.slot_id);
              const locked = slot ? hoursUntil(slot.starts_at) < cancelWindow : false;
              const busy = busyId === b.id;
              return (
                <li key={b.id} className="rounded border border-gray-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{slot ? resourceName(slot.resource_id) : "Unknown"}</p>
                      <p className="text-sm text-gray-600">
                        {slot ? formatSlotTime(slot.starts_at, slot.ends_at) : b.slot_id}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-gray-500">{b.status}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        aria-label="Reschedule to"
                        defaultValue=""
                        disabled={busy || locked || available.length === 0}
                        onChange={(e) => {
                          const newSlotId = e.target.value;
                          e.target.value = "";
                          if (newSlotId) {
                            act(b.id, () => api.rescheduleBooking(b.id, newSlotId), "Rescheduled.");
                          }
                        }}
                        className="rounded border border-gray-300 px-2 py-1.5 text-sm disabled:opacity-50"
                      >
                        <option value="">Reschedule to...</option>
                        {available.map((s) => (
                          <option key={s.slot_id} value={s.slot_id}>
                            {resourceName(s.resource_id)} - {formatSlotTime(s.starts_at, s.ends_at)}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => act(b.id, () => api.cancelBooking(b.id), "Cancelled.")}
                        disabled={busy || locked}
                        className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                      >
                        {busy ? "..." : "Cancel"}
                      </button>
                    </div>
                  </div>
                  {locked && (
                    <p className="mt-2 text-xs text-gray-500">
                      Locked: starts within {cancelWindow}h, the cancellation window has closed.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-medium">
          Available <Term term="slot" plural />
        </h2>
        {available.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">{copy.emptyStateSlots}</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {available.map((s) => {
              const busy = busyId === s.slot_id;
              return (
                <li
                  key={s.slot_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded border border-gray-200 p-4"
                >
                  <div>
                    <p className="font-medium">{resourceName(s.resource_id)}</p>
                    <p className="text-sm text-gray-600">{formatSlotTime(s.starts_at, s.ends_at)}</p>
                    <p className="mt-1 text-xs text-gray-500">
                      {s.available_count}/{s.capacity} open
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      act(
                        s.slot_id,
                        () => api.createBooking({ slot_id: s.slot_id, client_email: email! }),
                        copy.confirmTitle
                      )
                    }
                    disabled={busy}
                    className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {busy ? "..." : "Book"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
