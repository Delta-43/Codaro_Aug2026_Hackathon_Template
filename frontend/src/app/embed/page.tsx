"use client";

/**
 * The embed's landing screen: the pinned business's profile + bookable
 * services. Always single-tenant (an embed adopter runs their own deployment
 * pinned via tenancy.mode: "single" + providerCode — see plugin_sdk/CLAUDE.md),
 * so unlike (app)/provider/page.tsx there's no marketplace/FollowingServices
 * branch to handle.
 */
import { Store } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";
import { ProviderProfile } from "@/components/provider/provider-profile";

export default function EmbedProfilePage() {
  const { activeProvider, ready } = useApp();

  if (!ready) {
    return <div className="py-10 text-center text-sm text-muted-foreground">Loading…</div>;
  }

  if (!activeProvider) {
    return (
      <EmptyState
        icon={<Store className="size-8" aria-hidden />}
        title="Nothing to book yet"
        body="This business isn't set up for booking yet."
      />
    );
  }

  return (
    <div className="py-2">
      <ProviderProfile
        provider={activeProvider}
        clampBio={false}
        showFollow={false}
        showMessage={false}
        calendarHref="/embed/calendar"
      />
    </div>
  );
}
