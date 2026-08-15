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
import { createBooking, getAvailability, getResources, isApiError } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { CalendarView } from "@/components/calendar/calendar-view";
import { ConfirmScreen } from "@/components/booking/confirm-screen";
import { ResultScreen } from "@/components/booking/result-screen";
import { SelectionBar } from "@/components/booking/selection-bar";

type Phase = "browse" | "confirm" | "result";
const ms = (iso: string) => new Date(iso).getTime();

function validateSpan(span: Slot[], service: Service): string | null {
  if (span.length < 1) return "Nothing selected.";
  if (span.length > service.maxSlotsPerBooking)
    return `You can book up to ${service.maxSlotsPerBooking} in a row.`;
  for (const s of span) {
    if (s.status !== "available" && s.status !== "partially_booked")
      return "That range includes an unavailable time.";
  }
  for (let i = 1; i < span.length; i++) {
    if (ms(span[i].startUtc) !== ms(span[i - 1].endUtc))
      return "Selected times must be back-to-back with no gaps.";
  }
  return null;
}

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
  const { vertical } = useApp();
  const isRange = service.maxSlotsPerBooking > 1;

  const [phase, setPhase] = useState<Phase>("browse");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [start, setStart] = useState<Slot | null>(null);
  const [partySize, setPartySize] = useState(1);
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
      const problem = validateSpan(span, service);
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
      });
      setBooking(b);
      setPhase("result");
    } catch (e) {
      const msg = isApiError(e) ? e.message : "Couldn't complete the booking.";
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
