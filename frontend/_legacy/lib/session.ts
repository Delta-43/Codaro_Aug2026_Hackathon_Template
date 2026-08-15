"use client";

/** "Login" here is identity only -- per frontend/CLAUDE.md there is no password
 *  auth and no auth provider. We just remember which email the visitor claimed
 *  so the dashboard can scope `/bookings?client_email=` to them. */

const KEY = "booking-engine.client_email";

export function getClientEmail(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY);
}

export function setClientEmail(email: string): void {
  window.localStorage.setItem(KEY, email.trim().toLowerCase());
}

export function clearClientEmail(): void {
  window.localStorage.removeItem(KEY);
}
