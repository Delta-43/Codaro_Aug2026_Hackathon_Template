import { createElement } from "react";

import type { Provider, Service } from "@/types/domain";
import { buttonFx } from "@/config/buttons";
import { formatOffer } from "@/lib/format";
import { getServiceAnimation } from "@/components/showcase/animations";
import { ScrollZoomReveal } from "@/components/showcase/scroll-zoom";
import { getServiceTagline } from "@/components/showcase/showcase-copy";
import { cinzel, showcaseDisplayClass } from "@/components/showcase/showcase-fonts";
import { cn } from "@/lib/utils";

/**
 * One row in the `/showcase` catalogue list: a full-width "scene" pairing a
 * bespoke animation authored for this exact service (looked up by name via
 * `getServiceAnimation` — a curated one-to-one map, not a shared taxonomy of
 * reusable icon "kinds") with the service's name/description/price and —
 * when a provider record is available — a small byline.
 *
 * Alternates icon/text sides on even/odd `index` for an Apple-product-page
 * rhythm (icon left on even rows, right on odd), stacking to a single column
 * on mobile where there's no room for a side-by-side row. The whole row is
 * wrapped in `ScrollZoomReveal` so it zooms/fades in as it's scrolled to —
 * deliberately no `backdrop-filter`/`.liquid-glass` on the wrapped element
 * (combining a scroll-driven transform with a blur broke compositing here
 * before; see `useScrollMotion` in `components/landing/scroll-reveal.tsx`),
 * so the card treatment below is a solid/translucent fill instead of glass.
 *
 * Never touches `service.imageUrl`: the animation *is* the artwork here.
 */
export function ServicePanel({
  service,
  provider,
  index = 0,
}: {
  service: Service;
  provider?: Provider;
  /** Row position within the list — even rows put the animation on the left,
   *  odd rows flip it to the right. Defaults to 0 (icon-left) when omitted. */
  index?: number;
}) {
  const reversed = index % 2 === 1;
  const tagline = getServiceTagline(service.name);

  return (
    <ScrollZoomReveal className="w-full">
      <div
        className={cn(
          "flex w-full flex-col items-center gap-8 rounded-[2rem] border border-white/10 bg-white/[0.03] px-6 py-12",
          "sm:min-h-[78vh] sm:flex-row sm:gap-14 sm:px-12 sm:py-20",
          "lg:min-h-[85vh] lg:gap-20 lg:px-16",
          reversed && "sm:flex-row-reverse",
          buttonFx.plate,
        )}
      >
        <div className="flex shrink-0 items-center justify-center">
          {/* `createElement` rather than `const Animation = …; <Animation />`:
              the lookup returns a module-level component, but assigning it to a
              local and rendering it as JSX reads to react-hooks/static-components
              as a component created during render. */}
          {createElement(getServiceAnimation(service.name), {
            className: "size-40 sm:size-48 lg:size-56",
          })}
        </div>
        <div className="flex max-w-xl flex-1 flex-col items-center gap-4 text-center sm:items-start sm:text-left">
          {tagline ? (
            <p
              className={cn(
                "text-xs font-semibold uppercase tracking-[0.2em] text-primary/70",
                cinzel.variable,
                showcaseDisplayClass,
              )}
            >
              {tagline}
            </p>
          ) : null}
          <h3 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {service.name}
          </h3>
          <p className="text-base text-muted-foreground sm:text-lg">
            {service.description}
          </p>
          <p className="text-lg font-medium text-primary">{formatOffer(service)}</p>
          {provider ? (
            <p className="text-sm text-muted-foreground/80">by {provider.name}</p>
          ) : null}
        </div>
      </div>
    </ScrollZoomReveal>
  );
}
