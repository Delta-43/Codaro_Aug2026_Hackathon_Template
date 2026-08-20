"use client";

import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A multi-line field wearing the same skin as `<Input>` and `<Select>`.
 *
 * Both textareas in the app — the review note and the owner's announcement —
 * had been hand-styled to `rounded-lg border-input bg-background ring-2`, which
 * is the shape and tint the single-line fields stopped using: a review box sat
 * on the same card as a `rounded-2xl bg-input/50` input and read as a different
 * control. Radius, tint, ring and type scale come from here now.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 resize-none rounded-2xl border border-transparent bg-input/50 px-2.5 py-2 text-base transition-[color,box-shadow] duration-200 outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
