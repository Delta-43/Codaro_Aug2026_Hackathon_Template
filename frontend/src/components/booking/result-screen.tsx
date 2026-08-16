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
  return (
    <section className="flex flex-col items-center py-10 text-center">
      <div className="grid size-14 place-items-center rounded-full bg-primary/10 text-primary">
        <Check className="size-7" aria-hidden />
      </div>
      <h1 className="mt-4 text-xl font-semibold tracking-tight">You&apos;re booked</h1>

      <p className="mt-4 text-xs uppercase tracking-wide text-muted-foreground">Reference</p>
      <p className="font-mono text-2xl font-semibold tracking-widest">{booking.reference}</p>

      <div className="mt-5 w-full max-w-sm rounded-xl border border-border bg-card p-4 text-left text-sm">
        <div className="flex justify-between py-0.5">
          <span className="text-muted-foreground">{service.name}</span>
        </div>
        <div className="flex justify-between py-0.5">
          <span className="text-muted-foreground">Date</span>
          <span className="font-medium">
            {formatDate(booking.startUtc, tz, { weekday: true })}
          </span>
        </div>
        <div className="flex justify-between py-0.5">
          <span className="text-muted-foreground">Time</span>
          <span className="font-medium">
            {formatTimeRange(booking.startUtc, booking.endUtc, tz)} {zoneAbbrev(booking.startUtc, tz)}
          </span>
        </div>
        <div className="flex justify-between py-0.5">
          <span className="text-muted-foreground">Total</span>
          <span className="font-medium">
            {formatMoney(booking.priceMinorUnits, booking.currency)}
          </span>
        </div>
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
