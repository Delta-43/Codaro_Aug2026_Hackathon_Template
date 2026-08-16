"use client";

/**
 * Business tab 3 — Requests. Incoming booking requests to screen and act on.
 * A per-business "auto-approve" switch (top right) skips manual review; with it
 * off, each request is approved or rejected by hand. Each card surfaces the
 * client's screening signals — rating, how long they've been a member, past
 * bookings with you, and a flag when something looks off — so the business can
 * decide who they want to work with.
 *
 * Requests are demo-generated (deterministic per business) until the backend
 * grows a pending-approval state; actions are local for now.
 */
import { useMemo, useState } from "react";
import { Check, Clock, ShieldCheck, Star, TriangleAlert, Users, X } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { Button } from "@/components/ui/button";
import { demoRequests, type DemoRequest } from "@/lib/business-demo";
import { cn } from "@/lib/utils";

type Decision = "approved" | "rejected";

export default function RequestsPage() {
  const { ready, useCase, seed } = useOwner();
  const all = useMemo(() => demoRequests(useCase, seed), [useCase, seed]);
  const [autoApprove, setAutoApprove] = useState(false);
  const [decided, setDecided] = useState<Record<string, Decision>>({});

  if (!ready) return <Skeleton className="h-64 w-full" />;

  const pending = all.filter((r) => !decided[r.id]);

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
        <AutoApproveSwitch on={autoApprove} onChange={setAutoApprove} />
      </div>

      {autoApprove ? (
        <div className="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-primary">
          <ShieldCheck className="size-4 shrink-0" aria-hidden />
          New requests skip this queue and are confirmed on arrival. Turn off to screen each one.
        </div>
      ) : null}

      {pending.length === 0 && !autoApprove ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No requests waiting. Nice and clear.
        </p>
      ) : (
        <ul className="space-y-3">
          {all.map((r) => (
            <RequestCard
              key={r.id}
              request={r}
              partyNoun={useCase.partyNoun}
              decision={decided[r.id]}
              autoApprove={autoApprove}
              onDecide={(d) => setDecided((prev) => ({ ...prev, [r.id]: d }))}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function AutoApproveSwitch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className="flex shrink-0 flex-col items-end gap-1"
    >
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Auto-approve
      </span>
      <span
        className={cn(
          "flex h-6 w-11 items-center rounded-full p-0.5 transition-colors",
          on ? "bg-primary" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "size-5 rounded-full bg-card shadow-sm transition-transform",
            on ? "translate-x-5" : "translate-x-0",
          )}
        />
      </span>
    </button>
  );
}

function RequestCard({
  request: r,
  partyNoun,
  decision,
  autoApprove,
  onDecide,
}: {
  request: DemoRequest;
  partyNoun: string | null;
  decision?: Decision;
  autoApprove: boolean;
  onDecide: (d: Decision) => void;
}) {
  const settled = decision ?? (autoApprove ? "approved" : undefined);
  const memberLabel =
    r.memberMonths >= 12
      ? `${Math.floor(r.memberMonths / 12)}y member`
      : `${r.memberMonths}mo member`;

  return (
    <li
      className={cn(
        "rounded-2xl border bg-card p-4 transition-colors",
        settled === "approved"
          ? "border-primary/30"
          : settled === "rejected"
            ? "border-border opacity-60"
            : r.flagged
              ? "border-amber-500/40"
              : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        <AvatarImg src={r.avatarUrl} alt="" className="size-11 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-semibold">{r.clientName}</span>
            <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
              <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
              {r.rating.toFixed(1)}
            </span>
            {r.flagged ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                <TriangleAlert className="size-3" aria-hidden /> Screen
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            <span>{memberLabel}</span>
            <span aria-hidden>·</span>
            <span>{r.bookingsWithYou} bookings with you</span>
          </div>
          <p className="mt-2 text-sm">
            Wants <span className="font-medium">{r.serviceLabel}</span> {r.note}.
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden /> {r.whenLabel}
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
            {settled === "approved" ? (autoApprove && !decision ? "Auto-approved" : "Approved") : "Rejected"}
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
