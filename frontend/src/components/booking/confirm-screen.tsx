// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

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
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { getQuote } from "@/api";
import { useApp } from "@/context/app-context";
import { useCart } from "@/context/cart-context";
import { Button } from "@/components/ui/button";
import { PartyStepper } from "@/components/booking/party-stepper";
import { PartyBands } from "@/components/booking/party-bands";
import { OptionsPicker } from "@/components/booking/options-picker";
import { FieldForm, type FieldValues } from "@/components/booking/field-form";
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
import { InlineMessage } from "@/components/ui/inline-message";


/** `location.modes` in words. The keys are the engine's; the sentence is ours. */
const LOCATION_LABELS: Record<string, string> = {
  on_site: "At the venue",
  at_customer: "At your address",
  remote: "Online",
  delivery: "Delivered to you",
  pickup: "Collected by you",
};

/** How far apart a sequence's sessions sit, in words. */
function sequenceGapLabel(minGapHours: number): string {
  if (!minGapHours) return "One after another";
  const days = Math.round(minGapHours / 24);
  if (days >= 7 && days % 7 === 0) {
    const weeks = days / 7;
    return `About one a week, ${weeks === 1 ? "a week" : `${weeks} weeks`} apart`;
  }
  return days >= 1 ? `${days} day${days === 1 ? "" : "s"} apart` : `${minGapHours}h apart`;
}

/** A `payments.schedule` step's due point, relative to the booking. Negative
 *  offsets are "before it starts", which is how a balance is usually written. */
function dueLabel(offsetHours: number | undefined): string {
  if (!offsetHours) return " · now";
  const hours = Math.abs(offsetHours);
  const span = hours % 24 === 0 ? `${hours / 24}d` : `${hours}h`;
  return offsetHours < 0 ? ` · ${span} before` : ` · ${span} after`;
}

export function ConfirmScreen({
  provider,
  service,
  resourceName,
  slots,
  tz,
  vertical,
  partySize,
  onPartyChange,
  partyBands,
  onPartyBandsChange,
  options,
  onOptionsChange,
  subject,
  onSubjectChange,
  metaValues,
  onMetaChange,
  repeatPattern,
  repeatPatterns,
  onRepeatPatternChange,
  repeatCount,
  onRepeatChange,
  bookSequence,
  onBookSequenceChange,
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
  /** `booking.party.composition` — heads per band. Replaces the flat stepper
   *  wherever the config declares bands, because the bands ARE the party size. */
  partyBands: Record<string, number>;
  onPartyBandsChange: (next: Record<string, number>) => void;
  /** `booking.options` — chosen paid extras, priced server-side. */
  options: Record<string, string | boolean>;
  onOptionsChange: (next: Record<string, string | boolean>) => void;
  /** `booking.subject` — who/what the booking is about. */
  subject: FieldValues;
  onSubjectChange: (next: FieldValues) => void;
  /** `metaFields.bookings` — the deployment's own declared fields. */
  metaValues: FieldValues;
  onMetaChange: (next: FieldValues) => void;
  /** The repeat pattern in force, and the patterns on offer (`recurrence`).
   *  Null when the service offers no repeat at all. */
  repeatPattern: string | null;
  repeatPatterns: string[];
  onRepeatPatternChange: (pattern: string) => void;
  repeatCount: number;
  onRepeatChange: (n: number) => void;
  /** `booking.sequence` — whether to book the whole course, not just step 1. */
  bookSequence: boolean;
  onBookSequenceChange: (on: boolean) => void;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onBack: () => void;
}) {
  const { metaFields, capability } = useApp();
  const cart = useCart();
  const first = slots[0];
  const last = slots[slots.length - 1];
  const bands = service.party.composition;
  const bookingFields = metaFields.bookings ?? [];
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
  // Bands, options and the subject all change the PRICE (weighted heads, add-on
  // lines, `subjectField` tiers), so they belong in the stamp — a stale total
  // after ticking "Full board" is the same bug as a stale total after a party
  // change, which is what this stamp exists to prevent.
  const shapeKey = JSON.stringify([partyBands, options, subject]);
  const quoteKey = `${service.id}|${slotKey}|${partySize}|${shapeKey}`;
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
      partyBands: bands.length ? partyBands : undefined,
      options,
      subject,
    })
      .then((q) => !cancelled && setResult({ key: quoteKey, quote: q }))
      .catch(() => !cancelled && setResult({ key: quoteKey, quote: null }));
    return () => {
      cancelled = true;
    };
  }, [service.id, slotKey, partySize, slots, quoteKey, bands.length, partyBands, options, subject]);

  const settled = result.key === quoteKey;
  const quote = settled ? result.quote : null;
  const quoteError = settled && result.quote === null;

  // `payments.flow` decides whether money is even due here. "invoice_after"
  // bills later and "none" means the product carries no payment at all —
  // labelling either "Total" beside a pay affordance was wrong.
  // `payments.flow` is one of prepay | pay_on_site | invoice_after | split |
  // none. The old branch tested for "deposit", which the schema has never
  // accepted, so it never fired: a split-payment or pay-on-site deployment was
  // labelled "Total" beside a pay-now affordance it does not have.
  const MONEY_LABELS: Record<string, string> = {
    prepay: "Due now",
    pay_on_site: "Due on arrival",
    invoice_after: "Billed after",
    split: "Total, paid in parts",
  };
  const moneyLabel = MONEY_LABELS[service.paymentFlow] ?? "Total";
  // `pricing.model: "quote"` + `capabilities.quotes` — the business prices this
  // by hand after seeing the request. The engine returns 0 for such a service,
  // which the price card would render as "Free"; the honest screen asks for a
  // quote instead of quoting one.
  const byQuote = service.pricingModel === "quote" && service.capabilities.quotes !== false;
  const blocking = service.prerequisites.filter((p) => p.blocksConfirmation);

  return (
    <section className="py-4">
      <button
        type="button"
        onClick={onBack}
        className={cn(
          "-ml-1 mb-3 inline-flex origin-left items-center gap-1 text-sm font-medium text-muted-foreground transition-all hover:text-foreground",
          buttonFx.press,
        )}
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
        {bands.length ? (
          // `party.composition` — the bands are the party size, so the flat
          // stepper is replaced rather than shown alongside it.
          <div className="py-2">
            <span className="text-sm text-muted-foreground">
              {vertical.partyNoun ?? "Party"}
            </span>
            <div className="mt-2">
              <PartyBands
                bands={bands}
                counts={partyBands}
                max={Math.max(1, maxParty)}
                onChange={onPartyBandsChange}
              />
            </div>
          </div>
        ) : isShared ? (
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
        {/* Where it happens (`location.modes`). Shown only where the deployment
            offers more than one way, since "on site" alone is not news. */}
        {service.locationModes.length > 1 ? (
          <DetailRow label="Where" value={LOCATION_LABELS[service.locationDefault] ?? service.locationDefault} />
        ) : null}
      </div>

      {/* Paid extras (`booking.options`) — priced into the quote below. */}
      {service.options.length ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">Extras</p>
          <OptionsPicker
            options={service.options}
            values={options}
            currency={service.currency}
            onChange={onOptionsChange}
          />
        </div>
      ) : null}

      {/* Who or what this is for (`booking.subject`). Required fields are
          enforced server-side; the asterisks here are the same contract. */}
      {service.subject.enabled && service.subject.fields.length ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">{service.subject.noun}</p>
          <FieldForm
            fields={service.subject.fields}
            values={subject}
            onChange={onSubjectChange}
            idPrefix="subject"
          />
        </div>
      ) : null}

      {/* `metaFields.bookings` — whatever this deployment additionally asks for.
          Validated server-side against the same descriptors. */}
      {bookingFields.length ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">Details</p>
          <FieldForm
            fields={bookingFields}
            values={metaValues}
            onChange={onMetaChange}
            idPrefix="meta"
          />
        </div>
      ) : null}

      {/* Priced by hand (`pricing.model: "quote"`): say so, and say what happens
          next, rather than showing a total the engine did not compute. */}
      {byQuote ? (
        <div className="mt-3 rounded-xl border border-border bg-card p-4">
          <p className="text-sm font-semibold">Price on request</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {provider.name} will send a price for this request before anything is
            confirmed or charged.
          </p>
        </div>
      ) : null}

      {/* Price — every line comes from the quote, so what is shown is charged. */}
      {!byQuote && service.paymentFlow !== "none" ? (
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
              {/* `payments.schedule` — when each part falls due. Display-only:
                  there is no PSP in this engine, but these are the terms the
                  customer is agreeing to, and hiding them was the problem. */}
              {service.paymentSchedule.length ? (
                <div className="mt-2 border-t border-border pt-2">
                  {service.paymentSchedule.map((step) => (
                    <div
                      key={step.key}
                      className="flex items-baseline justify-between py-0.5 text-xs text-muted-foreground"
                    >
                      <span>{step.label ?? step.key}</span>
                      <span>
                        {step.kind === "percent"
                          ? `${step.value}%`
                          : formatMoney(step.value, quote.currency)}
                        {dueLabel(step.dueOffsetHours)}
                      </span>
                    </div>
                  ))}
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

      {/* The whole course, bought at once (`booking.sequence`). Later sessions
          are best-effort on the server exactly like a repeat: they land where
          the business opened a slot, and the response names any that did not. */}
      {service.sequence.enabled && service.sequence.steps > 1 ? (
        <div className="mt-3 flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
          <label htmlFor="book-sequence" className="text-sm">
            <div className="font-medium">
              Book all {service.sequence.steps} {vertical.slotNounPlural.toLowerCase()}
            </div>
            <div className="text-muted-foreground">
              {sequenceGapLabel(service.sequence.minGapHours)}
            </div>
          </label>
          <input
            id="book-sequence"
            type="checkbox"
            checked={bookSequence}
            onChange={(e) => onBookSequenceChange(e.target.checked)}
            className="size-4 accent-primary"
          />
        </div>
      ) : null}

      {/* Repeat — `recurrence`. Later occurrences are best-effort on the server:
          they land only where the business actually opened a slot, and the
          response names any that could not be booked. */}
      {repeatPattern ? (
        <div className="mt-3 flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
          <div className="text-sm">
            {repeatPatterns.length > 1 ? (
              // A config listing weekly + biweekly + monthly used to book the
              // first one silently; the other two were unreachable.
              <label className="flex items-center gap-2 font-medium">
                Repeat
                <select
                  value={repeatPattern}
                  onChange={(e) => onRepeatPatternChange(e.target.value)}
                  className="h-8 rounded-2xl border border-transparent bg-input/50 px-2.5 text-sm"
                >
                  {repeatPatterns.map((pattern) => (
                    <option key={pattern} value={pattern}>
                      {pattern}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <div className="font-medium">Repeat {repeatPattern}</div>
            )}
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
        <InlineMessage className="mt-3">{error}</InlineMessage>
      ) : null}

      <div className="mt-5 flex gap-2">
        <Button variant="outline" className="flex-1" isDisabled={busy} onPress={onBack}>
          Back
        </Button>
        <Button className="flex-1" isDisabled={busy} onPress={onConfirm}>
          {busy ? "Working…" : byQuote ? "Request a quote" : vertical.bookingVerb}
        </Button>

        {/* `capabilities.cart` — keep this selection and go and pick another.
            Nothing is held: the basket is a list of intents, and each one is
            re-priced and re-checked when it is actually booked. */}
        {capability("cart") && !byQuote ? (
          <Button
            variant="outline"
            className="mt-2 w-full"
            isDisabled={busy || !quote}
            onPress={() => {
              if (!quote) return;
              cart.add({
                serviceId: service.id,
                serviceName: service.name,
                providerName: provider.name,
                resourceId: first.resourceId,
                resourceName,
                slotIds: slots.map((s) => s.id),
                startUtc: first.startUtc,
                endUtc: last.endUtc,
                partySize,
                partyBands: bands.length ? partyBands : undefined,
                options,
                subject,
                metadata: metaValues,
                amountMinorUnits: quote.amountMinorUnits,
                currency: quote.currency,
              });
              onBack();
            }}
          >
            Add to basket
          </Button>
        ) : null}
      </div>
    </section>
  );
}
