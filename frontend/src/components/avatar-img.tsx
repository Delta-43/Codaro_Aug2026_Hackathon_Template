import { cn } from "@/lib/utils";

/**
 * Plain <img> avatar. Seed images are deterministic SVG data URIs, so no
 * next/image optimization is needed (and it would reject data: URLs anyway).
 */
export function AvatarImg({
  src,
  alt,
  className,
}: {
  src?: string;
  alt: string;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src ?? ""}
      alt={alt}
      className={cn("rounded-full bg-muted object-cover", className)}
    />
  );
}
