"use client";

/**
 * Review capture for a completed booking. Renders the saved review read-only if
 * one exists, otherwise a 1–5 star picker + note that calls leaveReview. The API
 * only accepts reviews on completed bookings; this component is rendered solely
 * in that case (see BookingDetail).
 */
import { useState } from "react";
import { Star } from "lucide-react";
import type { Booking } from "@/types/domain";
import { isApiError, leaveReview } from "@/api";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function ReviewForm({
  booking,
  tz,
  onReviewed,
}: {
  booking: Booking;
  tz: string;
  onReviewed: (updated: Booking) => void;
}) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (booking.review) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">Your review</h2>
        <div className="mt-2 flex items-center gap-0.5" aria-label={`${booking.review.rating} out of 5`}>
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={cn(
                "size-4",
                i < booking.review!.rating
                  ? "fill-amber-400 text-amber-400"
                  : "text-muted-foreground/40",
              )}
              aria-hidden
            />
          ))}
        </div>
        {booking.review.text ? (
          <p className="mt-2 text-sm text-foreground/90">{booking.review.text}</p>
        ) : null}
        <p className="mt-2 text-xs text-muted-foreground">
          {formatDate(booking.review.createdAtUtc, tz, { weekday: true, withYear: true })}
        </p>
      </div>
    );
  }

  async function submit() {
    if (busy || rating < 1) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await leaveReview(booking.id, rating, text);
      onReviewed(updated);
    } catch (e) {
      setError(isApiError(e) ? e.message : "Couldn't save your review.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">Leave a review</h2>

      <div className="mt-3 flex items-center gap-1" role="radiogroup" aria-label="Rating">
        {Array.from({ length: 5 }).map((_, i) => {
          const value = i + 1;
          const filled = (hover || rating) >= value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              aria-label={`${value} star${value === 1 ? "" : "s"}`}
              onMouseEnter={() => setHover(value)}
              onMouseLeave={() => setHover(0)}
              onClick={() => setRating(value)}
              className={cn(
                "rounded-md p-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
                buttonFx.star,
              )}
            >
              <Star
                className={cn(
                  "size-6 transition-colors",
                  filled ? "fill-amber-400 text-amber-400" : "text-muted-foreground/40",
                )}
                aria-hidden
              />
            </button>
          );
        })}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Share how it went (optional)"
        aria-label="Review note"
        rows={3}
        className="mt-3 w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
      />

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}

      <Button className="mt-3" isDisabled={busy || rating < 1} onPress={submit}>
        {busy ? "Saving…" : "Submit review"}
      </Button>
    </div>
  );
}
