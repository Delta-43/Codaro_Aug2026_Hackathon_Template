"use client";

/**
 * Optimistic follow/unfollow for a provider, shared by the search preview and
 * the profile header. Follow applies to providers (never "subscribe").
 */
import { useState } from "react";
import type { Provider } from "@/types/domain";
import { followProvider, unfollowProvider } from "@/api";
import { useApp } from "@/context/app-context";

export function useFollow(provider: Provider | null) {
  const { user, setUser } = useApp();
  const [busy, setBusy] = useState(false);
  const isFollowing = !!(provider && user?.followedProviderIds.includes(provider.id));

  async function toggle() {
    if (!provider || !user || busy) return;
    setBusy(true);
    const prev = user;
    const nextFollowed = isFollowing
      ? user.followedProviderIds.filter((id) => id !== provider.id)
      : [...user.followedProviderIds, provider.id];
    setUser({ ...user, followedProviderIds: nextFollowed }); // optimistic
    try {
      setUser(
        isFollowing ? await unfollowProvider(provider.id) : await followProvider(provider.id),
      );
    } catch {
      setUser(prev); // revert on failure
    } finally {
      setBusy(false);
    }
  }

  return { isFollowing, busy, toggle };
}
