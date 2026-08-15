import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Booking } from "@/types/domain";
import { StatusBadge } from "@/components/booking/status-badge";
import { formatBookingWhen, formatMoney } from "@/lib/format";

/**
 * One row in the Bookings list. Deep-links to the detail screen. Provider and
 * service names are resolved by the list (bookings carry only ids), so they're
 * passed in rather than fetched here.
 */
export function BookingCard({
  booking,
  serviceName,
  providerName,
  tz,
}: {
  booking: Booking;
  serviceName: string;
  providerName: string;
  tz: string;
}) {
  return (
    <Link
      href={`/bookings/${booking.id}`}
      className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-muted/50"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium">{serviceName}</span>
          <StatusBadge status={booking.status} />
        </div>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">{providerName}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {formatBookingWhen(booking.startUtc, booking.endUtc, tz)}
        </p>
        <div className="mt-1 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
          <span className="font-mono">{booking.reference}</span>
          <span aria-hidden>·</span>
          <span>{formatMoney(booking.priceMinorUnits, booking.currency)}</span>
          {booking.partySize > 1 ? (
            <>
              <span aria-hidden>·</span>
              <span>party of {booking.partySize}</span>
            </>
          ) : null}
        </div>
      </div>
      <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden />
    </Link>
  );
}
