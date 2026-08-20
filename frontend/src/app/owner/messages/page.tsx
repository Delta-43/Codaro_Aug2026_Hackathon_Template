"use client";

/**
 * Business tab 3 — Messages. The permanent hub for everything conversational:
 * incoming booking requests to screen at the top (a request is the start of a
 * relationship), then the thread inbox below. The per-business "auto-approve"
 * switch flips every offer between manual review and instant confirmation
 * (persisted server-side); with it off, each request is approved or rejected by
 * hand against the real backend. Each card surfaces the client's screening
 * signals — membership length, past bookings with you, cancellations. Requests +
 * actions are the real /owner + /bookings API.
 *
 * On a service whose `booking.granularity` is "none" the customer picks no date
 * at all — they describe what they need and the BUSINESS assigns the day. That
 * makes this screen, not the calendar, the place a date is chosen: each card
 * carries an <AssignDatePanel> that clears the blocking prerequisites, picks an
 * open date on the request's own resource, and announces it down the thread the
 * inbox below already renders. Approve/Reject stay for services that arrive with
 * a date and only need a yes or no.
 *
 * (Pass 2 will add an Archived view of rejected/completed relationships.)
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, Check, Clock, ShieldCheck, Star, TriangleAlert, Users, X } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { MessagingSection } from "@/components/messaging/messaging-section";
import { Button } from "@/components/ui/button";
import { InlineMessage } from "@/components/ui/inline-message";
import { ArrangementSummary } from "@/components/owner/arrangement-summary";
import { AssignDatePanel } from "@/components/owner/assign-date-panel";
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
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

type Decision = "approved" | "rejected";

function memberLabel(iso: string | null): string {
  if (!iso) return "new member";
  const months = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24 * 30)));
  if (months < 1) return "joined this month";
  return months >= 12 ? `${Math.floor(months / 12)}y member` : `${months}mo member`;
}

export default function MessagesPage() {
  const { ready, vocab, activeProvider } = useOwner();
  const [requests, setRequests] = useState<OwnerRequest[]>([]);
  const [services, setServices] = useState<OwnerServiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [decided, setDecided] = useState<Record<string, Decision>>({});
  const [error, setError] = useState<string | null>(null);
  // Which card has its assign-date panel open. One at a time: two open panels
  // both holding a date for the same chapel is a race the owner can't see.
  const [assigning, setAssigning] = useState<string | null>(null);
  // Assigned dates, kept at page level on purpose: an assigned request is
  // `confirmed`, so `load()` drops it from the pending list and the card that
  // reported the success disappears with it.
  const [assignedNotes, setAssignedNotes] = useState<string[]>([]);

  // Scoped to the active provider like the Services tab — the owner endpoints
  // return every business the owner has, and the auto-approve master switch
  // below must never flip another business's offers. Keyed on the id, not the
  // object, so a provider refresh minting same-id objects doesn't refetch.
  const activeProviderId = activeProvider?.id ?? null;
  const load = useCallback(async () => {
    const [reqs, svcs] = await Promise.all([
      getOwnerRequests().catch(() => [] as OwnerRequest[]),
      getOwnerServices().catch(() => [] as OwnerServiceSummary[]),
    ]);
    setRequests(activeProviderId ? reqs.filter((r) => r.providerId === activeProviderId) : reqs);
    setServices(activeProviderId ? svcs.filter((s) => s.providerId === activeProviderId) : svcs);
    setLoading(false);
  }, [activeProviderId]);

  useEffect(() => {
    // Back to the skeleton on a provider switch — never show business A's
    // requests under business B's header while the refetch is in flight.
    setLoading(true);
    void load();
  }, [load]);

  const autoApprove = services.length > 0 && services.every((s) => s.autoApprove);
  const pending = useMemo(() => requests.filter((r) => !decided[r.id]), [requests, decided]);
  // The request's own service supplies the subject-field labels and the
  // prerequisite descriptors — both are per-service, so they're looked up by
  // id rather than read off the global config.
  const serviceById = useMemo(
    () => new Map(services.map((s) => [s.id, s] as const)),
    [services],
  );

  async function onAssigned(summary: string) {
    setAssignedNotes((prev) => [summary, ...prev]);
    setAssigning(null);
    await load();
  }

  async function toggleAutoApprove(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      // Auto-approve is per-service; the switch flips every offer at once.
      await Promise.all(
        services.filter((s) => s.autoApprove !== next).map((s) => updateService(s.id, { autoApprove: next })),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't update auto-approve.");
    } finally {
      // Refetch even on partial failure — some services may have flipped.
      await load();
      setBusy(false);
    }
  }

  async function decide(r: OwnerRequest, d: Decision) {
    if (busy) return; // no double-fire: approve-then-reject during the round-trip
    setBusy(true);
    setError(null);
    try {
      if (d === "approved") await approveBooking(r.id);
      else await rejectBooking(r.id);
      setDecided((prev) => ({ ...prev, [r.id]: d }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || loading) return <Skeleton className="h-64 w-full" />;

  return (
    <section className="space-y-4 py-2">
      {/* Requests to screen — the top of every business relationship. */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Requests</h1>
          <p className="text-sm text-muted-foreground">
            {autoApprove
              ? `Auto-approve is on — new ${vocab.bookingNounPlural.toLowerCase()} are accepted automatically.`
              : `${pending.length} waiting on your decision.`}
          </p>
        </div>
        <AutoApproveSwitch on={autoApprove} disabled={busy || services.length === 0} onChange={toggleAutoApprove} />
      </div>

      {error ? <InlineMessage className="rounded-2xl px-4 py-2.5">{error}</InlineMessage> : null}

      {assignedNotes.map((note, i) => (
        <InlineMessage key={`${note}-${i}`} tone="notice" className="rounded-2xl px-4 py-2.5">
          Date assigned — {note}
        </InlineMessage>
      ))}

      {autoApprove ? (
        <div className="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-primary">
          <ShieldCheck className="size-4 shrink-0" aria-hidden />
          New requests skip this queue and are confirmed on arrival. Turn off to screen each one.
        </div>
      ) : null}

      {requests.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          No requests waiting. Nice and clear.
        </p>
      ) : (
        <ul className="space-y-3">
          {requests.map((r) => (
            <RequestCard
              key={r.id}
              request={r}
              service={serviceById.get(r.serviceId)}
              partyNoun={vocab.partyNoun}
              decision={decided[r.id]}
              busy={busy}
              onDecide={(d) => decide(r, d)}
              assignOpen={assigning === r.id}
              onToggleAssign={() => setAssigning((cur) => (cur === r.id ? null : r.id))}
              onAssigned={onAssigned}
            />
          ))}
        </ul>
      )}

      {/* Inbox — the business's conversations with its customers. */}
      <MessagingSection basePath="/owner/messages" />
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
      className={cn("flex shrink-0 flex-col items-end gap-1 transition-all disabled:opacity-50", buttonFx.press)}
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
  service,
  partyNoun,
  decision,
  busy,
  onDecide,
  assignOpen,
  onToggleAssign,
  onAssigned,
}: {
  request: OwnerRequest;
  service?: OwnerServiceSummary;
  partyNoun: string | null;
  decision?: Decision;
  busy: boolean;
  onDecide: (d: Decision) => void;
  assignOpen: boolean;
  onToggleAssign: () => void;
  onAssigned: (summary: string) => void | Promise<void>;
}) {
  const browserTz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
  const flagged = r.client.cancelledWithProvider > 0;
  const settled = decision;
  // The customer never picked this date on a "none"-granularity service — it is
  // the placeholder the request was parked on. Saying "wants 14:00 on Tuesday"
  // about a date nobody chose is a lie the owner would act on.
  const dateIsPlaceholder = service?.granularity === "none";

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
        <AvatarImg src={r.client.avatarUrl} name={r.client.displayName} alt="" className="size-11 shrink-0" />
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
              <Clock className="size-3.5" aria-hidden />{" "}
              {dateIsPlaceholder
                ? "No date yet — awaiting assignment"
                : formatBookingWhen(r.startUtc, r.endUtc, browserTz)}
            </span>
            {partyNoun && r.partySize > 1 ? (
              <span className="inline-flex items-center gap-1">
                <Users className="size-3.5" aria-hidden /> {r.partySize} {partyNoun}
              </span>
            ) : null}
          </div>

          {/* Who it's for, what they chose, and who settles it. */}
          <ArrangementSummary
            booking={r}
            fields={service?.subject?.fields ?? []}
            subjectNoun={service?.subject?.noun}
          />
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
            {/* The primary move on a date-assigning service; still offered
                elsewhere, where it just moves an already-chosen date. */}
            <Button
              size="sm"
              variant={dateIsPlaceholder ? "default" : "outline"}
              isDisabled={busy}
              onPress={onToggleAssign}
              aria-expanded={assignOpen}
            >
              <CalendarDays aria-hidden /> {assignOpen ? "Hide dates" : "Assign date"}
            </Button>
            <Button
              size="sm"
              variant={dateIsPlaceholder ? "outline" : "default"}
              isDisabled={busy}
              onPress={() => onDecide("approved")}
            >
              <Check aria-hidden /> Approve
            </Button>
            <Button variant="outline" size="sm" isDisabled={busy} onPress={() => onDecide("rejected")}>
              <X aria-hidden /> Reject
            </Button>
          </>
        )}
      </div>

      {assignOpen && !settled ? (
        <AssignDatePanel
          request={r}
          service={service}
          onClose={onToggleAssign}
          onAssigned={onAssigned}
        />
      ) : null}
    </li>
  );
}
