"use client";

/**
 * Business tab 3 — Requests. Incoming booking requests to screen and act on.
 * The per-business "auto-approve" switch (top right) flips every offer between
 * manual review and instant confirmation (persisted server-side); with it off,
 * each request is approved or rejected by hand against the real backend. Each
 * card surfaces the client's screening signals — how long they've been a member,
 * past bookings with you, and any cancellations — so the business can decide who
 * they want to work with. Requests + actions are the real /owner + /bookings API.
 */
import { useEffect, useMemo, useState } from "react";
import { Check, Clock, ShieldCheck, Star, TriangleAlert, Users, X } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { Button } from "@/components/ui/button";
import {
  approveBooking,
  getOwnerRequests,
  getOwnerServices,
  rejectBooking,
  updateService,
  ApiError,
} from "@/api";
import type { OwnerRequest, OwnerServiceSummary } from "@/types/domain";
import { formatBookingWhen, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

type Decision = "approved" | "rejected";

function memberLabel(iso: string | null): string {
  if (!iso) return "new member";
  const months = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24 * 30)));
  if (months < 1) return "joined this month";
  return months >= 12 ? `${Math.floor(months / 12)}y member` : `${months}mo member`;
}

export default function RequestsPage() {
  const { ready, vocab } = useOwner();
  const [requests, setRequests] = useState<OwnerRequest[]>([]);
  const [services, setServices] = useState<OwnerServiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [decided, setDecided] = useState<Record<string, Decision>>({});
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const [reqs, svcs] = await Promise.all([
      getOwnerRequests().catch(() => [] as OwnerRequest[]),
      getOwnerServices().catch(() => [] as OwnerServiceSummary[]),
    ]);
    setRequests(reqs);
    setServices(svcs);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  const autoApprove = services.length > 0 && services.every((s) => s.autoApprove);
  const pending = useMemo(() => requests.filter((r) => !decided[r.id]), [requests, decided]);

  async function toggleAutoApprove(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      // Auto-approve is per-service; the switch flips every offer at once.
      await Promise.all(
        services.filter((s) => s.autoApprove !== next).map((s) => updateService(s.id, { autoApprove: next })),
      );
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update auto-approve.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(r: OwnerRequest, d: Decision) {
    setError(null);
    try {
      if (d === "approved") await approveBooking(r.id);
      else await rejectBooking(r.id);
      setDecided((prev) => ({ ...prev, [r.id]: d }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't go through. Try again.");
    }
  }

  if (!ready || loading) return <Skeleton className="h-64 w-full" />;

  return (
    <section className="space-y-4 py-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Requests</h1>
          <p className="text-sm text-muted-foreground">
            {autoApprove
              ? "Auto-approve is on — new bookings are accepted automatically."
              : `${pending.length} waiting on your decision.`}
          </p>
        </div>
        <AutoApproveSwitch on={autoApprove} disabled={busy || services.length === 0} onChange={toggleAutoApprove} />
      </div>

      {error ? (
        <p className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {autoApprove ? (
        <div className="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-primary">
          <ShieldCheck className="size-4 shrink-0" aria-hidden />
          New requests skip this queue and are confirmed on arrival. Turn off to screen each one.
        </div>
      ) : null}

      {requests.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No requests waiting. Nice and clear.
        </p>
      ) : (
        <ul className="space-y-3">
          {requests.map((r) => (
            <RequestCard
              key={r.id}
              request={r}
              partyNoun={vocab.partyNoun}
              decision={decided[r.id]}
              onDecide={(d) => decide(r, d)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function AutoApproveSwitch({
  on,
  disabled,
  onChange,
}: {
  on: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className="flex shrink-0 flex-col items-end gap-1 disabled:opacity-50"
    >
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Auto-approve</span>
      <span className={cn("flex h-6 w-11 items-center rounded-full p-0.5 transition-colors", on ? "bg-primary" : "bg-muted")}>
        <span
          className={cn("size-5 rounded-full bg-card shadow-sm transition-transform", on ? "translate-x-5" : "translate-x-0")}
        />
      </span>
    </button>
  );
}

function RequestCard({
  request: r,
  partyNoun,
  decision,
  onDecide,
}: {
  request: OwnerRequest;
  partyNoun: string | null;
  decision?: Decision;
  onDecide: (d: Decision) => void;
}) {
  const browserTz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
  const flagged = r.client.cancelledWithProvider > 0;
  const settled = decision;

  return (
    <li
      className={cn(
        "rounded-2xl border bg-card p-4 transition-colors",
        settled === "approved"
          ? "border-primary/30"
          : settled === "rejected"
            ? "border-border opacity-60"
            : flagged
              ? "border-amber-500/40"
              : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        <AvatarImg src={r.client.avatarUrl} alt="" className="size-11 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-semibold">{r.client.displayName}</span>
            {r.client.rating != null && r.client.reviewCount > 0 ? (
              <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                {r.client.rating.toFixed(1)}
              </span>
            ) : null}
            {flagged ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                <TriangleAlert className="size-3" aria-hidden /> Screen
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            <span>{memberLabel(r.client.memberSinceUtc)}</span>
            <span aria-hidden>·</span>
            <span>{r.client.bookingsWithProvider} bookings with you</span>
            {r.client.cancelledWithProvider > 0 ? (
              <>
                <span aria-hidden>·</span>
                <span className="text-amber-600 dark:text-amber-400">{r.client.cancelledWithProvider} cancelled</span>
              </>
            ) : null}
          </div>
          <p className="mt-2 text-sm">
            Wants <span className="font-medium">{r.serviceName}</span> ·{" "}
            {formatMoney(r.priceMinorUnits, r.currency)}.
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden /> {formatBookingWhen(r.startUtc, r.endUtc, browserTz)}
            </span>
            {partyNoun && r.partySize > 1 ? (
              <span className="inline-flex items-center gap-1">
                <Users className="size-3.5" aria-hidden /> {r.partySize} {partyNoun}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
        {settled ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-sm font-medium",
              settled === "approved" ? "text-primary" : "text-muted-foreground",
            )}
          >
            {settled === "approved" ? <Check className="size-4" aria-hidden /> : <X className="size-4" aria-hidden />}
            {settled === "approved" ? "Approved" : "Rejected"}
          </span>
        ) : (
          <>
            <Button size="sm" onPress={() => onDecide("approved")}>
              <Check aria-hidden /> Approve
            </Button>
            <Button variant="outline" size="sm" onPress={() => onDecide("rejected")}>
              <X aria-hidden /> Reject
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
