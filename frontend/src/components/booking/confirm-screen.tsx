"use client";

/**
 * Confirmation — a full screen, not a dialog. Shows provider, service,
 * resource, date, start–end with timezone, duration, party size, an itemised
 * price and total, and the cancellation policy in words. Primary action is the
 * vertical's bookingVerb.
 */
import { ChevronLeft } from "lucide-react";
import type { Provider, Service, Slot } from "@/types/domain";
import type { VerticalConfig } from "@/config/verticals";
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-medium">{value}</span>
    </div>
  );
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
  const total = service.priceMinorUnits * slots.length * partySize;

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
        <Row label={vertical.providerNoun} value={provider.name} />
        <Row label={vertical.serviceNoun} value={service.name} />
        <Row label={vertical.resourceNoun} value={resourceName} />
        <div className="my-1 border-t border-border" />
        <Row label="Date" value={dateLabel} />
        <Row label="Time" value={timeLabel} />
        <Row label="Duration" value={formatSpan(slots.length, service.slotDurationMinutes)} />
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
          <Row label="Party" value={`${partySize}`} />
        )}
      </div>

      {/* Price */}
      <div className="mt-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-baseline justify-between py-1 text-sm text-muted-foreground">
          <span>
            {formatMoney(service.priceMinorUnits, service.currency)} × {slots.length}
            {isShared ? ` × ${partySize}` : ""}
          </span>
          <span>{formatMoney(total, service.currency)}</span>
        </div>
        <div className="mt-1 flex items-baseline justify-between border-t border-border pt-2">
          <span className="text-sm font-semibold">Total</span>
          <span className="text-base font-semibold">
            {formatMoney(total, service.currency)}
          </span>
        </div>
      </div>

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
