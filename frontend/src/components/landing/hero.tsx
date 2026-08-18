"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PipelineTerminal } from "@/components/landing/pipeline-terminal";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { ScrollCue } from "@/components/landing/scroll-cue";

/**
 * Above-the-fold pitch for the product — deliberately vertical-agnostic (no
 * provider/service/resource nouns from any one vertical). One liquid-glass
 * plate (copy + terminal) over the scene, plus a scroll cue to the next plate.
 */
export function Hero({ authed }: { authed: boolean }) {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section className="flex min-h-[92vh] snap-start items-center px-4 pt-24 pb-12 sm:pt-28">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="flex flex-col items-center gap-10 px-6 py-12 text-center sm:px-10 sm:py-14">
          <div>
            <p className="text-lg font-bold tracking-tight sm:text-xl">
              <span className="inline-block origin-center cursor-pointer text-primary transition-transform duration-200 ease-out hover:scale-125">
                service.com
              </span>
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              One booking engine. Built for every business.
            </h1>
            <p className="mx-auto mt-4 max-w-md text-foreground/80">
              One engine, infinite businesses — booking, scheduling, and availability, reshaped
              instantly for the business you&apos;re building.
            </p>
            <div className="mt-8 flex justify-center">
              <Link
                href={authed ? "/search" : "/login"}
                className={cn(
                  buttonVariants({ size: "lg" }),
                  "origin-center gap-1.5 rounded-full px-6 transition-transform duration-200 ease-out hover:scale-105",
                )}
              >
                {authed ? "Open app" : "Get Started"}
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </div>
          </div>
          <PipelineTerminal />
        </GlassPanel>

        <ScrollCue />
      </div>
    </section>
  );
}
