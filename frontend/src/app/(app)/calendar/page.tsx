// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

// Tab 3 — Calendar / availability + booking. Browsable Month · Week · Day with
// density and slot states; selecting availability runs the confirm → create →
// result flow (Phase 6).
import { CalendarDays } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";
import { BookingFlow } from "@/components/booking/booking-flow";
import { Skeleton } from "@/components/skeleton";

export default function CalendarPage() {
  const { activeProvider, activeService, activeResource, user, vertical, ready } = useApp();

  // Availability is rendered in the viewer's zone, taken from their profile.
  // Painting before boot finishes means `tz` falls back to UTC and every slot
  // shows at the wrong local time.
  if (!ready) return <Skeleton className="h-96 w-full" />;

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
