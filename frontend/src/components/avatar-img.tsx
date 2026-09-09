// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { useEffect, useId, useState } from "react";
import { avatarGradient, avatarInitials } from "@/lib/business-view";
import { cn } from "@/lib/utils";

/**
 * The one avatar surface. Every person and business face in the app goes
 * through here so the photo *and* its fallback look the same everywhere.
 *
 * Three states, in order:
 *  1. `src` is a non-empty URL → a plain lazy `<img>`. (Deliberately not
 *     `next/image`: seed avatars are same-origin files under `/media/` and
 *     uploads are Supabase Storage URLs on a host `next.config.mjs` has no
 *     `remotePatterns` entry for.)
 *  2. that image fails to load → we fall *back* to (3) rather than leaving the
 *     browser's broken-image glyph. Demo portraits are downloaded files that
 *     may be missing or truncated, so this is a real path, not a theoretical one.
 *  3. no usable `src` → the deterministic gradient + initials from `name`,
 *     drawn inline as an SVG (the same gradient + initials artwork, but it scales
 *     with the box instead of inheriting a random parent font-size, and costs
 *     no request).
 *
 * An empty `src` is never handed to the DOM: `<img src="">` makes the browser
 * re-request the current document and then renders as broken.
 */
export function AvatarImg({
  src,
  alt,
  name,
  className,
}: {
  src?: string | null;
  alt: string;
  /** Used when `src` is absent or fails to load, to render initials instead. */
  name?: string | null;
  className?: string;
}) {
  const url = typeof src === "string" ? src.trim() : "";
  const [failed, setFailed] = useState(false);
  const gradientId = useId();

  // A row that recycles (a re-sorted inbox, a re-fetched list) must not keep a
  // previous occupant's failure, or a good photo renders as initials forever.
  useEffect(() => {
    setFailed(false);
  }, [url]);

  if (!url || failed) {
    const initials = avatarInitials(name);
    const { from, to } = avatarGradient(name || alt || "?");
    // Nameless: a flat muted disc. Inventing a colour for someone we can't even
    // label reads as a person who isn't there.
    if (!initials) {
      return (
        <span
          role="img"
          aria-label={alt || undefined}
          className={cn("inline-block shrink-0 rounded-full bg-muted", className)}
        />
      );
    }
    return (
      <svg
        viewBox="0 0 96 96"
        width={96}
        height={96}
        role="img"
        aria-label={alt || undefined}
        className={cn("shrink-0 rounded-full bg-muted", className)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={from} />
            <stop offset="1" stopColor={to} />
          </linearGradient>
        </defs>
        <rect width="96" height="96" rx="48" fill={`url(#${gradientId})`} />
        <text
          x="48"
          y="49"
          dominantBaseline="central"
          textAnchor="middle"
          fontFamily="Outfit, ui-sans-serif, system-ui, sans-serif"
          fontSize="38"
          fontWeight="600"
          fill="#fff"
        >
          {initials}
        </text>
      </svg>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      width={96}
      height={96}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={cn("shrink-0 rounded-full bg-muted object-cover", className)}
    />
  );
}
