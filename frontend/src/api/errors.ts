/**
 * The error contract. The backend mirrors these codes so UI error handling
 * (inline "slot was just taken", disabled-with-reason, retry) needs no change
 * when mocks are swapped for HTTP.
 */
export type ApiErrorCode =
  | "SLOT_UNAVAILABLE" // a chosen slot filled up before commit
  | "CUTOFF_PASSED" // inside cancellationCutoffHours of start
  | "NOT_FOUND" // no such entity
  | "CAPACITY_EXCEEDED" // partySize > remaining capacity
  | "INVALID_RANGE" // multi-slot selection not contiguous / wrong length
  | "NETWORK"; // transport failure (reserved; not thrown by mocks)

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  /** Optional machine-readable context (e.g. which slot ids failed). */
  readonly details?: Record<string, unknown>;

  constructor(
    code: ApiErrorCode,
    message: string,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
    // Keep instanceof working when compiled to ES5-ish targets.
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
