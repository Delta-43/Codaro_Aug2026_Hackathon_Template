// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * One label/value line in a booking summary.
 *
 * Shared by `booking-detail.tsx` and `confirm-screen.tsx`, which showed the
 * same list of facts (when, where, party size, price) through byte-identical
 * private copies of this component, so a spacing or type-scale tweak landed on
 * the confirm screen and not the detail view, or vice versa.
 */
export function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-medium">{value}</span>
    </div>
  );
}
