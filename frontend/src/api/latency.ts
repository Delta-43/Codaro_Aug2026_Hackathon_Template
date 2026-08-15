/**
 * Simulated network. Every API function awaits `delay()` so real loading
 * states are exercised in the mock world exactly as they will be against HTTP.
 * `clone()` hands callers a detached copy so no component can mutate the store
 * by reference — the same isolation a JSON-over-HTTP boundary gives for free.
 */

const MIN_MS = 150;
const MAX_MS = 450;

export function delay(minMs = MIN_MS, maxMs = MAX_MS): Promise<void> {
  const ms = minMs + Math.random() * (maxMs - minMs);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function clone<T>(value: T): T {
  // Our domain data is plain JSON (strings/numbers/arrays/objects), so a
  // structured clone is exact and cheap. Prefer the platform primitive when
  // present; fall back for older runtimes.
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}
