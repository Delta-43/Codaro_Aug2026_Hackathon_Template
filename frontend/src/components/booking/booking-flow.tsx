"use client";

/**
 * Selection → confirmation → create → result, wrapped around the calendar.
 * Single-slot services open confirmation on tap; range services (maxSlots > 1)
 * use tap-start / tap-end to build a contiguous span (validated inline, no
 * modal) with a running total. On SLOT_UNAVAILABLE the user stays on the
 * calendar: a banner explains, availability refreshes, other choices survive.
 */
import { useMemo, useState } from "react";
import type { Booking, Provider, Resource, Service, Slot } from "@/types/domain";
import { createBooking, getAvailability, getResources, isApiError, joinWaitlist } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { CalendarView } from "@/components/calendar/calendar-view";
import { ConfirmScreen } from "@/components/booking/confirm-screen";
import { ResultScreen } from "@/components/booking/result-screen";
import { SelectionBar } from "@/components/booking/selection-bar";
import { ms } from "@/lib/format";
import { validateSpan } from "@/lib/slot-span";

type Phase = "browse" | "confirm" | "result";

export function BookingFlow({
  provider,
  service,
  resource,
  tz,
}: {
  provider: Provider;
  service: Service;
  resource: Resource | null;
  tz: string;
}) {
  const { vertical, copy } = useApp();
  const isRange = service.maxSlotsPerBooking > 1;

  const [phase, setPhase] = useState<Phase>("browse");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [start, setStart] = useState<Slot | null>(null);
  const [partySize, setPartySize] = useState(1);
  // Repeat count, 1 = no repeat. Only offered where the config enables
  // `recurrence` AND the capability is on; every other deployment never sees it.
  const [repeatCount, setRepeatCount] = useState(1);
  // The engine accepts one pattern per series; offering the first declared one
  // keeps the control a single stepper rather than a pattern picker nobody asked
  // for. A config listing several still books the first.
  const repeatPattern = service.recurrence.enabled
    ? (service.recurrence.patterns[0] ?? null)
    : null;
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [booking, setBooking] = useState<Booking | null>(null);

  const resources = useAsync(() => getResources(service.id), [service.id]);
  const nameFor = (id: string) => resources.data?.find((r) => r.id === id)?.name ?? "";
  const selectedIds = useMemo(() => new Set(slots.map((s) => s.id)), [slots]);

  function resetSelection() {
    setSlots([]);
    setStart(null);
    setRangeError(null);
    setPartySize(1);
  }

  async function handleSelect(slot: Slot) {
    setBanner(null);
    if (!isRange) {
      setSlots([slot]);
      setPartySize(1);
      setConfirmError(null);
      setPhase("confirm");
      return;
    }
    setRangeError(null);
    // Start (or restart) the range when there's no anchor, a different
    // resource, or a tap at/before the anchor.
    if (!start || slot.resourceId !== start.resourceId || ms(slot.startUtc) <= ms(start.startUtc)) {
      setStart(slot);
      setSlots([slot]);
      return;
    }
    // Second tap: build the contiguous span on the anchor's resource.
    try {
      const avail = await getAvailability({
        serviceId: service.id,
        resourceId: start.resourceId,
        fromUtc: start.startUtc,
        toUtc: slot.endUtc,
      });
      const span = avail
        .flatMap((d) => d.slots)
        .filter((s) => s.resourceId === start.resourceId)
        .sort((a, b) => ms(a.startUtc) - ms(b.startUtc));
      const problem = validateSpan(span, service, vertical.slotNounPlural);
      if (problem) {
        setRangeError(problem);
        return;
      }
      setSlots(span);
    } catch {
      setRangeError("Couldn't build that range. Try again.");
    }
  }

  async function confirm() {
    if (busy || slots.length === 0) return;
    setBusy(true);
    setConfirmError(null);
    try {
      const b = await createBooking({
        serviceId: service.id,
        resourceId: slots[0].resourceId,
        slotIds: slots.map((s) => s.id),
        partySize,
        repeat:
          repeatCount > 1 && repeatPattern
            ? { pattern: repeatPattern, count: repeatCount }
            : undefined,
      });
      setBooking(b);
      setPhase("result");
    } catch (e) {
      const msg = isApiError(e) ? e.message : `Couldn't complete the ${vertical.bookingNoun.toLowerCase()}.`;
      if (isApiError(e) && (e.code === "SLOT_UNAVAILABLE" || e.code === "CAPACITY_EXCEEDED")) {
        setBanner(msg);
        resetSelection();
        setReloadKey((k) => k + 1);
        setPhase("browse");
      } else {
        setConfirmError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  /** Take a place in the queue for a full slot. Feedback goes through the same
   *  banner the calendar already uses for "that slot was just taken", so the
   *  flow gains no new UI state for a rare action. */
  async function joinQueue(slot: Slot) {
    try {
      const entry = await joinWaitlist(slot.id);
      setBanner(
        entry.peopleAhead
          ? `You're on the waitlist — ${entry.peopleAhead} ahead of you.`
          : (copy.waitlistJoined ?? "You're on the waitlist."),
      );
    } catch (e) {
      setBanner(isApiError(e) ? e.message : "Couldn't join the waitlist.");
    }
  }

  function done() {
    setBooking(null);
    resetSelection();
    setReloadKey((k) => k + 1); // reflect the decremented capacity
    setPhase("browse");
  }

  if (phase === "result" && booking) {
    return <ResultScreen booking={booking} service={service} tz={tz} onDone={done} />;
  }

  if (phase === "confirm") {
    return (
      <ConfirmScreen
        provider={provider}
        service={service}
        resourceName={nameFor(slots[0]?.resourceId ?? "")}
        slots={slots}
        tz={tz}
        vertical={vertical}
        partySize={partySize}
        onPartyChange={setPartySize}
        repeatPattern={repeatPattern}
        repeatCount={repeatCount}
        onRepeatChange={setRepeatCount}
        busy={busy}
        error={confirmError}
        onConfirm={confirm}
        onBack={() => {
          setPhase("browse");
          if (!isRange) resetSelection();
        }}
      />
    );
  }

  return (
    <div>
      <div className="mb-3">
        <h1 className="text-lg font-semibold tracking-tight">{service.name}</h1>
        <p className="text-sm text-muted-foreground">
          {provider.name}
          {resource ? ` · ${resource.name}` : ""}
        </p>
      </div>

      {banner ? (
        <div
          role="alert"
          className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300"
        >
          {banner}
        </div>
      ) : null}

      <CalendarView
        service={service}
        resourceId={resource?.id ?? null}
        tz={tz}
        selectedIds={selectedIds}
        onSelect={handleSelect}
        onWaitlist={service.waitlist.enabled ? joinQueue : undefined}
        reloadKey={reloadKey}
      />

      {isRange && slots.length > 0 ? (
        <SelectionBar
          service={service}
          slots={slots}
          error={rangeError}
          onContinue={() => {
            setConfirmError(null);
            setPhase("confirm");
          }}
          onClear={resetSelection}
        />
      ) : isRange && rangeError ? (
        <p className="mt-2 text-sm text-destructive">{rangeError}</p>
      ) : null}
    </div>
  );
}
