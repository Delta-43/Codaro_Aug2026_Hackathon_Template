// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * "Enter a code", the single entry point for resolving a provider by its
 * publicCode, whether typed or scanned. Both paths go through the same
 * getProviderByCode call (a real scan would too); the demo scan is a set of
 * tappable seeded codes, labelled honestly as a demo. Replaces the separate
 * inline code field + QR modal so the search toolbar stays compact.
 */
import { useState } from "react";
import { QrCode } from "lucide-react";
import type { Provider } from "@/types/domain";
import { getProviderByCode } from "@/api";
import { Modal } from "@/components/modal";
import { CodeEntry } from "@/components/search/code-entry";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function CodeModal({
  open,
  onClose,
  targets,
  onResolved,
}: {
  open: boolean;
  onClose: () => void;
  targets: Provider[];
  onResolved: (p: Provider) => void;
}) {
  const [scanning, setScanning] = useState<string | null>(null);

  async function scan(code: string) {
    if (scanning) return;
    setScanning(code);
    try {
      const provider = await getProviderByCode(code);
      onResolved(provider);
    } finally {
      setScanning(null);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Enter a code">
      {/* Type it */}
      <p className="mb-2 text-xs text-muted-foreground">
        Enter a provider code to jump straight to them.
      </p>
      <CodeEntry onResolved={onResolved} />

      {/* …or scan it (demo) */}
      <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or scan a code
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="relative mx-auto mb-4 grid aspect-square max-w-[180px] place-items-center overflow-hidden rounded-xl border border-border bg-muted/40">
        <div className="pointer-events-none absolute inset-5 rounded-lg border-2 border-primary/60" />
        <div className="pointer-events-none absolute inset-x-7 top-7 h-0.5 animate-pulse bg-primary" />
        <QrCode className="size-14 text-muted-foreground/40" aria-hidden />
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        Demo scanner, no camera is used. Tap a code to simulate a scan.
      </p>

      <div className="space-y-2">
        {targets.slice(0, 3).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => scan(t.publicCode)}
            disabled={scanning !== null}
            className={cn(
              "flex w-full items-center justify-between rounded-lg border border-dashed border-border px-3 py-2 text-left text-sm disabled:opacity-60",
              buttonFx.surface,
            )}
          >
            <span className="min-w-0 truncate">{t.name}</span>
            <span className="shrink-0 font-mono text-xs text-muted-foreground">
              {scanning === t.publicCode ? "Scanning…" : t.publicCode}
            </span>
          </button>
        ))}
        {targets.length === 0 ? (
          <p className="text-sm text-muted-foreground">No codes to scan right now.</p>
        ) : null}
      </div>
    </Modal>
  );
}
