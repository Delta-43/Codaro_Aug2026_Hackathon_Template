// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Long-form prose primitives for /docs. The project has no typography plugin,
 * so headings/tables/code get their styling from these instead of a `prose`
 * class, server components, no client JS.
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** One numbered chapter. `id` is the TOC/scroll-spy anchor. */
export function Section({
  id,
  step,
  title,
  lede,
  children,
}: {
  id: string;
  step?: string;
  title: string;
  lede?: ReactNode;
  children: ReactNode;
}) {
  return (
    // tabIndex: the TOC moves focus here after the glide, so keyboard and
    // screen-reader users land where the scroll did. No ring, the heading
    // flash already marks the arrival.
    <section
      id={id}
      tabIndex={-1}
      className="scroll-mt-28 border-t border-border/60 pt-10 outline-none first:border-0 first:pt-0"
    >
      {step ? (
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">{step}</p>
      ) : null}
      <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
      {lede ? <p className="mt-3 text-base leading-relaxed text-muted-foreground">{lede}</p> : null}
      <div className="mt-6 space-y-4 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export function H3({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <h3 id={id} tabIndex={-1} className="scroll-mt-28 pt-4 text-base font-semibold text-foreground outline-none">
      {children}
    </h3>
  );
}

/** Inline code / a config path. */
export function C({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.8125rem] text-foreground">
      {children}
    </code>
  );
}

/** Fenced block. `label` names the file or command it comes from. */
export function Code({ label, children }: { label?: string; children: string }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-border bg-muted/40">
      {label ? (
        <figcaption className="border-b border-border/60 px-4 py-2 font-mono text-xs text-muted-foreground">
          {label}
        </figcaption>
      ) : null}
      <pre className="no-scrollbar overflow-x-auto px-4 py-3 text-[0.8125rem] leading-relaxed">
        <code className="font-mono text-foreground">{children}</code>
      </pre>
    </figure>
  );
}

/** Aside. `tone` "warn" is for the known-broken cases, not for emphasis. */
export function Note({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn";
  title: string;
  children: ReactNode;
}) {
  return (
    <aside
      className={cn(
        "rounded-xl border-l-2 bg-muted/40 px-4 py-3",
        tone === "warn" ? "border-l-destructive" : "border-l-primary",
      )}
    >
      <p
        className={cn(
          "text-xs font-semibold uppercase tracking-wide",
          tone === "warn" ? "text-destructive" : "text-primary",
        )}
      >
        {title}
      </p>
      <div className="mt-1.5 space-y-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </aside>
  );
}

/** Field/value reference table. Scrolls sideways rather than squashing on mobile. */
export function Table({
  head,
  rows,
}: {
  head: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="no-scrollbar overflow-x-auto rounded-xl border border-border">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40">
            {head.map((h, i) => (
              // Key by position: a header row never reorders, and some tables
              // repeat a label (e.g. two "Key"/"Default" columns), which would
              // collide on a text key.
              <th key={i} className="whitespace-nowrap px-4 py-2.5 font-medium text-foreground">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0 align-top">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5 text-muted-foreground">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function List({ children }: { children: ReactNode }) {
  return <ul className="ml-1 space-y-2 [&>li]:relative [&>li]:pl-5">{children}</ul>;
}

export function Item({ children }: { children: ReactNode }) {
  return (
    <li className="before:absolute before:left-0 before:top-[0.6em] before:size-1.5 before:rounded-full before:bg-primary/60">
      {children}
    </li>
  );
}
