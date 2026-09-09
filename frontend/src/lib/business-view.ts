// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Deterministic view helpers for business mode + user profiles.
 *
 * Seeded off a stable key (the use case + entity id), so a given business/user
 * always renders the same avatar across tabs and refreshes.
 *
 * What lives here: the seeded RNG, the avatar gradient/initials helpers, and
 * the `Metric` /
 * `BookingView` shapes that the owner views (fed real `/owner/*` data) type
 * against.
 */
import type { Loan, PaymentState } from "@/types/domain";
// --- deterministic RNG ------------------------------------------------------

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(a: number): () => number {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function rng(seed: string): () => number {
  return mulberry32(hashStr(seed));
}

function pick<T>(r: () => number, arr: readonly T[]): T {
  return arr[Math.floor(r() * arr.length)];
}

// --- deterministic initials avatar (data URI) -------------------------------

const AVATAR_HUES = [3, 28, 46, 152, 190, 220, 260, 320];

/** The two gradient stops a given name always maps to. Shared by every avatar
 *  fallback so the same person gets the same colours on every surface. */
export function avatarGradient(name: string): { from: string; to: string } {
  const r = rng(name || "?");
  const hue = pick(r, AVATAR_HUES);
  return {
    from: `hsl(${hue} 70% 62%)`,
    to: `hsl(${(hue + 40) % 360} 68% 48%)`,
  };
}

/** Up to two uppercase initials from a display name (`""` when unnameable). */
export function avatarInitials(name: string | undefined | null): string {
  return (name ?? "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

// --- shapes -----------------------------------------------------------------

export interface Metric {
  key: string;
  label: string;
  value: string;
  sub?: string;
  tone: "up" | "down" | "neutral";
  help: string;
}

type BookingViewStatus = "confirmed" | "completed" | "pending";

export interface BookingView {
  id: string;
  title: string;
  client: string;
  serviceLabel: string;
  startUtc: string;
  endUtc: string;
  status: BookingViewStatus;
  partySize: number;
  priceMinorUnits: number;
  currency: string;
  /** The return leg, when the service loans something. Null for the vast
   *  majority of deployments, which loan nothing. */
  loan?: Loan | null;
  /** Outstanding blocking prerequisites and the payment position, so the owner
   *  console can act on both without refetching the full booking. */
  prerequisitesPending?: string[];
  payment?: PaymentState;
}
