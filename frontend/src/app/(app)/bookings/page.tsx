"use client";

/**
 * Tab 4 — Bookings. Calendar + list merged into one panel: a month / week / day
 * calendar of the customer's own bookings on top (the counterparty is the
 * business, so it reads as "who I'm booked with"), then the Upcoming / Past
 * segmented list below. Both are backed by getBookings; tapping a calendar entry
 * deep-links to the booking detail where reschedule / cancel / review live. The
 * inbox that used to live here now has its own permanent Messaging tab.
 */
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Ticket } from "lucide-react";
import type { Booking } from "@/types/domain";
import type { DemoBooking } from "@/lib/business-demo";
import { getBookings } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BookingCard } from "@/components/booking/booking-card";
import { BookingCalendar } from "@/components/business/booking-calendar";
import { cn } from "@/lib/utils";

type Scope = "upcoming" | "past";

// The calendar renders confirmed / completed / pending only; cancelled and
// rejected bookings drop off it (they still appear in the list below).
function bookingToCal(b: Booking): DemoBooking | null {
  if (b.status !== "confirmed" && b.status !== "completed" && b.status !== "pending") return null;
  return {
    id: b.id,
    title: b.serviceName || "Booking",
    client: b.providerName,
    serviceLabel: b.serviceName || "",
    startUtc: b.startUtc,
    endUtc: b.endUtc,
    status: b.status,
    partySize: b.partySize,
    priceMinorUnits: b.priceMinorUnits,
    currency: b.currency,
  };
}

export default function BookingsPage() {
  const { user, ready, singleBusiness } = useApp();
  const router = useRouter();
  const tz = user?.timezone ?? "UTC";
  const [scope, setScope] = useState<Scope>("upcoming");

  // One "all" fetch feeds the calendar; the list uses its own scoped fetch so
  // the backend's completed-in-past derivation is preserved for Upcoming / Past.
  // Single-business mode has a dedicated Calendar tab, so the my-bookings
  // calendar is dropped here (and its fetch skipped) to avoid two calendars.
  const all = useAsync<Booking[]>(
    () => (singleBusiness ? Promise.resolve([]) : getBookings("all")),
    [singleBusiness],
  );
  const data = useAsync<Booking[]>(() => getBookings(scope), [scope]);

  const calBookings = useMemo(
    () => (all.data ?? []).map(bookingToCal).filter((b): b is DemoBooking => b !== null),
    [all.data],
  );
  const bookings = data.data ?? [];

  return (
    <section className="space-y-4 py-4">
      <h1 className="text-xl font-semibold tracking-tight md:sr-only">Bookings</h1>

      {/* Calendar of my bookings — marketplace only; single-business has its own
          Calendar tab, so this would be a redundant second calendar. */}
      {!singleBusiness ? (
        all.loading && !all.data ? (
          <Skeleton className="h-72 w-full" />
        ) : calBookings.length > 0 ? (
          <BookingCalendar
            bookings={calBookings}
            timezone={tz}
            defaultView="month"
            onOpen={(b) => router.push(`/bookings/${b.id}`)}
          />
        ) : null
      ) : null}

      {/* Scope toggle */}
      <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
        {(["upcoming", "past"] as Scope[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setScope(s)}
            aria-pressed={scope === s}
            className={cn(
              "rounded-md px-4 py-1 text-sm font-medium capitalize transition-colors",
              scope === s
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {!ready || (data.loading && !data.data) ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)
        ) : data.error ? (
          <EmptyState title="Couldn't load bookings" body="Something interrupted the request.">
            <Button className="mt-1" onPress={data.reload}>
              Try again
            </Button>
          </EmptyState>
        ) : bookings.length === 0 ? (
          <EmptyState
            icon={<Ticket className="size-8" aria-hidden />}
            title={scope === "upcoming" ? "No upcoming bookings" : "No past bookings"}
            body={
              scope === "upcoming"
                ? "Find a provider and book a time — it'll show up here."
                : "Bookings you've completed or that have passed will appear here."
            }
            actionHref={scope === "upcoming" ? "/search" : undefined}
            actionLabel={scope === "upcoming" ? "Go to Search" : undefined}
          />
        ) : (
          bookings.map((b) => (
            <BookingCard
              key={b.id}
              booking={b}
              serviceName={b.serviceName || "Booking"}
              providerName={b.providerName}
              tz={tz}
            />
          ))
        )}
      </div>
    </section>
  );
}
