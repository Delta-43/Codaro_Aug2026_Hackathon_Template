"use client";

/**
 * Tab 2 — Services. In the marketplace this is the customer's followed-businesses
 * home (top-3 strip + quick view + drill-in), handled by <FollowingServices>. In
 * single-business mode, or before the customer follows anyone, it falls back to a
 * single business profile. Booking a service still locks that provider in and
 * moves to the calendar (inside <ProviderProfile>).
 */
import { Store } from "lucide-react";
import { useApp, useVertical } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";
import { ProviderProfile } from "@/components/provider/provider-profile";
import { FollowingServices } from "@/components/provider/following-services";

export default function ProviderPage() {
  const { activeProvider, singleBusiness, user } = useApp();
  const vertical = useVertical();
  const followedIds = user?.followedProviderIds ?? [];

  // Marketplace + at least one follow → the followed-businesses experience.
  if (!singleBusiness && followedIds.length > 0) {
    return <FollowingServices followedIds={followedIds} />;
  }

  // Single-business mode, or a marketplace customer who follows no one yet: show
  // the locked-in business profile if there is one.
  if (activeProvider) {
    return (
      <div className="py-4">
        <ProviderProfile provider={activeProvider} clampBio={false} showFollow={!singleBusiness} />
      </div>
    );
  }

  // Nothing to show. Single mode has no discovery, so drop the Search action.
  return (
    <EmptyState
      icon={<Store className="size-8" aria-hidden />}
      title={vertical.copy.noProviderTitle}
      body={
        singleBusiness
          ? vertical.copy.noProviderBody
          : "Search for a business and follow it — the ones you follow show up here."
      }
      actionHref={singleBusiness ? undefined : "/search"}
      actionLabel={singleBusiness ? undefined : "Go to Search"}
    />
  );
}
