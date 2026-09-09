// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Party split by band: `booking.party.composition`.
 *
 * The block declares what a party is made of (adult / child / senior) and what
 * each band costs as a multiple of the base rate (`priceFactor`). It shipped in
 * v2 with the pricing engine already able to weight it (`ctx.person_units`) and
 * no way to say how many of each: the app offered one flat number, so a family
 * of two adults and two children paid four adult fares.
 *
 * The counts ARE the party size: the total is reported upward rather than
 * edited separately, because the server rejects a party size that disagrees with
 * its bands (both numbers reach the engine; a mismatch means one is wrong).
 */
import { Minus, Plus } from "lucide-react";
import type { PartyBand } from "@/types/domain";
import { Button } from "@/components/ui/button";

export function PartyBands({
  bands,
  counts,
  max,
  onChange,
}: {
  bands: PartyBand[];
  counts: Record<string, number>;
  /** Remaining capacity across the selection, the whole party must fit. */
  max: number;
  onChange: (next: Record<string, number>) => void;
}) {
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);

  function set(key: string, next: number) {
    const clamped = Math.max(0, next);
    const others = total - (counts[key] ?? 0);
    if (others + clamped > max) return;
    onChange({ ...counts, [key]: clamped });
  }

  return (
    <div className="space-y-2">
      {bands.map((band) => {
        const count = counts[band.key] ?? 0;
        // A factor of exactly 1 is the norm and says nothing worth the space;
        // anything else is the reason this control exists, so it is labelled.
        const factor = band.priceFactor;
        return (
          <div key={band.key} className="flex items-center justify-between gap-4">
            <div className="text-sm">
              <div className="font-medium">{band.label}</div>
              {factor !== undefined && factor !== 1 ? (
                <div className="text-xs text-muted-foreground">
                  {Math.round(factor * 100)}% of the full rate
                </div>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="icon-sm"
                aria-label={`Fewer ${band.label}`}
                isDisabled={count <= 0}
                onPress={() => set(band.key, count - 1)}
              >
                <Minus className="size-4" aria-hidden />
              </Button>
              <span className="min-w-6 text-center text-sm font-semibold tabular-nums">
                {count}
              </span>
              <Button
                variant="outline"
                size="icon-sm"
                aria-label={`More ${band.label}`}
                isDisabled={total >= max}
                onPress={() => set(band.key, count + 1)}
              >
                <Plus className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
        );
      })}
      <p className="pt-1 text-xs text-muted-foreground">
        {total} of {max} places
      </p>
    </div>
  );
}
