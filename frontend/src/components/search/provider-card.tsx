"use client";

import { Star } from "lucide-react";
import type { Provider } from "@/types/domain";
import { useVertical } from "@/context/app-context";
import { AvatarImg } from "@/components/avatar-img";
import { distanceFromHome } from "@/lib/geo";
import { cn } from "@/lib/utils";

/** A search result. Followed providers get a distinct highlighted treatment. */
export function ProviderCard({
  provider,
  isFollowed,
  onOpen,
}: {
  provider: Provider;
  isFollowed: boolean;
  onOpen: (p: Provider) => void;
}) {
  const vertical = useVertical();
  const category =
    vertical.categories.find((c) => c.id === provider.categoryId)?.label ?? provider.categoryId;

  return (
    <button
      type="button"
      onClick={() => onOpen(provider)}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors",
        isFollowed
          ? "border-primary/40 bg-accent/40 ring-1 ring-primary/25 hover:bg-accent/60"
          : "border-border bg-card hover:bg-muted/50",
      )}
    >
      <AvatarImg src={provider.avatarUrl} alt="" className="size-12 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{provider.name}</span>
          {isFollowed ? (
            <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              Following
            </span>
          ) : null}
        </div>
        <p className="truncate text-sm text-muted-foreground">{provider.tagline}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="rounded bg-muted px-1.5 py-0.5">{category}</span>
          <span className="inline-flex items-center gap-0.5">
            <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
            {provider.rating.toFixed(1)}
          </span>
          <span>({provider.reviewCount})</span>
          <span aria-hidden>·</span>
          <span>
            {provider.location.city} · {distanceFromHome(provider.location)}
          </span>
        </div>
      </div>
    </button>
  );
}
