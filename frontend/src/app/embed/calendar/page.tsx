"use client";

// Embed's booking screen — standalone copy of (app)/calendar/page.tsx with
// /embed-relative EmptyState hrefs (this tree has no /search or top-level
// /provider route). Renders the same <BookingFlow>; kept as its own thin page
// rather than threading extra href props through the (app) version, since
// this is route-specific glue, not shared domain logic.
import { CalendarDays } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";
import { BookingFlow } from "@/components/booking/booking-flow";

export default function EmbedCalendarPage() {
  const { activeProvider, activeService, activeResource, user } = useApp();

  if (!activeProvider) {
    return (
      <EmptyState
        icon={<CalendarDays className="size-8" aria-hidden />}
        title="Nothing to book yet"
        body="This business isn't set up for booking yet."
      />
    );
  }

  if (!activeService) {
    return (
      <EmptyState
        icon={<CalendarDays className="size-8" aria-hidden />}
        title="Choose something to book"
        body={`Pick something on the ${activeProvider.name} profile to see availability.`}
        actionHref="/embed"
        actionLabel="View profile"
      />
    );
  }

  const tz = user?.timezone ?? "UTC";

  return (
    <section className="py-2">
      <BookingFlow
        provider={activeProvider}
        service={activeService}
        resource={activeResource}
        tz={tz}
      />
    </section>
  );
}
