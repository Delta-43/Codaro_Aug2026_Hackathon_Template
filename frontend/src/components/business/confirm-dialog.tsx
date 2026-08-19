"use client";

/**
 * Minimalist "are you sure?" gate. A compact centred card: title, supporting
 * copy, an optional summary of what's changing, and an inline Cancel / confirm
 * pair. `tone` only colours the confirm button — "destructive" (default) makes
 * it red for irreversible actions (delete, editing a live offer), "default"
 * keeps it neutral for reversible ones (sign out). The chrome stays light either
 * way — no warning banner, no full-bleed buttons.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export function ConfirmDialog({
  open,
  title = "Are you sure you want to make this change?",
  body = "Changes to a live offer may not be reversible and can affect existing bookings.",
  confirmLabel = "Yes, save changes",
  busyLabel = "Saving…",
  tone = "destructive",
  onConfirm,
  onClose,
  children,
}: {
  open: boolean;
  title?: string;
  body?: string;
  confirmLabel?: string;
  /** In-progress label on the confirm button (default "Saving…"). */
  busyLabel?: string;
  /** Colours the confirm button: "destructive" (default) red for irreversible
   *  actions, "default" neutral for reversible ones. Layout is minimal either way. */
  tone?: "default" | "destructive";
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
  /** Optional summary of what's changing, shown above the buttons. */
  children?: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" aria-hidden onClick={() => !busy && onClose()} />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        className="relative z-10 w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-xl"
      >
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>

        {children ? (
          <div className="mt-3 rounded-xl border border-border bg-muted/40 p-3 text-sm">{children}</div>
        ) : null}

        {error ? (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" size="sm" isDisabled={busy} onPress={onClose}>
            Cancel
          </Button>
          <Button variant={tone === "destructive" ? "destructive" : "default"} size="sm" isDisabled={busy} onPress={confirm}>
            {busy ? busyLabel : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
