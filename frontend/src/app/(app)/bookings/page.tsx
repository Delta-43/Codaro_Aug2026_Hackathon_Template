"use client";

/**
 * Tab 4 — Bookings. Upcoming / Past segmented list backed by getBookings(scope).
 * Bookings carry only ids, so provider and service names are resolved once per
 * list and passed into each card. Tapping a row deep-links to the detail screen
 * where reschedule / cancel / review live.
 */
import { useState } from "react";
import { Ticket } from "lucide-react";
import type { Booking, Provider, Service } from "@/types/domain";
import { getBookings, getProvider, getService } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { BookingCard } from "@/components/booking/booking-card";
import { cn } from "@/lib/utils";

type Scope = "upcoming" | "past";

interface Loaded {
  bookings: Booking[];
  providers: Map<string, Provider>;
  services: Map<string, Service>;
}

export default function BookingsPage() {
  const { user } = useApp();
  const tz = user?.timezone ?? "UTC";
  const [scope, setScope] = useState<Scope>("upcoming");

  const data = useAsync<Loaded>(async () => {
    const bookings = await getBookings(scope);
    const providerIds = [...new Set(bookings.map((b) => b.providerId))];
    const serviceIds = [...new Set(bookings.map((b) => b.serviceId))];
    const [providerList, serviceList] = await Promise.all([
      Promise.all(providerIds.map((id) => getProvider(id).catch(() => null))),
      Promise.all(serviceIds.map((id) => getService(id).catch(() => null))),
    ]);
    const providers = new Map<string, Provider>();
    for (const p of providerList) if (p) providers.set(p.id, p);
    const services = new Map<string, Service>();
    for (const s of serviceList) if (s) services.set(s.id, s);
    return { bookings, providers, services };
  }, [scope]);

  const bookings = data.data?.bookings ?? [];

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
              serviceName={data.data?.services.get(b.serviceId)?.name ?? "Booking"}
              providerName={data.data?.providers.get(b.providerId)?.name ?? ""}
              tz={tz}
            />
          ))
        )}
      </div>
    </section>
  );
}
