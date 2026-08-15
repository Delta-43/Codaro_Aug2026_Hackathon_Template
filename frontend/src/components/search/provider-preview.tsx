"use client";

/**
 * Provider preview — discovery, not the full profile (that's Tab 2). Shows a
 * bio excerpt and service list with two actions: Follow (optimistic) and Open
 * (locks in and moves to Tab 2). Vocabulary: Follow applies to providers.
 */
import { useRouter } from "next/navigation";
import type { Provider } from "@/types/domain";
import { getServices } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { useFollow } from "@/hooks/use-follow";
import { Modal } from "@/components/modal";
import { AvatarImg } from "@/components/avatar-img";
import { Skeleton } from "@/components/skeleton";
import { Button } from "@/components/ui/button";
import { formatDuration, formatMoney } from "@/lib/format";

export function ProviderPreview({
  provider,
  open,
  onClose,
}: {
  provider: Provider | null;
  open: boolean;
  onClose: () => void;
}) {
  const { lockInProvider, vertical } = useApp();
  const router = useRouter();
  const { isFollowing, busy, toggle } = useFollow(provider);

  const services = useAsync(
    () => (provider ? getServices(provider.id) : Promise.resolve([])),
    [provider?.id],
  );

  if (!provider) return null;
  const bio =
    provider.bio.length > 180 ? `${provider.bio.slice(0, 177).trimEnd()}…` : provider.bio;

  function openProfile() {
    lockInProvider(provider!);
    onClose();
    router.push("/provider");
  }

  return (
    <Modal open={open} onClose={onClose} title={vertical.providerNoun}>
      <div className="flex items-start gap-3">
        <AvatarImg src={provider.avatarUrl} alt="" className="size-14 shrink-0" />
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold">{provider.name}</h3>
          <p className="truncate text-sm text-muted-foreground">{provider.tagline}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            ★ {provider.rating.toFixed(1)} ({provider.reviewCount}) ·{" "}
            {provider.location.city}
          </p>
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{bio}</p>

      <div className="mt-4">
        <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {vertical.serviceNounPlural}
        </h4>
        <div className="space-y-1.5">
          {services.loading && !services.data ? (
            <>
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-3/4" />
            </>
          ) : services.error ? (
            <p className="text-sm text-destructive">
              Couldn&apos;t load {vertical.serviceNounPlural.toLowerCase()}.
            </p>
          ) : (services.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing listed yet.</p>
          ) : (
            (services.data ?? []).map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2"
              >
                <span className="min-w-0 truncate text-sm font-medium">{s.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDuration(s.slotDurationMinutes)} ·{" "}
                  {formatMoney(s.priceMinorUnits, s.currency)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="mt-5 flex gap-2">
        <Button
          variant={isFollowing ? "secondary" : "outline"}
          className="flex-1"
          isDisabled={busy}
          onPress={toggle}
        >
          {isFollowing ? "Following" : "Follow"}
        </Button>
        <Button className="flex-1" onPress={openProfile}>
          Open
        </Button>
      </div>
    </Modal>
  );
}
