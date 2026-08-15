/** Slot timestamps come back from Postgres as ISO strings with an offset
 *  (e.g. "2026-08-15T00:34:40.620144+00:00"). Render them in the viewer's own
 *  timezone -- the rules engine works in UTC, the UI should not. */
export function formatSlotTime(startsAt: string, endsAt?: string): string {
  const start = new Date(startsAt);
  const date = start.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric"
  });
  const from = start.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (!endsAt) return `${date}, ${from}`;
  const to = new Date(endsAt).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${date}, ${from} - ${to}`;
}

/** Hours from now until the slot starts -- used to grey out actions the
 *  cancellation-window rule would reject anyway (`rules.cancellationWindowHours`). */
export function hoursUntil(startsAt: string): number {
  return (new Date(startsAt).getTime() - Date.now()) / 3_600_000;
}
