"use client";

/**
 * Assign-date panel — the owner-side half of a `booking.granularity: "none"`
 * service.
 *
 * On such a service the customer picks nothing: they submit a request, it lands
 * as a `pending` booking against a placeholder slot, and the BUSINESS names the
 * day afterwards (`timing.confirmation: "request_approve"`). Nothing in the
 * console did that job — a request could only be approved onto the placeholder
 * date it arrived with. This panel is where the real date is chosen and
 * announced.
 *
 * Three things it has to get right, all of them backend contracts:
 *
 * 1. **Same resource.** `POST /bookings/{id}/reschedule` reads `resource_id`
 *    from the booking's stored metadata and `_resolve_selection` rejects any
 *    slot that doesn't match it ("All times must be for the same option").
 *    So availability is fetched pinned to `request.resourceId` and no
 *    resource switch is offered — there is no such move to make.
 * 2. **Approve first.** `reschedule` requires status `confirmed`; `approve`
 *    is the only thing that gets it there. The order is not cosmetic.
 * 3. **Prerequisites gate the approve.** With `capabilities.prerequisites`
 *    on, `approve_booking` refuses while any *blocking* prerequisite is
 *    unmet and answers `Still outstanding: <labels>.` So the checklist comes
 *    first and the assign action stays disabled until it is clear — the
 *    owner clears the paperwork, then names the day.
 *
 * The announcement is drafted for the owner, not sent for them: it is a normal
 * editable textarea, and it goes out through the same `/conversations` thread
 * the inbox below already renders.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, Check, Loader2, Send, SquareCheckBig } from "lucide-react";
import {
  ApiError,
  approveBooking,
  getAvailability,
  getResources,
  rescheduleBooking,
  satisfyPrerequisite,
  sendMessage,
  startConversation,
} from "@/api";
import type { OwnerRequest, OwnerServiceSummary, Prerequisite, Slot } from "@/types/domain";
import { Button } from "@/components/ui/button";
import { InlineMessage } from "@/components/ui/inline-message";
import { Textarea } from "@/components/ui/textarea";
import { browserTz, zoneAbbrev } from "@/lib/format";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

/** How far ahead to look for an assignable date. The backend clamps to its own
 *  `timing.advanceBookingWindowDays` regardless — this is only how much of that
 *  window we ask for, and asking for more than exists costs nothing. */
const HORIZON_DAYS = 60;
/** Fallback for `timing.approvalWindowHours` on a backend too old to send it.
 *  Only decides which dates are grouped under "the week"; nothing enforces it. */
const FALLBACK_APPROVAL_WINDOW_HOURS = 168;

const DAY_MS = 24 * 60 * 60 * 1000;

/** "Friday, 5 September" — a date said out loud, for the announcement and the
 *  picker. `format.ts` has no long-weekday variant and this is the only caller. */
function longDate(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(iso));
}

function shortTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** The name the announcement addresses. The subject's first text-ish field is
 *  the deployment's own idea of "who this is about" — `full_name` on the funeral
 *  config — so it is read by descriptor order, never by a hardcoded key. */
function subjectName(request: OwnerRequest, service?: OwnerServiceSummary | null): string {
  const subject = request.subject ?? {};
  const ordered = service?.subject?.fields ?? [];
  for (const f of ordered) {
    const v = subject[f.key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  for (const v of Object.values(subject)) {
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

/** One phase of the commit. Each is a real round-trip, shown as it happens so a
 *  three-call sequence doesn't look like one hung button. */
type Phase = "idle" | "approving" | "assigning" | "notifying" | "done";

const PHASE_LABEL: Record<Exclude<Phase, "idle" | "done">, string> = {
  approving: "Approving the request…",
  assigning: "Assigning the date…",
  notifying: "Notifying the family…",
};

export function AssignDatePanel({
  request,
  service,
  onClose,
  onAssigned,
}: {
  request: OwnerRequest;
  /** The request's service — supplies the prerequisite descriptors (labels) and
   *  the subject noun. Absent only if the owner's service list failed to load,
   *  in which case the checklist falls back to the raw pending keys. */
  service?: OwnerServiceSummary | null;
  onClose: () => void;
  /** Told what happened, so the page can show it after this card has left the
   *  pending list (an assigned request is `confirmed` and no longer a request). */
  onAssigned: (summary: string) => void | Promise<void>;
}) {
  const tz = browserTz();

  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [resourceName, setResourceName] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  const [met, setMet] = useState<string[]>(request.prerequisitesMet ?? []);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const [selected, setSelected] = useState<Slot | null>(null);
  const [draft, setDraft] = useState("");
  const [draftEdited, setDraftEdited] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  // --- assignable dates ---------------------------------------------------
  // Pinned to the resource the request already holds: reschedule enforces
  // resource equality, so any other resource's slots would only ever 400.
  // Keyed on the CONTENT of the held-slot list, not the array: the parent
  // re-renders with a fresh `requests` array on every page state change, and an
  // identity dep would re-run this fetch each time the owner ticked a box.
  const heldKey = request.slotIds.join(",");
  useEffect(() => {
    let live = true;
    const from = new Date();
    const to = new Date(from.getTime() + HORIZON_DAYS * DAY_MS);
    void (async () => {
      try {
        const [days, resources] = await Promise.all([
          getAvailability({
            serviceId: request.serviceId,
            resourceId: request.resourceId,
            fromUtc: from.toISOString(),
            toUtc: to.toISOString(),
          }),
          getResources(request.serviceId).catch(() => []),
        ]);
        if (!live) return;
        const held = new Set(heldKey ? heldKey.split(",") : []);
        const party = Math.max(1, request.partySize);
        const open = days
          .flatMap((d) => d.slots)
          .filter(
            (s) =>
              s.resourceId === request.resourceId &&
              !held.has(s.id) &&
              s.status !== "blocked" &&
              s.status !== "past" &&
              s.capacity - s.bookedCount >= party,
          )
          .sort((a, b) => a.startUtc.localeCompare(b.startUtc));
        setSlots(open);
        setResourceName(resources.find((r) => r.id === request.resourceId)?.name ?? "");
      } catch (e) {
        if (!live) return;
        setLoadError(e instanceof ApiError ? e.message : "Couldn't load open dates.");
        setSlots([]);
      }
    })();
    return () => {
      live = false;
    };
  }, [request.serviceId, request.resourceId, heldKey, request.partySize]);

  // --- prerequisites ------------------------------------------------------
  // Only BLOCKING ones: `POST /bookings/{id}/prerequisites/{key}` accepts no
  // other key (404 "No blocking prerequisite named …"), and only these stop
  // the approve. Descriptors carry the labels; the booking carries the state.
  const blocking: Prerequisite[] = useMemo(
    () => (service?.prerequisites ?? []).filter((p) => p.blocksConfirmation),
    [service],
  );
  const fallbackPending = useMemo(
    () =>
      blocking.length === 0
        ? (request.prerequisitesPending ?? []).map(
            (key): Prerequisite => ({
              key,
              kind: "",
              label: key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
              appliesTo: "",
              required: true,
              blocksConfirmation: true,
            }),
          )
        : [],
    [blocking.length, request.prerequisitesPending],
  );
  const checklist = blocking.length ? blocking : fallbackPending;
  const outstanding = checklist.filter((p) => !met.includes(p.key));
  const cleared = checklist.length > 0 && outstanding.length === 0;

  async function satisfy(key: string) {
    if (savingKey) return;
    setSavingKey(key);
    setError(null);
    try {
      const updated = await satisfyPrerequisite(request.id, key);
      setMet(updated.prerequisitesMet ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't record that.");
    } finally {
      setSavingKey(null);
    }
  }

  // --- the announcement ---------------------------------------------------
  const name = subjectName(request, service);
  const composeDraft = useCallback(
    (slot: Slot) => {
      const who = name || request.serviceName;
      const at = resourceName ? `, at ${resourceName}` : "";
      return (
        `The service for ${who} is set for ${longDate(slot.startUtc, tz)} ` +
        `at ${shortTime(slot.startUtc, tz)}${at}. ` +
        `We will be in touch about the order of service. With our condolences.`
      );
    },
    [name, request.serviceName, resourceName, tz],
  );

  function pick(slot: Slot) {
    setSelected(slot);
    setError(null);
    // An owner who has typed keeps their words when they change their mind
    // about the date; an untouched draft re-writes itself to the new one.
    if (!draftEdited) setDraft(composeDraft(slot));
  }

  // The resource name lands a beat after the slots (two requests), so an
  // untouched draft written before it arrived is re-composed with the chapel in.
  useEffect(() => {
    if (selected && !draftEdited) setDraft(composeDraft(selected));
  }, [selected, draftEdited, composeDraft]);

  // --- commit -------------------------------------------------------------
  async function assign() {
    if (!selected || phase !== "idle") return;
    setError(null);
    setWarning(null);
    let approved = false;
    let scheduled = false;
    try {
      setPhase("approving");
      await approveBooking(request.id); // MUST be first: reschedule wants `confirmed`
      approved = true;
      setPhase("assigning");
      await rescheduleBooking(request.id, [selected.id]); // owner waiver: no cutoff check
      scheduled = true;
      setPhase("notifying");
      const convo = await startConversation(request.providerId, request.userId);
      await sendMessage(convo.id, draft.trim());
      setPhase("done");
      await onAssigned(
        `${name || request.serviceName} — ${longDate(selected.startUtc, tz)} at ${shortTime(selected.startUtc, tz)}. The family has been notified.`,
      );
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "That didn't go through. Try again.";
      if (scheduled) {
        // The date IS assigned; only the announcement failed. Saying "try
        // again" here would invite a second approve that 400s.
        setPhase("done");
        setWarning(`Date assigned, but the message didn't send: ${message} Send it from the inbox below.`);
        await onAssigned(
          `${name || request.serviceName} — ${longDate(selected.startUtc, tz)} at ${shortTime(selected.startUtc, tz)}. The family was NOT notified.`,
        );
        return;
      }
      setPhase("idle");
      setError(
        approved
          ? `Approved, but the date didn't take: ${message} The request is confirmed on its placeholder date — pick another.`
          : message,
      );
    }
  }

  // --- render -------------------------------------------------------------
  if (phase === "done") {
    return (
      <div className="mt-3 rounded-2xl border border-primary/30 bg-primary/5 p-3">
        <p className="flex items-center gap-1.5 text-sm font-medium text-primary">
          <Check className="size-4" aria-hidden /> Date assigned
        </p>
        {selected ? (
          <p className="mt-1 text-sm text-muted-foreground">
            {longDate(selected.startUtc, tz)} at {shortTime(selected.startUtc, tz)}{" "}
            {zoneAbbrev(selected.startUtc, tz)}
            {resourceName ? ` · ${resourceName}` : ""}
          </p>
        ) : null}
        {warning ? (
          <InlineMessage className="mt-2" tone="notice">
            {warning}
          </InlineMessage>
        ) : null}
      </div>
    );
  }

  const working = phase !== "idle";
  const grouped = groupByWeek(slots ?? [], service?.approvalWindowHours ?? FALLBACK_APPROVAL_WINDOW_HOURS);

  return (
    <div className="mt-3 space-y-3 rounded-2xl border border-border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Assign a date</p>
          <p className="text-xs text-muted-foreground">
            {resourceName ? `${resourceName} · ` : ""}dates the family does not choose.
          </p>
        </div>
        <Button variant="ghost" size="xs" isDisabled={working} onPress={onClose}>
          Close
        </Button>
      </div>

      {/* Step 1 — the paperwork. Nothing below is reachable until it is clear. */}
      {checklist.length > 0 ? (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Before confirming
          </p>
          <ul className="mt-1.5 space-y-1">
            {checklist.map((p) => {
              const done = met.includes(p.key);
              return (
                <li
                  key={p.key}
                  className="flex items-center justify-between gap-2 rounded-xl bg-card px-2.5 py-1.5 text-sm"
                >
                  <span className={cn("flex items-center gap-1.5", done && "text-muted-foreground line-through")}>
                    <SquareCheckBig
                      className={cn("size-3.5", done ? "text-primary" : "text-muted-foreground")}
                      aria-hidden
                    />
                    {p.label}
                  </span>
                  {done ? (
                    <span className="text-xs font-medium text-primary">On file</span>
                  ) : (
                    <Button
                      variant="outline"
                      size="xs"
                      isDisabled={savingKey !== null || working}
                      onPress={() => satisfy(p.key)}
                    >
                      {savingKey === p.key ? "Recording…" : "Mark received"}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
          {!cleared ? (
            <p className="mt-1.5 text-xs text-muted-foreground">
              {outstanding.length} outstanding. The date cannot be set until the file is complete.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Step 2 — the date itself. */}
      <div className={cn(checklist.length > 0 && !cleared && "pointer-events-none opacity-40")}>
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Open dates</p>
        {slots === null ? (
          <p className="mt-1.5 flex items-center gap-1.5 text-sm text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Checking the diary…
          </p>
        ) : slots.length === 0 ? (
          <p className="mt-1.5 text-sm text-muted-foreground">
            {loadError ?? "No open dates on this option. Add availability first."}
          </p>
        ) : (
          <div className="mt-1.5 space-y-2">
            {grouped.map((group) => (
              <div key={group.label}>
                <p className="text-[11px] text-muted-foreground">{group.label}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {group.slots.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      disabled={working}
                      onClick={() => pick(s)}
                      aria-pressed={selected?.id === s.id}
                      className={cn(
                        "rounded-xl border px-2.5 py-1 text-xs disabled:opacity-50",
                        buttonFx.tile,
                        selected?.id === s.id
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-card",
                      )}
                    >
                      {longDate(s.startUtc, tz)} · {shortTime(s.startUtc, tz)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Step 3 — the announcement, drafted but not sent. */}
      {selected ? (
        <div>
          <label
            htmlFor={`announce-${request.id}`}
            className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
          >
            Announcement to the family
          </label>
          <Textarea
            id={`announce-${request.id}`}
            value={draft}
            disabled={working}
            onChange={(e) => {
              setDraft(e.target.value);
              setDraftEdited(true);
            }}
            rows={4}
            className="mt-1"
          />
        </div>
      ) : null}

      {error ? <InlineMessage>{error}</InlineMessage> : null}

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          isDisabled={
            working || !selected || !draft.trim() || (checklist.length > 0 && !cleared)
          }
          onPress={assign}
        >
          {working ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
          {working ? PHASE_LABEL[phase as Exclude<Phase, "idle" | "done">] : "Confirm date & notify"}
        </Button>
        {!working && selected ? (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <CalendarDays className="size-3.5" aria-hidden />
            {longDate(selected.startUtc, tz)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** Split the open dates at the response window the config gives the business
 *  (`timing.approvalWindowHours`) — the premise is that the date lands inside
 *  it, so the ones that honour that are shown first and named as such. */
function groupByWeek(slots: Slot[], windowHours: number): { label: string; slots: Slot[] }[] {
  const edge = Date.now() + windowHours * 60 * 60 * 1000;
  const within = slots.filter((s) => new Date(s.startUtc).getTime() <= edge);
  const later = slots.filter((s) => new Date(s.startUtc).getTime() > edge);
  const out: { label: string; slots: Slot[] }[] = [];
  if (within.length) out.push({ label: `Within the response window (${Math.round(windowHours / 24)} days)`, slots: within });
  if (later.length) out.push({ label: "Later", slots: later });
  return out;
}
