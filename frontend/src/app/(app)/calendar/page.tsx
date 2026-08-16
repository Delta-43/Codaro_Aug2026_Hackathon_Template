"use client";

// Tab 3 — Calendar / availability + booking. Browsable Month · Week · Day with
// density and slot states; selecting availability runs the confirm → create →
// result flow (Phase 6).
import { CalendarDays } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";
import { BookingFlow } from "@/components/booking/booking-flow";

export default function CalendarPage() {
  const { activeProvider, activeService, activeResource, user, vertical } = useApp();

  if (!activeProvider) {
    return (
      <EmptyState
        icon={<CalendarDays className="size-8" aria-hidden />}
        title={vertical.copy.noProviderTitle}
        body={vertical.copy.noProviderBody}
        actionHref="/search"
        actionLabel="Go to Search"
      />
    );
  }

  if (!activeService) {
    return (
      <EmptyState
        icon={<CalendarDays className="size-8" aria-hidden />}
        title="Choose something to book"
        body={`Pick a ${vertical.serviceNoun.toLowerCase()} on the ${activeProvider.name} profile to see availability.`}
        actionHref="/provider"
        actionLabel="View profile"
      />
    );
  }

  const tz = user?.timezone ?? "UTC";

  return (
    <section className="py-4">
      <BookingFlow
        provider={activeProvider}
        service={activeService}
        resource={activeResource}
        tz={tz}
      />
    </section>
  );
}
