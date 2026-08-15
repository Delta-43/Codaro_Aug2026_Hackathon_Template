"use client";

/**
 * Demo QR scanner. No real camera permission is requested — a simulated
 * viewfinder with a few tappable mock targets that resolve to seeded providers
 * via getProviderByCode (the same path a real scan would take). Labelled
 * honestly as a demo.
 */
import { useState } from "react";
import { QrCode } from "lucide-react";
import type { Provider } from "@/types/domain";
import { getProviderByCode } from "@/api";
import { Modal } from "@/components/modal";

export function QrScannerModal({
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
    <Modal open={open} onClose={onClose} title="Scan a code">
      <p className="mb-3 text-xs text-muted-foreground">
        Demo scanner — no camera is used. Tap a code below to simulate a scan.
      </p>

      <div className="relative mx-auto mb-4 grid aspect-square max-w-[240px] place-items-center overflow-hidden rounded-xl border border-border bg-muted/40">
        <div className="pointer-events-none absolute inset-5 rounded-lg border-2 border-primary/60" />
        <div className="pointer-events-none absolute inset-x-7 top-7 h-0.5 animate-pulse bg-primary" />
        <QrCode className="size-16 text-muted-foreground/40" aria-hidden />
      </div>

      <div className="space-y-2">
        {targets.slice(0, 3).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => scan(t.publicCode)}
            disabled={scanning !== null}
            className="flex w-full items-center justify-between rounded-lg border border-dashed border-border px-3 py-2 text-left text-sm transition-colors hover:bg-muted disabled:opacity-60"
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
