"use client";

/**
 * One business's public profile — cover, avatar, meta, follow + message actions,
 * bio, links, and its bookable services. Extracted from the old Services tab so
 * it can be reused as both the "quick view" under the followed strip (bio
 * clamped, with a Show full bio affordance) and the full-screen bio view. Booking
 * a service locks this provider in as the active one, then routes to the calendar
 * — so it works even when the profile shown isn't the one currently locked in.
 */
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, MessageSquare, Star } from "lucide-react";
import type { Provider, Resource, Service } from "@/types/domain";
import { ApiError, getResources, getServices, startConversation } from "@/api";
import { useApp, useVertical } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { useFollow } from "@/hooks/use-follow";
import { AvatarImg } from "@/components/avatar-img";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/skeleton";
import { Button } from "@/components/ui/button";
import { ResourcePicker } from "@/components/provider/resource-picker";
import { formatDuration, formatMoney } from "@/lib/format";
import { distanceFromHome } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";

interface ServiceWithMeta {
  service: Service;
  spots: number | null; // spots per session, for shared_capacity only
}

export function ProviderProfile({
  provider: p,
  clampBio = false,
  onShowFullBio,
  showFollow = true,
}: {
  provider: Provider;
  /** Line-clamp the bio and offer a "Show full bio" button (quick-view mode). */
  clampBio?: boolean;
  onShowFullBio?: () => void;
  showFollow?: boolean;
}) {
  const vertical = useVertical();
  const { selectService, selectResource, lockInProvider, capability } = useApp();
  const router = useRouter();
  const { isFollowing, busy, toggle } = useFollow(p);
  const [picker, setPicker] = useState<Service | null>(null);
  const [messaging, setMessaging] = useState(false);

  // Open (or resume) the client's thread with this business, then jump to it.
  async function messageProvider() {
    setMessaging(true);
    try {
      const conv = await startConversation(p.id);
      router.push(`/messages/${conv.id}`);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Couldn't start a conversation.");
    } finally {
      setMessaging(false);
    }
  }

  const data = useAsync<ServiceWithMeta[]>(async () => {
    const services = await getServices(p.id);
    return Promise.all(
      services.map(async (service) => ({
        service,
        spots:
          service.bookingModel === "shared_capacity"
            ? ((await getResources(service.id))[0]?.capacity ?? null)
            : null,
      })),
    );
  }, [p.id]);

  function handleSelect(service: Service) {
    lockInProvider(p); // the calendar reads the active provider — make it this one
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

  return (
    <section className="pb-2">
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

      {/* Actions — follow + message the business. Follow is additionally gated on
          `capabilities.follows`, which the backend already refuses, so the button
          would otherwise 404. */}
      <div className="mt-4 flex flex-wrap gap-2">
        {showFollow && capability("follows") ? (
          <Button variant={isFollowing ? "secondary" : "outline"} isDisabled={busy} onPress={toggle}>
            {isFollowing ? "Following" : "Follow"}
          </Button>
        ) : null}
        <Button variant="outline" isDisabled={messaging} onPress={messageProvider}>
          <MessageSquare aria-hidden /> Message
        </Button>
      </div>

      {/* Bio */}
      <p
        className={cn(
          "mt-5 text-sm leading-relaxed text-foreground/90",
          clampBio ? "line-clamp-3" : undefined,
        )}
      >
        {p.bio}
      </p>
      {clampBio && onShowFullBio ? (
        <button
          type="button"
          onClick={onShowFullBio}
          className="mt-1 inline-flex items-center gap-0.5 text-sm font-medium text-primary hover:underline"
        >
          Show full bio <ChevronDown className="size-4" aria-hidden />
        </button>
      ) : null}

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
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border border-border bg-card p-3 text-left",
                buttonFx.surface,
              )}
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
