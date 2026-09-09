// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Shared slot-span logic for the booking and reschedule flows.
 *
 * Both flows let the user drag out a contiguous run of slots on one resource,
 * and both must reject the same three things: too many slots for the service,
 * a slot that is not bookable, and a gap in the middle. That rule lived twice,
 * byte-identical, in `booking-flow.tsx` and `reschedule-flow.tsx`, so a change
 * to the limit or the copy could be applied to one flow and silently not the
 * other. One definition, both callers.
 */
import type { Service, Slot } from "@/types/domain";
import { ms } from "@/lib/format";

/** Why this span cannot be booked, or null when it is valid.
 *
 *  `slotNounPlural` comes from `terms.slots`, so the limit names what is being
 *  counted ("up to 14 nights in a row") instead of a bare number. Optional so
 *  the pure-logic callers and tests need not thread vocabulary through. */
export function validateSpan(
  span: Slot[],
  service: Service,
  slotNounPlural?: string,
): string | null {
  if (span.length < 1) return "Nothing selected.";
  if (span.length > service.maxSlotsPerBooking)
    return `You can book up to ${service.maxSlotsPerBooking}${
      slotNounPlural ? ` ${slotNounPlural.toLowerCase()}` : ""
    } in a row.`;
  for (const s of span) {
    if (s.status !== "available" && s.status !== "partially_booked")
      return "That range includes an unavailable time.";
  }
  for (let i = 1; i < span.length; i++) {
    if (ms(span[i].startUtc) !== ms(span[i - 1].endUtc))
      return "Selected times must be back-to-back with no gaps.";
  }
  return null;
}
