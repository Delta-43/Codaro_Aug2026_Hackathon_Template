// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The three-dot "typing…" bubble, styled like a received message. The dots are
 * driven by Tailwind's built-in bounce with staggered delays — purely ephemeral
 * (fed by a Realtime broadcast, never persisted).
 */
export function TypingIndicator() {
  return (
    <div className="mr-auto flex w-fit items-center gap-1 rounded-2xl rounded-bl-md bg-muted px-3.5 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${i * 150}ms`, animationDuration: "1s" }}
        />
      ))}
      <span className="sr-only">Typing…</span>
    </div>
  );
}
