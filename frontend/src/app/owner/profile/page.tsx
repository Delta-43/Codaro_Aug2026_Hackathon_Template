"use client";

/**
 * Business tab 5 — Profile. The public-facing showcase a customer sees when
 * deciding whether to book: hero, bio, links/socials and reviews. Identity is
 * the owner's real provider (name/tagline/bio/rating/links) and the reviews are
 * the real ones left on their bookings (/providers/{id}/reviews). Editing lives
 * in Settings (cog, top-right).
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, Globe, MapPin, Settings, Star } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { BusinessArt } from "@/components/business/business-art";
import { BusinessBadge } from "@/components/business/verified-badge";
import { getProviderReviews } from "@/api";
import type { ProviderReview } from "@/types/domain";
import { avatarDataUri } from "@/lib/business-demo";

function whenLabel(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
  } catch {
    return "";
  }
}

export default function ProfilePage() {
  const { ready, activeProvider, scene, vocab } = useOwner();
  const [reviews, setReviews] = useState<ProviderReview[]>([]);

  useEffect(() => {
    if (!activeProvider) return;
    let cancelled = false;
    getProviderReviews(activeProvider.id)
      .then((r) => !cancelled && setReviews(r))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeProvider]);

  if (!ready) return <Skeleton className="h-96 w-full" />;

  if (!activeProvider) {
    return (
      <p className="rounded-2xl border border-dashed border-border px-4 py-12 text-center text-sm text-muted-foreground">
        Your public profile appears here once your business is set up.
      </p>
    );
  }

  const p = activeProvider;

  return (
    <section className="space-y-6 py-2">
      {/* Hero */}
      <div className="overflow-hidden rounded-3xl border border-border bg-card">
        <div className="relative h-36 w-full sm:h-44">
          <BusinessArt scene={scene} />
          <Link
            href="/owner/settings"
            aria-label="Settings"
            className="absolute right-3 top-3 grid size-9 place-items-center rounded-full bg-black/35 text-white backdrop-blur-sm transition-colors hover:bg-black/50"
          >
            <Settings className="size-5" aria-hidden />
          </Link>
          <div className="absolute -bottom-8 left-4">
            <BusinessBadge avatarUrl={p.avatarUrl} scene={scene} size="lg" />
          </div>
        </div>
        <div className="px-4 pb-4 pt-10">
          <h1 className="truncate text-xl font-semibold tracking-tight">{p.name}</h1>
          {p.tagline ? <p className="text-sm text-muted-foreground">{p.tagline}</p> : null}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
              <span className="font-medium text-foreground">{p.rating.toFixed(1)}</span>
              ({p.reviewCount})
            </span>
            {p.location.city ? (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden /> {p.location.city}
              </span>
            ) : null}
            <span className="rounded bg-muted px-1.5 py-0.5">{vocab.label}</span>
          </div>
        </div>
      </div>

      {/* About */}
      {p.bio ? (
        <div>
          <h2 className="mb-2 text-sm font-semibold">About</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{p.bio}</p>
        </div>
      ) : null}

      {/* Links & socials */}
      {p.links.length ? (
        <div>
          <h2 className="mb-2 text-sm font-semibold">Links</h2>
          <div className="flex flex-wrap gap-2">
            {p.links.map((s) => (
              <a
                key={s.label + s.url}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted"
              >
                {s.label.toLowerCase() === "website" ? (
                  <Globe className="size-3.5" aria-hidden />
                ) : (
                  <ExternalLink className="size-3.5" aria-hidden />
                )}
                <span className="font-medium">{s.label}</span>
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {/* Reviews */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Reviews</h2>
        {reviews.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
            No reviews yet — they show up here as customers rate their bookings.
          </p>
        ) : (
          <ul className="space-y-3">
            {reviews.map((rv, i) => (
              <li key={i} className="rounded-2xl border border-border bg-card p-3">
                <div className="flex items-center gap-2">
                  <AvatarImg src={avatarDataUri(rv.author)} alt="" className="size-8" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{rv.author}</span>
                      <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                        <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                        {rv.rating.toFixed(1)}
                      </span>
                    </div>
                    <span className="text-[11px] text-muted-foreground">{whenLabel(rv.createdAtUtc)}</span>
                  </div>
                </div>
                {rv.text ? <p className="mt-2 text-sm text-muted-foreground">{rv.text}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
