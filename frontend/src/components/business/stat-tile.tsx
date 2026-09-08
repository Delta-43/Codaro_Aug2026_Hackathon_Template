// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * A glanceable metric in the dashboard's numbers strip. The value alone can be
 * abstract ("+7%"?), so hovering (desktop) or tapping (mobile) reveals a plain
 * explanation of what the number means and how it's derived.
 */
import { useState } from "react";
import { Info, TrendingDown, TrendingUp } from "lucide-react";
import type { Metric } from "@/lib/business-view";
import { cn } from "@/lib/utils";

export function StatTile({ metric }: { metric: Metric }) {
  const [open, setOpen] = useState(false);

  const toneClass =
    metric.tone === "up"
      ? "text-emerald-600 dark:text-emerald-400"
      : metric.tone === "down"
        ? "text-destructive"
        : "text-foreground";

  return (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onBlur={() => setOpen(false)}
      aria-expanded={open}
      className="group relative flex flex-1 flex-col items-center gap-0.5 px-2 py-1 text-center outline-none"
    >
      <span className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {metric.label}
        <Info className="size-3 opacity-50" aria-hidden />
      </span>
      <span className={cn("flex items-center gap-1 text-xl font-semibold tracking-tight tabular-nums", toneClass)}>
        {metric.tone === "up" && <TrendingUp className="size-4" aria-hidden />}
        {metric.tone === "down" && <TrendingDown className="size-4" aria-hidden />}
        {metric.value}
      </span>
      {metric.sub ? <span className="text-[11px] text-muted-foreground">{metric.sub}</span> : null}

      {open ? (
        <span
          role="tooltip"
          className="absolute left-1/2 top-full z-30 mt-2 w-52 -translate-x-1/2 rounded-xl border border-border bg-popover px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed text-popover-foreground shadow-lg"
        >
          {metric.help}
        </span>
      ) : null}
    </button>
  );
}
