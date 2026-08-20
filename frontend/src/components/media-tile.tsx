"use client";

import { useEffect, useState } from "react";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The one photo surface for *things* — a chapel, a hearse, a vehicle, a room.
 * The counterpart to `AvatarImg`, which is for faces: this one stays
 * rectangular and never invents initials or a colour for an object.
 *
 * Same three states as the avatar, for the same reasons:
 *  1. a usable `src` → a plain lazy `<img>` (not `next/image`: seed photos are
 *     same-origin files under `/media/`, uploads are Supabase Storage URLs on a
 *     host `next.config.mjs` has no `remotePatterns` entry for);
 *  2. that image fails → the placeholder, not the browser's broken glyph. The
 *     demo photos are downloaded files that may be missing or truncated;
 *  3. no `src` → a muted panel with a faint icon.
 *
 * An empty `src` is never handed to the DOM: `<img src="">` makes the browser
 * re-request the current document and then renders as broken.
 */
export function MediaTile({
  src,
  alt,
  className,
  rounded = "rounded-lg",
}: {
  src?: string | null;
  /** Empty string for decorative use next to a visible name — the common case
   *  here, since every tile sits beside the unit's own label. */
  alt: string;
  className?: string;
  rounded?: string;
}) {
  const url = typeof src === "string" ? src.trim() : "";
  const [failed, setFailed] = useState(false);

  // A list that recycles (a re-fetched picker, a new service's units) must not
  // keep a previous occupant's failure, or a good photo stays a placeholder.
  useEffect(() => {
    setFailed(false);
  }, [url]);

  if (!url || failed) {
    return (
      <span
        role="img"
        aria-label={alt || undefined}
        className={cn("grid shrink-0 place-items-center bg-muted", rounded, className)}
      >
        <ImageIcon className="size-5 text-muted-foreground/40" aria-hidden />
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={cn("shrink-0 bg-muted object-cover", rounded, className)}
    />
  );
}
