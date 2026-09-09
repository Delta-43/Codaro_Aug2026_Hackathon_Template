// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Party-size stepper for shared_capacity, capped at remaining capacity. */
export function PartyStepper({
  value,
  min = 1,
  max,
  unit,
  onChange,
}: {
  value: number;
  min?: number;
  max: number;
  unit: string;
  onChange: (n: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Fewer"
        isDisabled={value <= min}
        onPress={() => onChange(Math.max(min, value - 1))}
      >
        <Minus className="size-4" aria-hidden />
      </Button>
      <span className="min-w-6 text-center text-sm font-semibold tabular-nums">{value}</span>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="More"
        isDisabled={value >= max}
        onPress={() => onChange(Math.min(max, value + 1))}
      >
        <Plus className="size-4" aria-hidden />
      </Button>
      <span className="text-sm text-muted-foreground">
        {unit}
        {max ? <span className="text-xs"> · {max} max</span> : null}
      </span>
    </div>
  );
}
