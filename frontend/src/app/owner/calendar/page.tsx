"use client";

/**
 * Business tab 4 — Calendar. Every approved booking laid out across the three
 * standard views (month / week / day, week by default). Tapping a booking opens
 * it for detail and management. Bookings are demo-generated (deterministic per
 * business) until the backend exposes an owner-wide bookings feed.
 */
import { useMemo, useState } from "react";
import { CalendarX2, Clock, Users } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { Modal } from "@/components/modal";
import { Button } from "@/components/ui/button";
import { BookingCalendar } from "@/components/business/booking-calendar";
import { demoBookings, type DemoBooking } from "@/lib/business-demo";
import { formatBookingWhen, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const browserTz = () =>
  typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";

const STATUS_CLASS: Record<DemoBooking["status"], string> = {
  confirmed: "bg-primary/10 text-primary",
  completed: "bg-muted text-muted-foreground",
  pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export default function CalendarPage() {
  const { ready, useCase, seed } = useOwner();
  const tz = browserTz();
  const bookings = useMemo(() => demoBookings(useCase, seed, tz), [useCase, seed, tz]);
  const [selected, setSelected] = useState<DemoBooking | null>(null);
  const [cancelled, setCancelled] = useState<Set<string>>(new Set());

  if (!ready) return <Skeleton className="h-96 w-full" />;

  const shown = bookings.map((b) =>
    cancelled.has(b.id) ? { ...b, status: "completed" as const } : b,
  );

  return (
    <section className="space-y-4 py-2">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Calendar</h1>
        <p className="text-sm text-muted-foreground">Your confirmed bookings across every offer.</p>
      </div>

      <BookingCalendar bookings={shown} timezone={tz} defaultView="week" onOpen={setSelected} />

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Booking">
        {selected ? (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">{selected.title}</h3>
                <p className="text-sm text-muted-foreground">{selected.client}</p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-1 text-xs font-medium capitalize",
                  STATUS_CLASS[cancelled.has(selected.id) ? "completed" : selected.status],
                )}
              >
                {cancelled.has(selected.id) ? "cancelled" : selected.status}
              </span>
            </div>

            <dl className="space-y-2 text-sm">
              <Row icon={<Clock className="size-4" aria-hidden />}>
                {formatBookingWhen(selected.startUtc, selected.endUtc, browserTz())}
              </Row>
              {useCase.partyNoun && selected.partySize > 1 ? (
                <Row icon={<Users className="size-4" aria-hidden />}>
                  {selected.partySize} {useCase.partyNoun}
                </Row>
              ) : null}
              <Row icon={<span className="grid size-4 place-items-center text-xs">€</span>}>
                {formatMoney(selected.priceMinorUnits, selected.currency)} total
              </Row>
            </dl>

            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              <Button size="sm" variant="outline" isDisabled>
                Message client
              </Button>
              <Button size="sm" variant="outline" isDisabled>
                Reschedule
              </Button>
              <Button
                size="sm"
                variant="destructive"
                isDisabled={cancelled.has(selected.id)}
                onPress={() => {
                  setCancelled((prev) => new Set(prev).add(selected.id));
                  setSelected(null);
                }}
              >
                Cancel booking
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Messaging and reschedule land when the backend booking feed is wired in.
            </p>
          </div>
        ) : null}
      </Modal>

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <CalendarX2 className="size-3.5" aria-hidden />
        Demo bookings — the live owner-wide feed is coming from the backend.
      </p>
    </section>
  );
}

function Row({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <span>{children}</span>
    </div>
  );
}
