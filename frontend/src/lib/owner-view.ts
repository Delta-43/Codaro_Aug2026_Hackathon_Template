/**
 * Adapters from the backend's owner shapes into the business-mode view shapes
 * the existing components consume (so the polished UI is reused verbatim, only
 * the data source changed — now 100% real `/owner/*` data).
 */
import type { DemoBooking } from "@/lib/business-demo";
import type { OwnerBooking } from "@/types/domain";

/** The customer's short name from their email local-part (owner-only field). */
function clientName(email?: string): string {
  const local = (email || "").split("@")[0];
  return local || "Guest";
}

/** Map an owner booking into the calendar's booking card. Only confirmed and
 *  completed reach the calendar; anything else is shown as confirmed. */
export function ownerBookingToCal(b: OwnerBooking, serviceName?: string): DemoBooking {
  const who = clientName(b.clientEmail);
  return {
    id: b.id,
    title: serviceName || who,
    client: who,
    serviceLabel: serviceName || "",
    startUtc: b.startUtc,
    endUtc: b.endUtc,
    status: b.status === "completed" ? "completed" : "confirmed",
    partySize: b.partySize,
    priceMinorUnits: b.priceMinorUnits,
    currency: b.currency,
    loan: b.loan,
    prerequisitesPending: b.prerequisitesPending,
    payment: b.payment,
  };
}
