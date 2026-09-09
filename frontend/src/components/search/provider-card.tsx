// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { Star } from "lucide-react";
import type { Provider } from "@/types/domain";
import { useVertical } from "@/context/app-context";
import { AvatarImg } from "@/components/avatar-img";
import { distanceFromHome } from "@/lib/geo";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";

/** A search result. Followed providers get a distinct highlighted treatment. */
export function ProviderCard({
  provider,
  isFollowed,
  onOpen,
  showPrice = true,
  showDistance = true,
}: {
  provider: Provider;
  isFollowed: boolean;
  onOpen: (p: Provider) => void;
  /** Facet gates, a free/remote vertical hides price/distance on the card. */
  showPrice?: boolean;
  showDistance?: boolean;
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
          ? "border-primary/40 bg-accent/30 hover:border-primary hover:bg-accent/60 hover:ring-1 hover:ring-primary/30"
          : cn("border-border bg-card", buttonFx.surface),
      )}
    >
      <AvatarImg src={provider.avatarUrl} name={provider.name} alt="" className="size-12 shrink-0" />
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
          {provider.location.city || showDistance ? (
            <>
              <span aria-hidden>·</span>
              <span>
                {[
                  provider.location.city,
                  showDistance ? distanceFromHome(provider.location) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </>
          ) : null}
          {showPrice && provider.priceFromMinorUnits != null ? (
            <>
              <span aria-hidden>·</span>
              <span>from {formatMoney(provider.priceFromMinorUnits, provider.currency)}</span>
            </>
          ) : null}
        </div>
      </div>
    </button>
  );
}
