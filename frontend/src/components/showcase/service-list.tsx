"use client";

import { getServices, searchProviders } from "@/api";
import { useAsync } from "@/hooks/use-async";
import { EmptyState } from "@/components/empty-state";
import { InlineMessage } from "@/components/ui/inline-message";
import { Skeleton } from "@/components/skeleton";
import { Button } from "@/components/ui/button";
import { ServicePanel } from "@/components/showcase/service-panel";
import { EMPTY_STATE_TITLE, EMPTY_STATE_BODY } from "@/components/showcase/showcase-copy";
import type { Provider, Service } from "@/types/domain";

const SKELETON_COUNT = 4;

/**
 * The `/showcase` catalogue: every service across every provider, rendered as
 * a single-column list of full-width `ServicePanel` rows (icon/creature on
 * one side, text on the other, alternating per row — see `ServicePanel`).
 * Both calls are public (no auth), so this renders the same for a logged-out
 * visitor as a signed-in one.
 */
export function ServiceList() {
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([getServices(), searchProviders({})]),
    [],
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-16 sm:gap-24">
        {Array.from({ length: SKELETON_COUNT }, (_, i) => (
          <Skeleton key={i} className="h-[60vh] rounded-[2rem] sm:h-[78vh]" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <InlineMessage tone="error" live="polite">
        <div className="flex flex-col items-start gap-2">
          <span>{error instanceof Error ? error.message : String(error)}</span>
          <Button size="sm" variant="outline" onPress={reload}>
            Retry
          </Button>
        </div>
      </InlineMessage>
    );
  }

  const [services, providers] = data as [Service[], Provider[]];

  if (services.length === 0) {
    return (
      <EmptyState title={EMPTY_STATE_TITLE} body={EMPTY_STATE_BODY} />
    );
  }

  const providerById = new Map<string, Provider>(providers.map((p) => [p.id, p]));

  return (
    <div className="flex flex-col gap-16 sm:gap-24">
      {services.map((service, i) => (
        <ServicePanel
          key={service.id}
          service={service}
          provider={providerById.get(service.providerId)}
          index={i}
        />
      ))}
    </div>
  );
}
