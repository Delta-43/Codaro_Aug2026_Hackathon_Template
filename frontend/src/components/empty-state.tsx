// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

/**
 * A purposeful empty state: a line of copy plus a primary action. Used
 * wherever a data-driven view has nothing to show — never render blank.
 * Navigation uses next/link styled with the button variants (client-side nav).
 */
export function EmptyState({
  icon,
  title,
  body,
  actionHref,
  actionLabel,
  children,
}: {
  icon?: ReactNode;
  title: string;
  body?: string;
  actionHref?: string;
  actionLabel?: string;
  children?: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-[50dvh] max-w-sm flex-col items-center justify-center gap-3 px-4 py-16 text-center">
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <h2 className="text-base font-semibold tracking-tight">{title}</h2>
      {body ? <p className="text-sm text-muted-foreground">{body}</p> : null}
      {actionHref && actionLabel ? (
        <Link
          href={actionHref}
          className={cn(buttonVariants({ variant: "default", size: "lg" }), "mt-1")}
        >
          {actionLabel}
        </Link>
      ) : null}
      {children}
    </div>
  );
}
