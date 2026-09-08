// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { Children, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * An inline form/flow message — a validation error, a rule violation the
 * backend rejected, a wrong-portal notice.
 *
 * Two things it centralises:
 *
 * **It arrives instead of snapping in.** These messages appear mid-interaction
 * and shove the layout below them; a bare conditional render pops the content
 * down with no warning and it reads as a glitch. A short fade + slide from above
 * makes it legible as "something just appeared here". `motion-reduce` drops the
 * movement for anyone who has asked for that.
 *
 * **It re-announces on a *new* message.** React reuses the DOM node when only
 * the text changes, so a second, different error would swap silently under a
 * still element — the user retries, gets a different rejection, and sees nothing
 * move. Keying on the message content remounts it, so the animation replays.
 *
 * It also carries the ARIA that four of the seven call sites had and three
 * didn't: an error is `role="alert"` (interrupts), a notice is `role="status"`
 * (waits its turn). `live` overrides that pairing for the case the tone can't
 * express — a message that is genuinely an error but is already on screen at
 * first paint, where interrupting the reader announces nothing the user just
 * did.
 *
 * Visuals stay overridable via `className` — the booking flows sit on cards and
 * use `rounded-lg`, the login plate matches its `rounded-2xl` inputs — but the
 * tint, padding and type scale come from here so they can't drift apart again.
 */
/** A key that changes whenever the *text* of the message does.
 *
 *  Not just `typeof children === "string"`: a call site that interpolates —
 *  `<InlineMessage>Failed: {reason}</InlineMessage>` — hands over an array of
 *  children, which would key as `undefined` and silently lose the remount this
 *  component exists to guarantee. Flattening the text children covers that;
 *  element children have no text to compare, so they contribute a constant and
 *  fall back to React's normal reuse. */
function messageKey(children: ReactNode): string | undefined {
  const parts = Children.toArray(children).map((child) =>
    typeof child === "string" || typeof child === "number" ? String(child) : "<el>",
  );
  return parts.length ? parts.join("") : undefined;
}

export function InlineMessage({
  children,
  className,
  tone = "error",
  live,
}: {
  children: ReactNode;
  className?: string;
  /** `error`: something failed. `notice`: it worked, but not the way you meant. */
  tone?: "error" | "notice";
  /** Override how assertively screen readers announce this. Defaults to the
   *  tone: `error` interrupts, `notice` waits. Pass `"polite"` for an error
   *  that is present on first paint rather than raised by an action. */
  live?: "assertive" | "polite";
}) {
  const assertive = (live ?? (tone === "error" ? "assertive" : "polite")) === "assertive";
  return (
    <p
      // Remount on a changed message so the entrance animation replays.
      key={messageKey(children)}
      role={assertive ? "alert" : "status"}
      className={cn(
        "animate-in fade-in slide-in-from-top-1 fill-mode-both duration-200 ease-out",
        "motion-reduce:animate-none motion-reduce:transition-none",
        "rounded-lg px-3 py-2 text-sm",
        tone === "error"
          ? "border border-destructive/40 bg-destructive/10 text-destructive"
          : "border border-amber-400/30 bg-amber-400/10 text-amber-700 dark:text-amber-400",
        className,
      )}
    >
      {children}
    </p>
  );
}
