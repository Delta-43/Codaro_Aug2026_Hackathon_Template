"use client";

/**
 * Docs chapter — a short "how it actually works" explainer that links out to
 * the full /docs guide. Sits between the reviews and the closing CTA; the nav's
 * "Docs" link also routes to /docs, this plate is the in-page teaser for it.
 */
import { ArrowRight, BookOpen } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "";

export function DocsCta() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  return (
    <section id="docs" className="flex min-h-[92vh] snap-start scroll-mt-24 items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="flex flex-col items-center gap-6 px-6 py-14 text-center sm:px-10">
          <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
            <BookOpen className="size-6" aria-hidden />
          </span>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Curious how it works?
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-foreground/80">
              One config file sets your vocabulary, rules, pricing, and look; seed data fills the
              catalog. When your business changes, the same engine repivots — no rewrite. The docs
              walk through the config, the API, and the whole booking pipeline end to end.
            </p>
          </div>
          <a
            href={`${APP_URL}/docs`}
            className={cn(
              buttonVariants({ size: "lg" }),
              buttonFx.pill,
                  "gap-1.5 px-6",
            )}
          >
            Read the docs
            <ArrowRight className="size-4" aria-hidden />
          </a>
        </GlassPanel>      </div>
    </section>
  );
}
