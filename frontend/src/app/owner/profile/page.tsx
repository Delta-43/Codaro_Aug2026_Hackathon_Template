"use client";

/**
 * Business tab 5 — Profile. The public-facing showcase a customer sees when
 * deciding whether to book: hero, bio, links/socials, gallery, videos and
 * reviews. Everything follows the active demo use case (Settings → Demo), so
 * each niche presents itself coherently. Editing name/photo etc. lives in
 * Settings (cog, top-right — mobile) / the avatar (top-right — desktop).
 */
import { useMemo } from "react";
import Link from "next/link";
import { ExternalLink, Globe, MapPin, Play, Settings, Star } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { AvatarImg } from "@/components/avatar-img";
import { BusinessArt } from "@/components/business/business-art";
import { VerifiedScene } from "@/components/business/verified-badge";
import { demoGallery, demoReviews, demoSocial, demoVideos } from "@/lib/business-demo";

export default function ProfilePage() {
  const { ready, useCase, demoBusiness, seed } = useOwner();

  const gallery = useMemo(() => demoGallery(useCase), [useCase]);
  const videos = useMemo(() => demoVideos(useCase), [useCase]);
  const reviews = useMemo(() => demoReviews(useCase, seed), [useCase, seed]);
  const socials = useMemo(() => demoSocial(useCase), [useCase]);

  if (!ready) return <Skeleton className="h-96 w-full" />;

  return (
    <section className="space-y-6 py-2">
      {/* Hero */}
      <div className="overflow-hidden rounded-3xl border border-border bg-card">
        <div className="relative h-36 w-full sm:h-44">
          <BusinessArt scene={useCase.profileScene} />
          <Link
            href="/owner/settings"
            aria-label="Settings"
            className="absolute right-3 top-3 grid size-9 place-items-center rounded-full bg-black/35 text-white backdrop-blur-sm transition-colors hover:bg-black/50"
          >
            <Settings className="size-5" aria-hidden />
          </Link>
          <div className="absolute -bottom-8 left-4">
            <VerifiedScene scene={useCase.profileScene} size="lg" />
          </div>
        </div>
        <div className="px-4 pb-4 pt-10">
          <h1 className="truncate text-xl font-semibold tracking-tight">{demoBusiness.name}</h1>
          <p className="text-sm text-muted-foreground">{demoBusiness.tagline}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
              <span className="font-medium text-foreground">{demoBusiness.rating.toFixed(1)}</span>
              ({demoBusiness.reviewCount})
            </span>
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3.5" aria-hidden /> {demoBusiness.city}
            </span>
            <span className="rounded bg-muted px-1.5 py-0.5">{useCase.label}</span>
          </div>
        </div>
      </div>

      {/* About */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">About</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">{demoBusiness.bio}</p>
      </div>

      {/* Links & socials */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Links</h2>
        <div className="flex flex-wrap gap-2">
          {socials.map((s) => (
            <a
              key={s.label}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted"
            >
              {s.label === "Website" ? <Globe className="size-3.5" aria-hidden /> : <ExternalLink className="size-3.5" aria-hidden />}
              <span className="font-medium">{s.label}</span>
              <span className="text-muted-foreground">{s.handle}</span>
            </a>
          ))}
        </div>
      </div>

      {/* Gallery */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Gallery</h2>
        <div className="grid grid-cols-3 gap-2">
          {gallery.map((m) => (
            <figure key={m.id} className="overflow-hidden rounded-xl border border-border">
              <div className="aspect-square">
                <BusinessArt scene={m.scene} />
              </div>
              <figcaption className="truncate px-2 py-1 text-[11px] text-muted-foreground">{m.title}</figcaption>
            </figure>
          ))}
        </div>
      </div>

      {/* Videos */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Videos</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {videos.map((m) => (
            <figure key={m.id} className="overflow-hidden rounded-xl border border-border">
              <div className="relative aspect-video">
                <BusinessArt scene={m.scene} />
                <span className="absolute inset-0 grid place-items-center">
                  <span className="grid size-10 place-items-center rounded-full bg-black/45 text-white backdrop-blur-sm">
                    <Play className="size-5 translate-x-0.5 fill-white" aria-hidden />
                  </span>
                </span>
              </div>
              <figcaption className="truncate px-2 py-1.5 text-xs">{m.title}</figcaption>
            </figure>
          ))}
        </div>
      </div>

      {/* Reviews */}
      <div>
        <h2 className="mb-2 text-sm font-semibold">Reviews</h2>
        <ul className="space-y-3">
          {reviews.map((rv) => (
            <li key={rv.id} className="rounded-2xl border border-border bg-card p-3">
              <div className="flex items-center gap-2">
                <AvatarImg src={rv.avatarUrl} alt="" className="size-8" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{rv.author}</span>
                    <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                      <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                      {rv.rating.toFixed(1)}
                    </span>
                  </div>
                  <span className="text-[11px] text-muted-foreground">{rv.whenLabel}</span>
                </div>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{rv.text}</p>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Showcase content is demo data for the selected use case. Switch use cases in Settings → Demo.
      </p>
    </section>
  );
}
