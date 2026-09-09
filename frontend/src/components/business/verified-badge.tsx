// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The business identity chip: a circular logo inside a gold ring with a small
 * "verified" star-tick overlapping the corner (Twitter/X style) to mark this as
 * a business account, distinct from a customer avatar.
 */
import { BadgeCheck } from "lucide-react";
import { AvatarImg } from "@/components/avatar-img";
import { BusinessArt } from "@/components/business/business-art";
import { cn } from "@/lib/utils";

function VerifiedAvatar({
  src,
  alt,
  name,
  size = "md",
  className,
}: {
  src?: string;
  alt: string;
  name?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  // `sm` is the top-bar chip: it has to breathe inside a 56px bar and match the
  // customer shell's avatar, so it is deliberately smaller than a "small card".
  const dims = size === "lg" ? "size-20" : size === "sm" ? "size-8" : "size-14";
  const tick = size === "lg" ? "size-7" : size === "sm" ? "size-3.5" : "size-5";
  return (
    <div className={cn("relative shrink-0", className)}>
      <div className="rounded-full bg-gradient-to-br from-amber-300 to-amber-500 p-[3px] shadow-sm">
        <AvatarImg src={src} name={name} alt={alt} className={cn(dims, "border-2 border-card")} />
      </div>
      <BadgeCheck
        className={cn(
          tick,
          "absolute -bottom-0.5 -right-0.5 rounded-full fill-amber-400 stroke-card text-card",
        )}
        aria-label="Verified business"
      />
    </div>
  );
}

/** The business identity chip used across the owner UI: the uploaded provider
 *  avatar when one is set, else the on-brand generated scene, keeping the same
 *  gold-ring + verified treatment either way, so every surface shows the same
 *  face. Callers pass the provider's `avatarUrl` (may be empty) and its `scene`. */
export function BusinessBadge({
  avatarUrl,
  name,
  scene,
  size = "md",
  className,
}: {
  avatarUrl?: string;
  /** Only used if the uploaded logo fails to load, then it draws initials. */
  name?: string;
  scene: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return avatarUrl ? (
    <VerifiedAvatar src={avatarUrl} name={name} alt="" size={size} className={className} />
  ) : (
    <VerifiedScene scene={scene} size={size} className={className} />
  );
}

/** Same gold-ring + verified treatment, but the "photo" is a generated on-brand
 *  scene (the business's illustrated profile picture) instead of an <img>. */
export function VerifiedScene({
  scene,
  size = "md",
  className,
}: {
  scene: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  // `sm` is the top-bar chip: it has to breathe inside a 56px bar and match the
  // customer shell's avatar, so it is deliberately smaller than a "small card".
  const dims = size === "lg" ? "size-20" : size === "sm" ? "size-8" : "size-14";
  const tick = size === "lg" ? "size-7" : size === "sm" ? "size-3.5" : "size-5";
  return (
    <div className={cn("relative shrink-0", className)}>
      <div className="rounded-full bg-gradient-to-br from-amber-300 to-amber-500 p-[3px] shadow-sm">
        <div className={cn(dims, "overflow-hidden rounded-full border-2 border-card")}>
          <BusinessArt scene={scene} />
        </div>
      </div>
      <BadgeCheck
        className={cn(
          tick,
          "absolute -bottom-0.5 -right-0.5 rounded-full fill-amber-400 stroke-card text-card",
        )}
        aria-label="Verified business"
      />
    </div>
  );
}
