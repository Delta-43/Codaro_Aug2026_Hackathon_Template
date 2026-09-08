// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Booking result — success mark, the reference in large monospace, a summary,
 * and two actions: View in Bookings and Done.
 */
import Link from "next/link";
import { Check } from "lucide-react";
import type { Booking, Service } from "@/types/domain";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { formatDate, formatMoney, formatTimeRange, zoneAbbrev } from "@/lib/format";
import { useApp } from "@/context/app-context";

export function ResultScreen({
  booking,
  service,
  tz,
  onDone,
}: {
  booking: Booking;
  service: Service;
  tz: string;
  onDone: () => void;
}) {
  const { copy, vertical } = useApp();
  // A `timing.confirmation: request_approve` pivot lands the booking as PENDING,
  // and this screen still said "You're booked" — the one moment the config has a
  // dedicated sentence for (`copy.requestPending`) was the moment it was wrong.
  // A quote request is a pending booking with a different meaning, and the
  // config has always carried its own sentence (`copy.quoteRequested`) — it was
  // just never rendered, so a quote-model deployment said "request sent" where
  // it meant "we'll price this and come back to you".
  const byQuote = service.pricingModel === "quote" && service.capabilities.quotes !== false;
  // `booking.granularity: "none"` + still pending: the slot on this booking is
  // the placeholder the flow resolved, not a date anyone has agreed to. Printing
  // it here would announce a date the business has not yet assigned.
  const dateHidden = booking.status === "pending" && service.granularity === "none";
  const headline =
    booking.status !== "pending"
      ? (copy.confirmTitle ?? "You're booked")
      : byQuote
        ? (copy.quoteRequested ?? "Your quote request has been sent")
        : (copy.requestPending ?? "Your request has been sent");
  return (
    <section className="flex flex-col items-center py-10 text-center">
      <div className="grid size-14 place-items-center rounded-full bg-primary/10 text-primary">
        <Check className="size-7" aria-hidden />
      </div>
      <h1 className="mt-4 text-xl font-semibold tracking-tight">{headline}</h1>

      {/* A repeating series: say exactly how many landed. A customer who asked
          for 12 and got 3 must not have to count their own bookings to find
          out — `skipped` is reported by the server for precisely this. */}
      {booking.series ? (
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">
          {booking.series.bookedIds.length} of {booking.series.requested}{" "}
          {booking.series.pattern} {vertical.bookingNounPlural.toLowerCase()} booked
          {booking.series.skipped.length
            ? ` — ${booking.series.skipped.length} had no availability and were skipped.`
            : "."}
        </p>
      ) : null}

      <p className="mt-4 text-xs uppercase tracking-wide text-muted-foreground">Reference</p>
      <p className="font-mono text-2xl font-semibold tracking-widest">{booking.reference}</p>

      <div className="mt-5 w-full max-w-sm rounded-xl border border-border bg-card p-4 text-left text-sm">
        <p className="pb-1 font-medium">{service.name}</p>
        {dateHidden ? (
          <div className="flex justify-between py-0.5">
            <span className="text-muted-foreground">Date</span>
            <span className="font-medium">To be confirmed</span>
          </div>
        ) : (
          <>
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Date</span>
              <span className="font-medium">
                {formatDate(booking.startUtc, tz, { weekday: true })}
              </span>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Time</span>
              <span className="font-medium">
                {formatTimeRange(booking.startUtc, booking.endUtc, tz)}{" "}
                {zoneAbbrev(booking.startUtc, tz)}
              </span>
            </div>
          </>
        )}
        {/* No money line where there is none to show: `payments.flow: "none"`
            carries no charge, and a quote request has not been priced yet — both
            rendered a "Total 0.00" that reads as a bug rather than as free. */}
        {service.paymentFlow !== "none" && !byQuote ? (
          <div className="flex justify-between py-0.5">
            <span className="text-muted-foreground">Total</span>
            <span className="font-medium">
              {formatMoney(booking.priceMinorUnits, booking.currency)}
            </span>
          </div>
        ) : null}
      </div>

      <div className="mt-6 flex w-full max-w-sm gap-2">
        <Link
          href={`/bookings/${booking.id}`}
          className={cn(buttonVariants({ variant: "default" }), "flex-1")}
        >
          View in Bookings
        </Link>
        <Button variant="outline" className="flex-1" onPress={onDone}>
          Done
        </Button>
      </div>
    </section>
  );
}
