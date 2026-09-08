// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Move an existing booking to new times. Selection mirrors the create flow
 * (single-slot services confirm on tap; range services build a contiguous span)
 * but is pinned to the booking's own resource and party size — the two things
 * reschedule can't change — and commits via rescheduleBooking. The backend is
 * atomic (acquire new, release old) and re-checks the cutoff, so on
 * CUTOFF_PASSED we surface its message and bounce back to the detail screen; on
 * SLOT_UNAVAILABLE / CAPACITY_EXCEEDED we refresh availability and let the user
 * re-pick.
 */
import { useMemo, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { useVertical } from "@/context/app-context";
import type { Booking, Service, Slot } from "@/types/domain";
import { getAvailability, getResources, isApiError, rescheduleBooking } from "@/api";
import { useAsync } from "@/hooks/use-async";
import { CalendarView } from "@/components/calendar/calendar-view";
import { SelectionBar } from "@/components/booking/selection-bar";
import { Button } from "@/components/ui/button";
import { formatBookingWhen, formatSpan, ms } from "@/lib/format";
import { validateSpan } from "@/lib/slot-span";
import { InlineMessage } from "@/components/ui/inline-message";

export function RescheduleFlow({
  booking,
  service,
  tz,
  onDone,
  onCancel,
  onCutoff,
}: {
  booking: Booking;
  service: Service;
  tz: string;
  onDone: (updated: Booking) => void;
  onCancel: () => void;
  /** CUTOFF_PASSED came back mid-flow — bubble the message up to the detail. */
  onCutoff: (message: string) => void;
}) {
  const vertical = useVertical();
  const isRange = service.maxSlotsPerBooking > 1;

  const [slots, setSlots] = useState<Slot[]>([]);
  const [start, setStart] = useState<Slot | null>(null);
  const [phase, setPhase] = useState<"pick" | "confirm">("pick");
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);

  const resources = useAsync(() => getResources(service.id), [service.id]);
  const resourceName = resources.data?.find((r) => r.id === booking.resourceId)?.name ?? "";
  const selectedIds = useMemo(() => new Set(slots.map((s) => s.id)), [slots]);

  function resetSelection() {
    setSlots([]);
    setStart(null);
    setRangeError(null);
  }

  async function handleSelect(slot: Slot) {
    setBanner(null);
    if (!isRange) {
      setSlots([slot]);
      setConfirmError(null);
      setPhase("confirm");
      return;
    }
    setRangeError(null);
    if (!start || slot.resourceId !== start.resourceId || ms(slot.startUtc) <= ms(start.startUtc)) {
      setStart(slot);
      setSlots([slot]);
      return;
    }
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

  async function commit() {
    if (busy || slots.length === 0) return;
    setBusy(true);
    setConfirmError(null);
    try {
      const updated = await rescheduleBooking(
        booking.id,
        slots.map((s) => s.id),
      );
      onDone(updated);
    } catch (e) {
      const msg = isApiError(e) ? e.message : "Couldn't move this booking.";
      if (isApiError(e) && e.code === "CUTOFF_PASSED") {
        onCutoff(msg);
        return;
      }
      if (isApiError(e) && (e.code === "SLOT_UNAVAILABLE" || e.code === "CAPACITY_EXCEEDED")) {
        setBanner(msg);
        resetSelection();
        setReloadKey((k) => k + 1);
        setPhase("pick");
      } else {
        setConfirmError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  const first = slots[0];
  const last = slots[slots.length - 1];

  if (phase === "confirm" && first) {
    return (
      <section className="py-4">
        <button
          type="button"
          onClick={() => {
            setPhase("pick");
            if (!isRange) resetSelection();
          }}
          className={cn(
            "-ml-1 mb-3 inline-flex origin-left items-center gap-1 text-sm font-medium text-muted-foreground transition-all hover:text-foreground",
            buttonFx.press,
          )}
        >
          <ChevronLeft className="size-4" aria-hidden /> Back
        </button>

        <h1 className="text-xl font-semibold tracking-tight">Confirm new time</h1>

        <div className="mt-4 rounded-xl border border-border bg-card p-4 text-sm">
          <div className="flex items-baseline justify-between gap-4 py-1">
            <span className="text-muted-foreground">Current</span>
            <span className="text-right font-medium line-through decoration-muted-foreground/60">
              {formatBookingWhen(booking.startUtc, booking.endUtc, tz)}
            </span>
          </div>
          <div className="flex items-baseline justify-between gap-4 py-1">
            <span className="text-muted-foreground">New</span>
            <span className="text-right font-medium">
              {formatBookingWhen(first.startUtc, last.endUtc, tz)}
            </span>
          </div>
          <div className="my-1 border-t border-border" />
          <div className="flex items-baseline justify-between gap-4 py-1">
            <span className="text-muted-foreground">Duration</span>
            <span className="text-right font-medium">
              {formatSpan(slots.length, service.slotDurationMinutes)}
            </span>
          </div>
          {resourceName ? (
            <div className="flex items-baseline justify-between gap-4 py-1">
              <span className="text-muted-foreground">Kept on</span>
              <span className="text-right font-medium">{resourceName}</span>
            </div>
          ) : null}
        </div>

        {confirmError ? (
          <InlineMessage className="mt-3">{confirmError}</InlineMessage>
        ) : null}

        <div className="mt-5 flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            isDisabled={busy}
            onPress={() => {
              setPhase("pick");
              if (!isRange) resetSelection();
            }}
          >
            Back
          </Button>
          <Button className="flex-1" isDisabled={busy} onPress={commit}>
            {busy ? "Moving…" : "Confirm move"}
          </Button>
        </div>
      </section>
    );
  }

  return (
    <div className="py-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Move {vertical.bookingNoun.toLowerCase()}</h1>
          <p className="text-sm text-muted-foreground">
            Pick a new time · {service.name}
            {resourceName ? ` · ${resourceName}` : ""}
          </p>
        </div>
        <Button variant="ghost" size="sm" isDisabled={busy} onPress={onCancel}>
          Cancel
        </Button>
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
        resourceId={booking.resourceId}
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
