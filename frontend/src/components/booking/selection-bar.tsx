// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

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
  // No total here any more. This bar renders on every slot click, so quoting it
  // would fire a request per tap, and the only number it could compute without
  // one is `priceMinorUnits * slots`, the default-block formula that misprices
  // every tiered/per-person/per-hour service. The confirm screen quotes once,
  // authoritatively; a "from" rate is honest at this stage and cannot mislead.
  const showsRate = service.paymentFlow !== "none" && service.pricingModel === "fixed";
  return (
    <div className="sticky bottom-16 z-20 mt-3 rounded-xl border border-border bg-card p-3 shadow-lg md:bottom-3">
      {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm">
          <div className="font-medium">
            {formatSpan(slots.length, service.slotDurationMinutes)}
          </div>
          {showsRate ? (
            <div className="text-muted-foreground">
              {formatMoney(service.priceMinorUnits * slots.length, service.currency)}
            </div>
          ) : null}
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
