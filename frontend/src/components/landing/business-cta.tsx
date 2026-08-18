"use client";

/**
 * Owner-facing pitch — the closing call to action. Its button is the one
 * sign-in entry point down here (the mid-page login buttons were removed), so
 * a visitor who's read the whole page still has a clear way in.
 */
import Link from "next/link";
import { ArrowRight, Building2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";

export function BusinessCta({ authed }: { authed: boolean }) {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section className="flex min-h-[92vh] snap-start items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="flex flex-col items-center gap-6 px-6 py-14 text-center sm:px-10">
          <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
            <Building2 className="size-6" aria-hidden />
          </span>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Run a business? Bring it to service.com.
            </h2>
            <p className="mx-auto mt-3 max-w-md text-foreground/80">
              List your business, set your own rules, and start taking bookings. The engine adapts
              to you — not the other way around.
            </p>
          </div>
          <Link
            href={authed ? "/search" : "/login"}
            className={cn(
              buttonVariants({ size: "lg" }),
              "origin-center gap-1.5 rounded-full px-6 transition-transform duration-200 ease-out hover:scale-105",
            )}
          >
            {authed ? "Open app" : "Sign in"}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </GlassPanel>
      </div>
    </section>
  );
}
