"use client";

// Tab 3 — Calendar / availability. Operates only on the locked-in provider &
// service. Empty states guide the user forward; the month/week/day views,
// density, and selection land in Phases 5–6.
import { CalendarDays } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";

export default function CalendarPage() {
  const { activeProvider, activeService, vertical } = useApp();

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

  return (
    <section className="py-6">
      <h1 className="text-xl font-semibold tracking-tight">{activeService.name}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{activeProvider.name}</p>
      <p className="mt-6 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Month · Week · Day availability, density, and slot selection arrive in
        Phases 5–6.
      </p>
    </section>
  );
}
