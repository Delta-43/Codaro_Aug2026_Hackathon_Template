"use client";

/**
 * Full-screen "are you sure?" gate for changes that may not be reversible
 * (editing a live offer, etc.). A big destructive confirm, a calm cancel, and a
 * top-right X — deliberately heavy so a change is always intentional.
 */
import { useEffect, useState, type ReactNode } from "react";
import { TriangleAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ConfirmDialog({
  open,
  title = "Are you sure you want to make this change?",
  body = "Changes to a live offer may not be reversible and can affect existing bookings.",
  confirmLabel = "Yes, save changes",
  onConfirm,
  onClose,
  children,
}: {
  open: boolean;
  title?: string;
  body?: string;
  confirmLabel?: string;
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
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-hidden onClick={() => !busy && onClose()} />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        className="relative z-10 w-full max-w-md rounded-3xl border border-border bg-card p-6 text-center shadow-2xl"
      >
        <button
          onClick={() => !busy && onClose()}
          aria-label="Close"
          className="absolute right-4 top-4 flex size-8 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" aria-hidden />
        </button>

        <div className="mx-auto mb-4 grid size-14 place-items-center rounded-full bg-destructive/10 text-destructive">
          <TriangleAlert className="size-7" aria-hidden />
        </div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <p className="mx-auto mt-2 max-w-xs text-sm text-muted-foreground">{body}</p>

        {children ? (
          <div className="mt-4 rounded-2xl border border-border bg-muted/40 p-3 text-left text-sm">{children}</div>
        ) : null}

        {error ? (
          <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <div className="mt-6 flex flex-col gap-2">
          <Button
            variant="destructive"
            size="lg"
            isDisabled={busy}
            onPress={confirm}
            className="w-full bg-destructive text-base font-semibold text-white hover:bg-destructive/90 dark:text-white"
          >
            {busy ? "Saving…" : confirmLabel}
          </Button>
          <Button variant="ghost" size="lg" isDisabled={busy} onPress={onClose} className="w-full">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
