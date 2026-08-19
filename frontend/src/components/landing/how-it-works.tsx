"use client";

/**
 * "How it works" chapter — three steps that mirror the pipeline the hero
 * terminal shows (configure → seed → go live). Uses only the engine's neutral
 * spine nouns (providers/services), never a vertical-specific term.
 */
import { Rocket, Settings2, Sparkles, Zap } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { Dock, DockItem } from "@/components/landing/dock";

const STEPS = [
  {
    icon: Settings2,
    title: "Configure",
    body: "Set your vocabulary, rules, and look in one config file — no code, no rewrite.",
  },
  {
    icon: Sparkles,
    title: "Seed",
    body: "Load your providers, services, and availability. Your catalog is ready in minutes.",
  },
  {
    icon: Rocket,
    title: "Go live",
    body: "Share your link. Customers browse, pick a slot, and book — instantly.",
  },
];

export function HowItWorks() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section id="how" className="flex min-h-[92vh] snap-start snap-always scroll-mt-24 items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          <div className="mb-6 flex justify-center">
            <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <Zap className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            From idea to booking in three steps.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-center text-foreground/80">
            The same pipeline, whatever business you run.
          </p>

          <Dock className="mt-10 grid gap-8 sm:grid-cols-3">
            {STEPS.map((step, i) => (
              <div key={step.title} className="text-center">
                <DockItem className="mx-auto flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm hover:bg-primary hover:text-primary-foreground">
                  <step.icon className="size-5" aria-hidden />
                </DockItem>
                <p className="mt-4 text-xs font-medium uppercase tracking-wide text-foreground/70">
                  Step {i + 1}
                </p>
                <h3 className="mt-1 text-lg font-medium text-foreground">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-foreground/80">{step.body}</p>
              </div>
            ))}
          </Dock>
        </GlassPanel>      </div>
    </section>
  );
}
