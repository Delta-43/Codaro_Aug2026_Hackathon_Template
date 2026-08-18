"use client";

/**
 * Full booking detail + the whole lifecycle: reschedule, cancel, and (once
 * completed) review. It owns the mutable booking — every mutation through the
 * API returns the updated row, which we swap in place, so nothing here refetches
 * or recomputes status. The cutoff greying-out is a client hint only; the
 * backend stays the authority and its ApiError messages are shown verbatim.
 */
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, CalendarClock, X } from "lucide-react";
import type { Booking, Provider, Service } from "@/types/domain";
import { useApp } from "@/context/app-context";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { StatusBadge } from "@/components/booking/status-badge";
import { CancelDialog } from "@/components/booking/cancel-dialog";
import { RescheduleFlow } from "@/components/booking/reschedule-flow";
import { ReviewForm } from "@/components/booking/review-form";
import {
  formatBookingWhen,
  formatCutoffPolicy,
  formatDate,
  formatMoney,
  formatSpan,
  formatTime,
  isWithinCutoff,
  zoneAbbrev,
} from "@/lib/format";
import { DetailRow } from "@/components/booking/detail-row";

export function BookingDetail({
  booking: initial,
  service,
  provider,
  resourceName,
  tz,
}: {
  booking: Booking;
  service: Service;
  provider: Provider;
  resourceName: string;
  tz: string;
}) {
  const { vertical } = useApp();
  const [booking, setBooking] = useState<Booking>(initial);
  const [mode, setMode] = useState<"detail" | "reschedule">("detail");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const withinCutoff = isWithinCutoff(booking.startUtc, service.cancellationCutoffHours);
  const canModify = booking.status === "confirmed" && !withinCutoff;
  const isShared = service.bookingModel === "shared_capacity";

  if (mode === "reschedule") {
    return (
      <RescheduleFlow
        booking={booking}
        service={service}
        tz={tz}
        onDone={(updated) => {
          setBooking(updated);
          setMode("detail");
          setNotice("Booking moved to the new time.");
        }}
        onCancel={() => setMode("detail")}
        onCutoff={(message) => {
          setMode("detail");
          setNotice(message);
        }}
      />
    );
  }

  const slotCount = booking.slotIds.length;
  const perSlot = service.priceMinorUnits;

  return (
    <section className="py-4">
      <Link
        href="/bookings"
        className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 mb-3")}
      >
        <ArrowLeft className="size-4" aria-hidden /> Bookings
      </Link>

      {/* Heading */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">{service.name}</h1>
          <p className="truncate text-sm text-muted-foreground">{provider.name}</p>
        </div>
        <StatusBadge status={booking.status} className="mt-1" />
      </div>

      {/* Reference */}
      <div className="mt-4 rounded-xl border border-border bg-card px-4 py-3">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Reference</p>
        <p className="font-mono text-lg font-semibold tracking-widest">{booking.reference}</p>
      </div>

      {notice ? (
        <div className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-border bg-muted px-3 py-2 text-sm">
          <span className="text-foreground/90">{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      ) : null}

      {/* Details */}
      <div className="mt-3 rounded-xl border border-border bg-card p-4">
        <DetailRow label={vertical.providerNoun} value={provider.name} />
        <DetailRow label={vertical.serviceNoun} value={service.name} />
        {resourceName ? <DetailRow label={vertical.resourceNoun} value={resourceName} /> : null}
        <div className="my-1 border-t border-border" />
        <DetailRow label="When" value={formatBookingWhen(booking.startUtc, booking.endUtc, tz)} />
        <DetailRow label="Duration" value={formatSpan(slotCount, service.slotDurationMinutes)} />
        <DetailRow
          label={isShared ? (vertical.partyNoun ?? "Party") : "Party"}
          value={`${booking.partySize}`}
        />
      </div>

      {/* Price */}
      <div className="mt-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-baseline justify-between py-1 text-sm text-muted-foreground">
          <span>
            {formatMoney(perSlot, booking.currency)} × {slotCount}
            {isShared ? ` × ${booking.partySize}` : ""}
          </span>
          <span>{formatMoney(booking.priceMinorUnits, booking.currency)}</span>
        </div>
        <div className="mt-1 flex items-baseline justify-between border-t border-border pt-2">
          <span className="text-sm font-semibold">Total</span>
          <span className="text-base font-semibold">
            {formatMoney(booking.priceMinorUnits, booking.currency)}
          </span>
        </div>
      </div>

      {/* Policy / cutoff */}
      {booking.status === "confirmed" ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {withinCutoff
            ? `Changes are closed — within ${service.cancellationCutoffHours}h of the start.`
            : formatCutoffPolicy(booking.startUtc, service.cancellationCutoffHours, tz)}
        </p>
      ) : null}

      {booking.status === "cancelled" && booking.cancelledAtUtc ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Cancelled on {formatDate(booking.cancelledAtUtc, tz, { weekday: true, withYear: true })}.
        </p>
      ) : null}

      {/* Change history */}
      {booking.changeHistory.length > 0 ? (
        <div className="mt-4">
          <h2 className="mb-2 text-sm font-semibold">History</h2>
          <ul className="space-y-2">
            {booking.changeHistory.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CalendarClock className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  Moved from{" "}
                  <span className="text-foreground">
                    {formatDate(c.fromStartUtc, tz, { weekday: true })},{" "}
                    {formatTime(c.fromStartUtc, tz)}
                  </span>{" "}
                  to{" "}
                  <span className="text-foreground">
                    {formatDate(c.toStartUtc, tz, { weekday: true })}, {formatTime(c.toStartUtc, tz)}{" "}
                    {zoneAbbrev(c.toStartUtc, tz)}
                  </span>
                  <span className="block text-xs">
                    on {formatDate(c.atUtc, tz, { weekday: true, withYear: true })}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Actions */}
      {canModify ? (
        <div className="mt-6 flex gap-2">
          <Button variant="outline" className="flex-1" onPress={() => setMode("reschedule")}>
            Reschedule
          </Button>
          <Button variant="destructive" className="flex-1" onPress={() => setCancelOpen(true)}>
            Cancel booking
          </Button>
        </div>
      ) : null}

      {/* Review (completed only, and only where reviews are enabled — the
          backend refuses the write, so showing this would 404 on submit).
          Read off THIS service, not the global block: the gate is per service. */}
      {booking.status === "completed" && service.capabilities.reviews !== false ? (
        <div className="mt-6">
          <ReviewForm booking={booking} tz={tz} onReviewed={setBooking} />
        </div>
      ) : null}

      <CancelDialog
        booking={booking}
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onCancelled={(updated) => {
          setBooking(updated);
          setCancelOpen(false);
          setNotice("Booking cancelled.");
        }}
      />
    </section>
  );
}
