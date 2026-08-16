"use client";

import type { Service, Slot } from "@/types/domain";
import { Button } from "@/components/ui/button";
import { formatMoney, formatSpan } from "@/lib/format";

/** Sticky running total for multi-slot range selection. */
export function SelectionBar({
  service,
  slots,
  error,
  onContinue,
  onClear,
}: {
  service: Service;
  slots: Slot[];
  error: string | null;
  onContinue: () => void;
  onClear: () => void;
}) {
  const total = service.priceMinorUnits * slots.length; // party applied at confirm
  return (
    <div className="sticky bottom-16 z-20 mt-3 rounded-xl border border-border bg-card p-3 shadow-lg md:bottom-3">
      {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm">
          <div className="font-medium">
            {formatSpan(slots.length, service.slotDurationMinutes)}
          </div>
          <div className="text-muted-foreground">{formatMoney(total, service.currency)}</div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onPress={onClear}>
            Clear
          </Button>
          <Button size="sm" onPress={onContinue}>
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
