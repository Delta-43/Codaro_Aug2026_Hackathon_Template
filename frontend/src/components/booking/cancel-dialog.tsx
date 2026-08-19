"use client";

/**
 * Cancel confirmation. The backend is the authority on the cutoff — this dialog
 * simply asks, calls cancelBooking, and surfaces any ApiError message verbatim
 * (e.g. CUTOFF_PASSED) rather than inventing its own copy.
 */
import { useState } from "react";
import type { Booking } from "@/types/domain";
import { cancelBooking, isApiError } from "@/api";
import { Modal } from "@/components/modal";
import { Button } from "@/components/ui/button";
import { useVertical } from "@/context/app-context";

export function CancelDialog({
  booking,
  open,
  onClose,
  onCancelled,
}: {
  booking: Booking;
  open: boolean;
  onClose: () => void;
  onCancelled: (updated: Booking) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // `terms.booking` — lowercase because it lands mid-sentence in every use here.
  const noun = useVertical().bookingNoun.toLowerCase();

  async function confirm() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await cancelBooking(booking.id);
      onCancelled(updated);
    } catch (e) {
      setError(isApiError(e) ? e.message : `Couldn't cancel this ${noun}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Cancel ${noun}?`}>
      <p className="text-sm text-muted-foreground">
        This releases your place. This can&apos;t be undone.
      </p>

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}

      <div className="mt-5 flex gap-2">
        <Button variant="outline" className="flex-1" isDisabled={busy} onPress={onClose}>
          Keep booking
        </Button>
        <Button variant="destructive" className="flex-1" isDisabled={busy} onPress={confirm}>
          {busy ? "Cancelling…" : `Cancel ${noun}`}
        </Button>
      </div>
    </Modal>
  );
}
