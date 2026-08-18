"use client";

/**
 * Tab 2 — the locked-in provider's profile. Operates only on the active
 * provider; none locked in → purposeful empty state. Selecting a service sets
 * it active and moves to the calendar; for unit_selection a resource picker
 * appears first.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronRight, ExternalLink, MessagesSquare, Star, Store } from "lucide-react";
import type { Resource, Service } from "@/types/domain";
import { ApiError, getResources, getServices, startConversation } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { useFollow } from "@/hooks/use-follow";
import { AvatarImg } from "@/components/avatar-img";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/skeleton";
import { Button } from "@/components/ui/button";
import { ResourcePicker } from "@/components/provider/resource-picker";
import { formatDuration, formatMoney } from "@/lib/format";
import { distanceFromHome } from "@/lib/geo";

interface ServiceWithMeta {
  service: Service;
  spots: number | null; // spots per session, for shared_capacity only
}

export default function ProviderPage() {
  const { activeProvider, vertical, selectService, selectResource } = useApp();
  const router = useRouter();
  const { isFollowing, busy, toggle } = useFollow(activeProvider);
  const [picker, setPicker] = useState<Service | null>(null);
  const [messaging, setMessaging] = useState(false);

  // Open (or resume) the client's thread with this business, then jump to it.
  async function messageProvider() {
    if (!activeProvider) return;
    setMessaging(true);
    try {
      const conv = await startConversation(activeProvider.id);
      router.push(`/bookings/messages/${conv.id}`);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Couldn't start a conversation.");
    } finally {
      setMessaging(false);
    }
  }

  const data = useAsync<ServiceWithMeta[]>(async () => {
    if (!activeProvider) return [];
    const services = await getServices(activeProvider.id);
    return Promise.all(
      services.map(async (service) => ({
        service,
        spots:
          service.bookingModel === "shared_capacity"
            ? ((await getResources(service.id))[0]?.capacity ?? null)
            : null,
      })),
    );
  }, [activeProvider?.id]);

  if (!activeProvider) {
    return (
      <EmptyState
        icon={<Store className="size-8" aria-hidden />}
        title={vertical.copy.noProviderTitle}
        body={vertical.copy.noProviderBody}
        actionHref="/search"
        actionLabel="Go to Search"
      />
    );
  }

  function handleSelect(service: Service) {
    selectService(service);
    if (service.bookingModel === "unit_selection") {
      setPicker(service);
    } else {
      selectResource(null);
      router.push("/calendar");
    }
  }

  function handlePick(resource: Resource | null) {
    selectResource(resource);
    setPicker(null);
    router.push("/calendar");
  }

  const p = activeProvider;

  return (
    <section className="pb-6">
      {/* Cover + avatar */}
      <div
        className="-mx-4 h-32 bg-cover bg-center md:-mx-6 md:rounded-xl"
        style={{ backgroundImage: `url(${p.coverUrl ?? ""})` }}
        aria-hidden
      />
      <div className="-mt-8 flex items-end gap-3 px-1">
        <AvatarImg src={p.avatarUrl} name={p.name} alt="" className="size-20 border-4 border-background" />
        <div className="min-w-0 flex-1 pb-1">
          <h1 className="truncate text-xl font-semibold tracking-tight">{p.name}</h1>
          <p className="truncate text-sm text-muted-foreground">{p.tagline}</p>
        </div>
      </div>

      {/* Meta row */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Star className="size-4 fill-amber-400 text-amber-400" aria-hidden />
          {p.rating.toFixed(1)} ({p.reviewCount})
        </span>
        <span aria-hidden>·</span>
        <span>
          {p.location.city}, {p.location.country} · {distanceFromHome(p.location)}
        </span>
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        <Button
          variant={isFollowing ? "secondary" : "outline"}
          isDisabled={busy}
          onPress={toggle}
        >
          {isFollowing ? "Following" : "Follow"}
        </Button>
        <Button variant="outline" isDisabled={messaging} onPress={messageProvider}>
          <MessagesSquare aria-hidden />
          Message
        </Button>
        <Link
          href="/search"
          className="inline-flex h-8 items-center rounded-2xl border border-border px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          Switch {vertical.providerNoun.toLowerCase()}
        </Link>
      </div>

      {/* Bio */}
      <p className="mt-5 text-sm leading-relaxed text-foreground/90">{p.bio}</p>

      {/* Links */}
      {p.links.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {p.links.map((l) => (
            <a
              key={l.url}
              href={l.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-lg bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              {l.label}
              <ExternalLink className="size-3" aria-hidden />
            </a>
          ))}
        </div>
      ) : null}

      {/* Services */}
      <h2 className="mb-2 mt-7 text-sm font-semibold">{vertical.serviceNounPlural}</h2>
      <div className="space-y-2">
        {data.loading && !data.data ? (
          <>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </>
        ) : data.error ? (
          <EmptyState
            title="Couldn't load"
            body={`We couldn't load the ${vertical.serviceNounPlural.toLowerCase()}.`}
          >
            <Button className="mt-1" onPress={data.reload}>
              Try again
            </Button>
          </EmptyState>
        ) : (
          (data.data ?? []).map(({ service, spots }) => (
            <button
              key={service.id}
              type="button"
              onClick={() => handleSelect(service)}
              className="flex w-full items-center gap-3 rounded-xl border border-border bg-card p-3 text-left transition-colors hover:bg-muted/50"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium">{service.name}</span>
                  <span className="shrink-0 text-sm font-medium">
                    {formatMoney(service.priceMinorUnits, service.currency)}
                  </span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
                  {service.description}
                </p>
                <div className="mt-1 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                  <span>{formatDuration(service.slotDurationMinutes)}</span>
                  {spots !== null ? (
                    <>
                      <span aria-hidden>·</span>
                      <span>{spots} spots per session</span>
                    </>
                  ) : null}
                </div>
              </div>
              <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          ))
        )}
      </div>

      <ResourcePicker
        service={picker}
        open={picker !== null}
        onClose={() => setPicker(null)}
        onPick={handlePick}
      />
    </section>
  );
}
