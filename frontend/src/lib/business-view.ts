// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Deterministic view helpers for business mode + user profiles.
 *
 * Seeded off a stable key (the use case + entity id), so a given business/user
 * always renders the same avatar across tabs and refreshes.
 *
 * What lives here: the seeded RNG, `avatarDataUri`, and the `Metric` /
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

/** A small initials avatar as an inline SVG data URI (no network, theme-safe). */
export function avatarDataUri(name: string): string {
  const r = rng(name);
  const hue = pick(r, AVATAR_HUES);
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="hsl(${hue} 70% 62%)"/>
<stop offset="1" stop-color="hsl(${(hue + 40) % 360} 68% 48%)"/></linearGradient></defs>
<rect width="96" height="96" rx="48" fill="url(#g)"/>
<text x="48" y="49" dominant-baseline="central" text-anchor="middle" font-family="Outfit, ui-sans-serif, system-ui, sans-serif" font-size="38" font-weight="600" fill="#fff">${initials}</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
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
