// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import type * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A native `<select>` wearing the same skin as `<Input>`.
 *
 * Four call sites had each hand-rolled the same class string — booking's field
 * form, its options picker, the repeat picker on the confirm screen and the
 * owner's service form — and the copy had already drifted from `Input`: no focus
 * ring, no transition, no disabled treatment, and the browser's own arrow in a
 * shape and colour nothing else on the page uses. Height, radius, tint, ring and
 * type scale now come from here, so a select sits beside an input without
 * looking borrowed from another app.
 *
 * It stays a real `<select>`: the platform's own popup is the accessible,
 * touch-friendly control on every device, and nothing here needs a listbox with
 * custom rows. `appearance-none` only removes the native arrow so the chevron
 * can match every other chevron in the UI.
 */
function Select({
  className,
  children,
  ...props
}: React.ComponentProps<"select">) {
  // `className` lands on the wrapper, not the control: every call site passes
  // sizing or spacing ("w-auto" beside a label, "mt-1" under one), and on the
  // bare <select> those would fight the chevron's positioning context.
  return (
    <div className={cn("relative inline-flex w-full items-center", className)}>
      <select
        data-slot="select"
        className={
          // The option list is painted by the platform from the control's own
          // colours, and the control is translucent (`bg-input/50`) — in dark
          // mode that resolved to dark-on-dark text in the open popup, so the
          // options get opaque theme colours of their own.
          "h-8 w-full min-w-0 appearance-none rounded-2xl border border-transparent bg-input/50 py-1 pr-8 pl-2.5 text-base transition-[color,box-shadow] duration-200 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&>option]:bg-background [&>option]:text-foreground"
        }
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2.5 size-4 text-muted-foreground"
        aria-hidden
      />
    </div>
  );
}

export { Select };
