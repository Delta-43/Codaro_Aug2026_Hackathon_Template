import { cn } from "@/lib/utils";

/**
 * Plain <img> avatar. Seed images are deterministic SVG data URIs, so no
 * next/image optimization is needed (and it would reject data: URLs anyway).
 * Falls back to initials (from `name`) when `src` is unset, rather than a
 * broken/empty image.
 */
export function AvatarImg({
  src,
  alt,
  name,
  className,
}: {
  src?: string;
  alt: string;
  /** Used only when `src` is falsy, to render initials instead of an image. */
  name?: string;
  className?: string;
}) {
  if (!src) {
    const initials = name
      ? name
          .trim()
          .split(/\s+/)
          .slice(0, 2)
          .map((w) => w[0]?.toUpperCase())
          .join("")
      : "";
    return (
      <div
        role="img"
        aria-label={alt}
        className={cn(
          "flex items-center justify-center rounded-full bg-muted font-medium text-muted-foreground select-none",
          className,
        )}
      >
        {initials || null}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={cn("rounded-full bg-muted object-cover", className)}
    />
  );
}
