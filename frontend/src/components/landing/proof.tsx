// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Evidence chapter. Deliberately not testimonials: invented quotes read as
 * customer endorsements on a page that markets the engine, which would be
 * misleading.
 *
 * Everything here is checkable instead. The counts come from the repository
 * (`scripts/check_pivots.py`, the backend suite) and the placing is the
 * hackathon result. Fixed page copy, not engine data.
 */
import { Award, DatabaseZap, FlaskConical, Layers } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

const FACTS = [
  {
    icon: Award,
    stat: "1st place",
    title: "Track B, Codaro x Google for Startups",
    body: "Booking and Resource Scheduling. Built over the length of the hackathon.",
  },
  {
    icon: Layers,
    stat: "11",
    title: "Config blocks, each overridable per service",
    body: "Booking, pricing, payments, inventory, location, prerequisites, timing, recurrence and the rest, so one deployment can host businesses that work nothing alike.",
  },
  {
    icon: FlaskConical,
    stat: "1,260",
    title: "Backend tests",
    body: "Rules resolution, availability, pricing, payments and per-user isolation, run on every push.",
  },
  {
    icon: DatabaseZap,
    stat: "0",
    title: "Migrations to pivot",
    body: "Base tables stay frozen. Anything a new domain needs lives in a metadata JSON column.",
  },
];

export function Proof() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section
      id="proof"
      className="flex min-h-[92vh] snap-start snap-always scroll-mt-24 items-center px-4 py-20"
    >
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          <div className="mb-6 flex justify-center">
            <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <Award className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            The claim, and the evidence for it.
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-center text-foreground/80">
            &ldquo;Pivot the product by editing one file&rdquo; is easy to say. These are the
            numbers behind it.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {FACTS.map((f) => (
              <div
                key={f.title}
                className={cn(
                  "group flex flex-col rounded-2xl border border-border/60 bg-card/60 p-5 backdrop-blur-sm",
                  buttonFx.plate,
                )}
              >
                <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground">
                  <f.icon className="size-5" aria-hidden />
                </span>
                <p className="mt-4 text-2xl font-semibold tracking-tight text-primary">{f.stat}</p>
                <h3 className="mt-0.5 text-base font-semibold text-foreground">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-foreground/80">{f.body}</p>
              </div>
            ))}
          </div>
          <p className="mx-auto mt-8 max-w-lg text-center text-sm text-foreground/60">
            Next.js 14 and FastAPI over hosted Supabase, self-hostable with Docker Compose, AGPL-3.0.
          </p>
        </GlassPanel>
      </div>
    </section>
  );
}
