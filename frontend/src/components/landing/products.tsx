// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * "What we offer" chapter for the funeral-home pivot — a liquid-glass plate of
 * the farewells and keepsakes families reach for most, from the plain (cremation
 * and burial) to the gloriously deadpan (a diamond, a tree, a star, a chatbot).
 * Same plate + indicator-icon pattern as the other chapters; each product is an
 * interactive tile whose hover feel comes from `buttonFx.plate`, not an inline
 * hover string (see frontend/CLAUDE.md).
 */
import { Flame, Flower, Gem, Heart, MessageCircle, Sparkles, TreePine } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

const PRODUCTS = [
  {
    icon: Flame,
    title: "Cremation & Burial",
    body: "The traditional farewells, arranged start to finish. Chapel, hearse, and director included.",
  },
  {
    icon: Gem,
    title: "Ashes-to-Diamond",
    body: "We press the ashes into a certified diamond, so you can keep them close. Available up to one carat.",
  },
  {
    icon: TreePine,
    title: "Memorial Tree",
    body: "Seed a loved one into a living tree and watch them grow. They give back more oxygen than most did in life.",
  },
  {
    icon: Flower,
    title: "Eternal Flowers",
    body: "3D-printed blooms for the service that never wilt, never brown, and never need watering.",
  },
  {
    icon: Sparkles,
    title: "A Star in Their Name",
    body: "Name a star after them. When the grandchildren say grandpa is watching from above, they won't be lying.",
  },
  {
    icon: MessageCircle,
    title: "AI Voice Companion",
    body: "A gentle chatbot built from real recordings, so you can still hear from them on the hard days.",
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
              <Heart className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            What families choose most.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-center text-foreground/80">
            From the simple to the celestial. Every farewell, your way.
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
            …and more, from cryogenic suspension to an orbital committal among the stars.
          </p>
        </GlassPanel>
      </div>
    </section>
  );
}
