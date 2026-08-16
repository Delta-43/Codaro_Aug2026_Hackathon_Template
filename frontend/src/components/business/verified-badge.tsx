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

export function VerifiedAvatar({
  src,
  alt,
  size = "md",
  className,
}: {
  src?: string;
  alt: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const dims = size === "lg" ? "size-20" : size === "sm" ? "size-10" : "size-14";
  const tick = size === "lg" ? "size-7" : size === "sm" ? "size-4" : "size-5";
  return (
    <div className={cn("relative shrink-0", className)}>
      <div className="rounded-full bg-gradient-to-br from-amber-300 to-amber-500 p-[3px] shadow-sm">
        <AvatarImg src={src} alt={alt} className={cn(dims, "border-2 border-card")} />
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
  const dims = size === "lg" ? "size-20" : size === "sm" ? "size-10" : "size-14";
  const tick = size === "lg" ? "size-7" : size === "sm" ? "size-4" : "size-5";
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
