"use client";

/**
 * Business tab 1 — Dashboard. The one-tap overview: who you are (verified badge),
 * the three numbers that matter (with tap/hover explanations), this week's
 * bookings, and the requests still waiting on you. All numbers are real,
 * aggregated server-side from the owner's own providers (/owner/dashboard).
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Star } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { BusinessBadge } from "@/components/business/verified-badge";
import { StatTile } from "@/components/business/stat-tile";
import { BookingCalendar } from "@/components/business/booking-calendar";
import { getOwnerDashboard } from "@/api";
import type { OwnerDashboard, OwnerRequest } from "@/types/domain";
import type { Metric } from "@/lib/business-view";
import { ownerBookingToCal } from "@/lib/owner-view";
import { CreateBusiness } from "@/components/business/create-business";
import type { VerticalConfig } from "@/config/verticals";
import { browserTz, formatBookingWhen, formatMoney } from "@/lib/format";
import type { TenancyTerms } from "@/api";

/** `tenancy.commission` in the tile's words: what the platform takes, and what
 *  is left. Declared since v2 and shown on no owner screen, so a marketplace
 *  taking 12% looked to its tenants exactly like one taking nothing. */
function commissionSub(rev: { minorUnits: number; currency: string }, terms: TenancyTerms) {
  if (!terms.commission.enabled || !terms.commission.rateBps) return null;
  const rate = terms.commission.rateBps / 100;
  const net = Math.round(rev.minorUnits * (1 - terms.commission.rateBps / 10000));
  return `${formatMoney(net, rev.currency)} after ${rate}% commission`;
}

function metricsOf(d: OwnerDashboard, vocab: VerticalConfig, terms: TenancyTerms): Metric[] {
  const { upcomingBookings: up, clientSatisfaction: sat, revenue: rev } = d.glance;
  const breakdown = up.byService.slice(0, 3).map((s) => s.count).join(" · ");
  const otherCurrencies = rev.byCurrency.slice(1).map((c) => c.currency);
  return [
    {
      key: "upcoming",
      label: `Upcoming ${vocab.bookingNounPlural.toLowerCase()}`,
      value: String(up.total),
      sub: up.byService.length ? `${breakdown} across ${up.byService.length} offers` : "next 30 days",
      tone: "neutral",
      help: `Confirmed ${vocab.bookingNounPlural.toLowerCase()} in the next 30 days, broken down by offer. Open the calendar to manage any of them.`,
    },
    {
      key: "satisfaction",
      label: `${vocab.clientNoun} satisfaction`,
      value: `${sat.deltaPct >= 0 ? "+" : ""}${sat.deltaPct}%`,
      sub: "vs last month",
      tone: sat.deltaPct > 0 ? "up" : sat.deltaPct < 0 ? "down" : "neutral",
      help: `Month-over-month change in ${vocab.bookingNoun.toLowerCase()} volume. You're rated ${sat.currentRating.toFixed(1)} across ${sat.reviewCount} reviews.`,
    },
    {
      key: "revenue",
      label: "Revenue this month",
      value: formatMoney(rev.minorUnits, rev.currency),
      sub:
        commissionSub(rev, terms) ??
        (otherCurrencies.length ? `+ ${otherCurrencies.join(", ")}` : "confirmed this cycle"),
      tone: "up",
      help: `Value of confirmed bookings for ${rev.period}${otherCurrencies.length ? `, shown in your top currency (you also earn in ${otherCurrencies.join(", ")})` : ""}, gross.${
        terms.commission.enabled && terms.commission.rateBps
          ? ` This marketplace charges ${terms.commission.rateBps / 100}% commission, on ${terms.commission.chargedOn}.`
          : ""
      }`,
    },
  ];
}

export default function DashboardPage() {
  const { ready, activeProvider, scene, vocab, tenancyTerms } = useOwner();
  const tz = browserTz();
  const [data, setData] = useState<OwnerDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getOwnerDashboard()
      .then((d) => !cancelled && setData(d))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const metrics = useMemo(
    () => (data ? metricsOf(data, vocab, tenancyTerms) : []),
    [data, vocab, tenancyTerms],
  );
  const week = useMemo(() => (data?.weekBookings ?? []).map((b) => ownerBookingToCal(b)), [data]);

  if (!ready || loading) {
    return (
      <div className="space-y-4 py-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const provider = data?.provider ?? activeProvider;

  // An owner with no provider gets the create form, not a dead end.
  if (!provider) return <CreateBusiness />;

  return (
    <section className="space-y-5 py-2">
      {/* Badge area */}
      <div className="flex items-center gap-3">
        <BusinessBadge avatarUrl={provider.avatarUrl} name={provider.name} scene={scene} size="md" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight">{provider.name}</h1>
          <p className="truncate text-sm text-muted-foreground">
            {vocab.label} · {provider.location.city}
          </p>
          <p className="mt-0.5 flex items-center gap-1 text-sm">
            <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
            <span className="font-medium">{provider.rating.toFixed(1)}</span>
            <span className="text-muted-foreground">({provider.reviewCount} reviews)</span>
          </p>
        </div>
      </div>

      {/* `tenancy.tenantVerification` — what this marketplace requires of a
          business before it trades. Declared in the config since v2 and shown
          nowhere, so an owner could not find out what was being asked of them.
          Informational: the engine does not yet gate trading on it, and saying
          so is better than implying a check that does not run. */}
      {tenancyTerms.verification.required ? (
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-sm font-semibold">Verification required to trade here</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {tenancyTerms.verification.credentials.length
              ? `Hold and keep current: ${tenancyTerms.verification.credentials
                  .map((c) => c.replace(/_/g, " "))
                  .join(", ")}.`
              : "This marketplace verifies its businesses before they trade."}
          </p>
        </div>
      ) : null}

      {/* Glanceable numbers */}
      {metrics.length ? (
        <div className="flex items-stretch justify-between gap-1 rounded-2xl border border-border bg-card p-3">
          {metrics.map((m, i) => (
            <div key={m.key} className="flex flex-1 items-stretch">
              {i > 0 ? <span className="mr-1 w-px bg-border" aria-hidden /> : null}
              <StatTile metric={m} />
            </div>
          ))}
        </div>
      ) : null}

      {/* Bookings — this week */}
      <div>
        <SectionHeader title={vocab.bookingNounPlural} href="/owner/bookings" cta="Full calendar" />
        <BookingCalendar bookings={week} timezone={tz} defaultView="week" compact onOpen={() => {}} />
      </div>

      {/* Requests checklist */}
      <div>
        <SectionHeader title="Requests to manage" href="/owner/messages" cta="All requests" />
        <RequestChecklist requests={data?.requests ?? []} tz={tz} />
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

function RequestChecklist({ requests, tz }: { requests: OwnerRequest[]; tz: string }) {
  const [done, setDone] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (requests.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
        No requests waiting — all caught up 🎉
      </p>
    );
  }

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
              aria-label={`Mark ${r.client.displayName}'s request handled`}
              className="size-4 shrink-0 rounded border-border accent-primary"
            />
            <AvatarImg src={r.client.avatarUrl} name={r.client.displayName} alt="" className="size-8" />
            <p className={`min-w-0 flex-1 text-sm ${checked ? "text-muted-foreground line-through" : ""}`}>
              <span className="font-medium">{r.client.displayName}</span> wants {r.serviceName}
              <span className="text-muted-foreground"> · {formatBookingWhen(r.startUtc, r.endUtc, tz)}</span>
            </p>
          </li>
        );
      })}
    </ul>
  );
}
