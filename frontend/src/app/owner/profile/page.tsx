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
import { ExternalLink, Globe, Settings, Star } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { BusinessHero } from "@/components/business/business-hero";
import { getProviderReviews } from "@/api";
import type { ProviderReview } from "@/types/domain";
import { whenLabel } from "@/lib/format";

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
      {/* Hero — the same header Settings edits in place. */}
      <BusinessHero
        provider={p}
        scene={scene}
        vocabLabel={vocab.label}
        action={
          <Link
            href="/owner/settings"
            aria-label="Settings"
            className="grid size-9 place-items-center rounded-full bg-black/35 text-white backdrop-blur-sm transition-colors hover:bg-black/50"
          >
            <Settings className="size-5" aria-hidden />
          </Link>
        }
      />

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
                  <AvatarImg src={rv.authorAvatarUrl} name={rv.author} alt="" className="size-8" />
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
