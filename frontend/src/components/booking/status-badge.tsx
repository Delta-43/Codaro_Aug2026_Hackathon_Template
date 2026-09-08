// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { BookingStatus } from "@/types/domain";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

/**
 * Small status pill for a booking. Reads `booking.status` as returned by the
 * API, which already normalizes a finished `confirmed` booking to `completed`,
 * so the badge never has to recompute time.
 */
const STATUS: Record<BookingStatus, { label: string; className: string }> = {
  confirmed: {
    label: "Confirmed",
    className: "bg-primary/10 text-primary",
  },
  completed: {
    label: "Completed",
    className: "bg-muted text-muted-foreground",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-destructive/10 text-destructive",
  },
  pending: {
    label: "Pending",
    className: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  rejected: {
    label: "Declined",
    className: "bg-destructive/10 text-destructive",
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: BookingStatus;
  className?: string;
}) {
  const s = STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium transition-transform",
        buttonFx.press,
        s.className,
        className,
      )}
    >
      {s.label}
    </span>
  );
}
