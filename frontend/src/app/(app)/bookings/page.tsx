"use client";

/**
 * Tab 4 — Bookings. Upcoming / Past segmented list backed by getBookings(scope).
 * Each booking carries its provider and service names inline (embedded by the
 * API), so the list is a single request. Tapping a row deep-links to the detail
 * screen where reschedule / cancel / review live.
 */
import { useState } from "react";
import { Ticket } from "lucide-react";
import type { Booking } from "@/types/domain";
import { getBookings } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BookingCard } from "@/components/booking/booking-card";
import { cn } from "@/lib/utils";

type Scope = "upcoming" | "past";

export default function BookingsPage() {
  const { user } = useApp();
  const tz = user?.timezone ?? "UTC";
  const [scope, setScope] = useState<Scope>("upcoming");

  const data = useAsync<Booking[]>(() => getBookings(scope), [scope]);

  const bookings = data.data ?? [];

  return (
    <section className="space-y-4 py-4">
      <h1 className="text-xl font-semibold tracking-tight md:sr-only">Bookings</h1>

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
        {data.loading && !data.data ? (
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
