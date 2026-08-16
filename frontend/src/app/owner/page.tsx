"use client";

/**
 * Business tab 1 — Dashboard. The one-tap overview: who you are (verified badge),
 * the three numbers that matter (with tap/hover explanations), this week's
 * bookings, and the requests still waiting on you. Identity + content follow the
 * active demo use case (Settings → Demo) so every niche renders coherently.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Star } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { VerifiedScene } from "@/components/business/verified-badge";
import { StatTile } from "@/components/business/stat-tile";
import { BookingCalendar } from "@/components/business/booking-calendar";
import { businessMetrics, demoBookings, demoRequests } from "@/lib/business-demo";

const browserTz = () =>
  typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";

export default function DashboardPage() {
  const { ready, useCase, demoBusiness, seed } = useOwner();
  const tz = browserTz();

  const metrics = useMemo(() => businessMetrics(useCase, seed), [useCase, seed]);
  const bookings = useMemo(() => demoBookings(useCase, seed, tz), [useCase, seed, tz]);
  const requests = useMemo(() => demoRequests(useCase, seed), [useCase, seed]);

  if (!ready) {
    return (
      <div className="space-y-4 py-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <section className="space-y-5 py-2">
      {/* Badge area */}
      <div className="flex items-center gap-3">
        <VerifiedScene scene={useCase.profileScene} size="md" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight">{demoBusiness.name}</h1>
          <p className="truncate text-sm text-muted-foreground">
            {useCase.label} · {demoBusiness.city}
          </p>
          <p className="mt-0.5 flex items-center gap-1 text-sm">
            <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
            <span className="font-medium">{demoBusiness.rating.toFixed(1)}</span>
            <span className="text-muted-foreground">({demoBusiness.reviewCount} reviews)</span>
          </p>
        </div>
      </div>

      {/* Glanceable numbers */}
      <div className="flex items-stretch justify-between gap-1 rounded-2xl border border-border bg-card p-3">
        {metrics.map((m, i) => (
          <div key={m.key} className="flex flex-1 items-stretch">
            {i > 0 ? <span className="mr-1 w-px bg-border" aria-hidden /> : null}
            <StatTile metric={m} />
          </div>
        ))}
      </div>

      {/* Bookings — this week */}
      <div>
        <SectionHeader title="Bookings" href="/owner/calendar" cta="Full calendar" />
        <BookingCalendar bookings={bookings} timezone={tz} defaultView="week" compact onOpen={() => {}} />
      </div>

      {/* Requests checklist */}
      <div>
        <SectionHeader title="Requests to manage" href="/owner/requests" cta="All requests" />
        <RequestChecklist requests={requests} />
      </div>
    </section>
  );
}

function SectionHeader({ title, href, cta }: { title: string; href: string; cta: string }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h2 className="text-sm font-semibold">{title}</h2>
      <Link href={href} className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline">
        {cta} <ArrowUpRight className="size-3.5" aria-hidden />
      </Link>
    </div>
  );
}

function RequestChecklist({ requests }: { requests: ReturnType<typeof demoRequests> }) {
  const [done, setDone] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const open = requests.filter((r) => !done.has(r.id));

  return (
    <ul className="divide-y divide-border rounded-2xl border border-border bg-card">
      {requests.map((r) => {
        const checked = done.has(r.id);
        return (
          <li key={r.id} className="flex items-center gap-3 px-3 py-2.5">
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(r.id)}
              aria-label={`Mark ${r.clientName}'s request handled`}
              className="size-4 shrink-0 rounded border-border accent-primary"
            />
            <p className={`min-w-0 flex-1 text-sm ${checked ? "text-muted-foreground line-through" : ""}`}>
              <span className="font-medium">{r.clientName}</span> {r.note}
              <span className="text-muted-foreground"> · {r.serviceLabel} · {r.whenLabel}</span>
            </p>
          </li>
        );
      })}
      {open.length === 0 ? (
        <li className="px-3 py-3 text-center text-xs text-muted-foreground">All caught up 🎉</li>
      ) : null}
    </ul>
  );
}
