"use client";

/**
 * Confirmation — a full screen, not a dialog. Shows provider, service,
 * resource, date, start–end with timezone, duration, party size, an itemised
 * price and total, and the cancellation policy in words. Primary action is the
 * vertical's bookingVerb.
 */
import { useEffect, useState } from "react";
import { ChevronLeft } from "lucide-react";
import type { Provider, Quote, Service, Slot } from "@/types/domain";
import type { VerticalConfig } from "@/config/verticals";
import { getQuote } from "@/api";
import { Button } from "@/components/ui/button";
import { PartyStepper } from "@/components/booking/party-stepper";
import {
  formatCutoffPolicy,
  formatDate,
  formatMoney,
  formatSpan,
  formatTimeRange,
  zoneAbbrev,
} from "@/lib/format";
import { slotRemaining } from "@/components/calendar/slot-pill";
import { DetailRow } from "@/components/booking/detail-row";

export function ConfirmScreen({
  provider,
  service,
  resourceName,
  slots,
  tz,
  vertical,
  partySize,
  onPartyChange,
  repeatPattern,
  repeatCount,
  onRepeatChange,
  busy,
  error,
  onConfirm,
  onBack,
}: {
  provider: Provider;
  service: Service;
  resourceName: string;
  slots: Slot[];
  tz: string;
  vertical: VerticalConfig;
  partySize: number;
  onPartyChange: (n: number) => void;
  /** Non-null only when the service offers a repeat (`recurrence`). */
  repeatPattern: string | null;
  repeatCount: number;
  onRepeatChange: (n: number) => void;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onBack: () => void;
}) {
  const first = slots[0];
  const last = slots[slots.length - 1];
  const isShared = service.bookingModel === "shared_capacity";
  const maxParty = Math.min(...slots.map(slotRemaining));

  const sameDay = formatDate(first.startUtc, tz) === formatDate(last.startUtc, tz);
  const dateLabel = sameDay
    ? formatDate(first.startUtc, tz, { weekday: true })
    : `${formatDate(first.startUtc, tz, { weekday: true })} – ${formatDate(last.startUtc, tz, { weekday: true })}`;
  const timeLabel = `${formatTimeRange(first.startUtc, last.endUtc, tz)} ${zoneAbbrev(first.startUtc, tz)}`;

  // The authoritative total comes from the engine that will charge it. The old
  // `priceMinorUnits * slots * party` here is only the DEFAULT pricing block's
  // formula: on a tiered service it showed 45000 where the API charged 12000.
  // Re-quoted whenever the selection or party size changes.
  const slotKey = slots.map((s) => s.id).join(",");
  // Stamped with the inputs it was quoted for. A bare `quote` would keep showing
  // the previous total while a re-quote is in flight after a party change —
  // displaying a stale price is the exact bug this component is fixing, so the
  // result is only rendered when its stamp still matches the selection.
  const quoteKey = `${service.id}|${slotKey}|${partySize}`;
  const [result, setResult] = useState<{ key: string; quote: Quote | null }>({
    key: "",
    quote: null,
  });
  useEffect(() => {
    let cancelled = false;
    getQuote({
      serviceId: service.id,
      resourceId: slots[0].resourceId,
      slotIds: slots.map((s) => s.id),
      partySize,
    })
      .then((q) => !cancelled && setResult({ key: quoteKey, quote: q }))
      .catch(() => !cancelled && setResult({ key: quoteKey, quote: null }));
    return () => {
      cancelled = true;
    };
  }, [service.id, slotKey, partySize, slots, quoteKey]);

  const settled = result.key === quoteKey;
  const quote = settled ? result.quote : null;
  const quoteError = settled && result.quote === null;

  // `payments.flow` decides whether money is even due here. "invoice_after"
  // bills later and "none" means the product carries no payment at all —
  // labelling either "Total" beside a pay affordance was wrong.
  const moneyLabel =
    service.paymentFlow === "invoice_after"
      ? "Billed after"
      : service.paymentFlow === "deposit"
        ? "Due now"
        : "Total";
  const blocking = service.prerequisites.filter((p) => p.blocksConfirmation);

  return (
    <section className="py-4">
      <button
        type="button"
        onClick={onBack}
        className="-ml-1 mb-3 inline-flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" aria-hidden /> Back
      </button>

      <h1 className="text-xl font-semibold tracking-tight">Confirm</h1>

      <div className="mt-4 rounded-xl border border-border bg-card p-4">
        <DetailRow label={vertical.providerNoun} value={provider.name} />
        <DetailRow label={vertical.serviceNoun} value={service.name} />
        <DetailRow label={vertical.resourceNoun} value={resourceName} />
        <div className="my-1 border-t border-border" />
        <DetailRow label="Date" value={dateLabel} />
        <DetailRow label="Time" value={timeLabel} />
        <DetailRow label="Duration" value={formatSpan(slots.length, service.slotDurationMinutes)} />
        {isShared ? (
          <div className="flex items-center justify-between gap-4 py-2">
            <span className="text-sm text-muted-foreground">
              {vertical.partyNoun ?? "Party"}
            </span>
            <PartyStepper
              value={partySize}
              max={Math.max(1, maxParty)}
              unit={vertical.partyNoun ?? "guests"}
              onChange={onPartyChange}
            />
          </div>
        ) : (
          <DetailRow label="Party" value={`${partySize}`} />
        )}
      </div>

      {/* Price — every line comes from the quote, so what is shown is charged. */}
      {service.paymentFlow !== "none" ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          {quote ? (
            <>
              {quote.breakdown.map((line, i) => (
                <div
                  key={`${line.label}-${i}`}
                  className="flex items-baseline justify-between py-1 text-sm text-muted-foreground"
                >
                  <span>{line.label}</span>
                  <span>{formatMoney(line.amountMinorUnits, quote.currency)}</span>
                </div>
              ))}
              <div className="mt-1 flex items-baseline justify-between border-t border-border pt-2">
                <span className="text-sm font-semibold">{moneyLabel}</span>
                <span className="text-base font-semibold">
                  {formatMoney(quote.amountMinorUnits, quote.currency)}
                </span>
              </div>
              {quote.depositMinorUnits > 0 ? (
                <div className="mt-1 flex items-baseline justify-between text-sm">
                  <span className="text-muted-foreground">Deposit due now</span>
                  <span className="font-medium">
                    {formatMoney(quote.depositMinorUnits, quote.currency)}
                  </span>
                </div>
              ) : null}
              {service.billingCycle !== "none" ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  Billed {service.billingCycle}.
                </p>
              ) : null}
            </>
          ) : quoteError ? (
            // Never fall back to arithmetic here: a wrong number is worse than
            // none, because the customer would take it as the price.
            <p className="text-sm text-muted-foreground">
              Price unavailable — it will be confirmed when you {vertical.bookingVerb.toLowerCase()}.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Pricing…</p>
          )}
        </div>
      ) : null}

      {/* Repeat — `recurrence`. Later occurrences are best-effort on the server:
          they land only where the business actually opened a slot, and the
          response names any that could not be booked. */}
      {repeatPattern ? (
        <div className="mt-3 flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
          <div className="text-sm">
            <div className="font-medium">Repeat {repeatPattern}</div>
            <div className="text-muted-foreground">
              {repeatCount > 1
                ? `${repeatCount} ${vertical.bookingNounPlural.toLowerCase()} in total`
                : "Just this one"}
            </div>
          </div>
          <PartyStepper
            value={repeatCount}
            max={Math.max(1, service.recurrence.maxOccurrences)}
            unit="times"
            onChange={onRepeatChange}
          />
        </div>
      ) : null}

      {blocking.length ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          <p className="text-sm font-semibold">Before this can be confirmed</p>
          <ul className="mt-1 space-y-1">
            {blocking.map((p) => (
              <li key={p.key} className="text-sm text-muted-foreground">
                {p.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="mt-3 text-sm text-muted-foreground">
        {formatCutoffPolicy(first.startUtc, service.cancellationCutoffHours, tz)}
      </p>

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}

      <div className="mt-5 flex gap-2">
        <Button variant="outline" className="flex-1" isDisabled={busy} onPress={onBack}>
          Back
        </Button>
        <Button className="flex-1" isDisabled={busy} onPress={onConfirm}>
          {busy ? "Working…" : vertical.bookingVerb}
        </Button>
      </div>
    </section>
  );
}
