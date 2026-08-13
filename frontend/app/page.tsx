"use client";

import { useEffect, useState } from "react";
import { Term, useDomain } from "@/lib/domain";
import { api, type SlotOccupancy } from "@/lib/api";

export default function LandingPage() {
  const { copy } = useDomain();
  const [slots, setSlots] = useState<SlotOccupancy[]>([]);

  useEffect(() => {
    api.slotOccupancy().then(setSlots).catch(console.error);
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">{copy.landingTitle}</h1>
      <p className="text-muted-foreground">{copy.landingSubtitle}</p>

      <section className="mt-8">
        <h2 className="text-lg font-medium">
          <Term term="slot" plural /> availability
        </h2>
        {slots.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">{copy.emptyStateSlots}</p>
        ) : (
          <ul className="mt-2 space-y-1">
            {slots.map((s) => (
              <li key={s.slot_id} className="text-sm">
                {s.starts_at} — {s.available_count}/{s.capacity} open
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* TODO: customer dashboard (book/reschedule/cancel) and owner
          dashboard (resource/slot CRUD, confirm/cancel bookings,
          analytics) are separate views — not built yet. */}
    </main>
  );
}
