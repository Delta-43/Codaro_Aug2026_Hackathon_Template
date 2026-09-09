// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * "What you can pivot" chapter, the config blocks that decide how the product
 * behaves, which is the whole pitch. Same plate + indicator-icon pattern as the
 * other chapters; each block is an interactive tile whose hover feel comes from
 * `buttonFx.plate`, not an inline hover string (see frontend/CLAUDE.md).
 *
 * Fixed page copy, deliberately: this markets the engine, so it must read the
 * same whatever `domain.config.json` currently says.
 */
import { Blocks, Boxes, CalendarClock, Coins, CreditCard, MapPin, ShieldCheck } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

const PRODUCTS = [
  {
    icon: CalendarClock,
    title: "Booking",
    body: "Unit kind, granularity, duration, party size and add-ons. A 30-minute appointment and a seven-night stay are the same row with different config.",
  },
  {
    icon: Coins,
    title: "Pricing",
    body: "Per hour, per night, per person, per unit, tiered, quoted or free. Fees, caps and deposits ride along.",
  },
  {
    icon: CreditCard,
    title: "Payments",
    body: "Prepay, pay on site, invoice after, split or none. Deposit schedules and no-show fees included.",
  },
  {
    icon: Boxes,
    title: "Inventory",
    body: "None, finite, rentable, consumable or serialised. A hire fleet and a hair salon need different answers.",
  },
  {
    icon: MapPin,
    title: "Location",
    body: "On-site, at the customer, remote, delivery or pickup, plus the business timezone and service area.",
  },
  {
    icon: ShieldCheck,
    title: "Prerequisites",
    body: "ID checks, intake forms, waivers, memberships and owner approval, gated per service rather than globally.",
  },
];

export function Products() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section
      id="services"
      className="flex min-h-[92vh] snap-start snap-always scroll-mt-24 items-center px-4 py-20"
    >
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          <div className="mb-6 flex justify-center">
            <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <Blocks className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Change the file. Not the code.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-center text-foreground/80">
            Eleven config blocks decide how the engine behaves, and every one can be overridden per service. One deployment can host businesses that work nothing alike.
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PRODUCTS.map((p) => (
              <div
                key={p.title}
                className={cn(
                  "group flex flex-col rounded-2xl border border-border/60 bg-card/60 p-5 backdrop-blur-sm",
                  buttonFx.plate,
                )}
              >
                <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground">
                  <p.icon className="size-5" aria-hidden />
                </span>
                <h3 className="mt-4 text-base font-semibold text-foreground">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-foreground/80">{p.body}</p>
              </div>
            ))}
          </div>

          <p className="mx-auto mt-8 max-w-lg text-center text-sm text-foreground/60">
            The database never changes at the pivot. New domain fields go in a metadata JSON column, so switching business needs no migration.
          </p>
        </GlassPanel>
      </div>
    </section>
  );
}
