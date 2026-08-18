"use client";

/**
 * Social-proof chapter — the team behind Codaro, in their own words. These are
 * real teammate reviews (fixed page copy, not engine data / not config-driven);
 * two slots are left open for teammates still to add theirs. Laid out as a
 * horizontal, snap-scrolling row.
 */
import { useRef } from "react";
import { ChevronLeft, ChevronRight, Star } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { ScrollCue } from "@/components/landing/scroll-cue";

type Review =
  | {
      kind: "review";
      name: string;
      role: string;
      initials: string;
      rating: number;
      message: string;
    }
  | { kind: "placeholder" };

const REVIEWS: Review[] = [
  {
    kind: "review",
    name: "Aryna Bobryk",
    role: "Jobless · Student · 42 attendee",
    initials: "AB",
    rating: 5,
    message:
      "Great platform, I really enjoyed working on it, endless possibilities for businesses, great team i worked with, recommend it for sure! ;)",
  },
  {
    kind: "review",
    name: "Philip Warda",
    role: "Music teacher",
    initials: "PW",
    rating: 5,
    message:
      "service.com is an amazing platform, it offers awesome functionality specifically for ease of use for the business and a user. I really like how flexible and functional it is, and how it makes getting information about what you want super easy. Overall I really recommend service.com",
  },
  {
    kind: "review",
    name: "Alban Billiette",
    role: "Unemployed",
    initials: "AB",
    rating: 5,
    message:
      "service.com is amazing because I really like programming, crocs and also my hackathon group, yayyy",
  },
  { kind: "placeholder" },
  { kind: "placeholder" },
];

export function Testimonials() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  const scrollRef = useRef<HTMLDivElement>(null);
  return (
    <section id="reviews" className="flex min-h-[92vh] snap-start scroll-mt-24 items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Built for every business — and it shows.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-center text-foreground/80">
            The team that built service.com, in their own words.
          </p>

          <div className="relative mt-10">
            <div
              ref={scrollRef}
              className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {REVIEWS.map((review, i) =>
              review.kind === "review" ? (
                <figure
                  key={review.name}
                  className="flex w-72 shrink-0 snap-start flex-col rounded-2xl border border-border/60 bg-card/60 p-5 backdrop-blur-sm sm:w-80"
                >
                  <div className="flex gap-0.5" aria-label={`${review.rating} out of 5 stars`}>
                    {Array.from({ length: review.rating }).map((_, s) => (
                      <Star
                        key={s}
                        className="size-4 origin-center cursor-pointer fill-primary text-primary transition-transform duration-200 ease-out hover:scale-150"
                        aria-hidden
                      />
                    ))}
                  </div>
                  <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-foreground">
                    “{review.message}”
                  </blockquote>
                  <figcaption className="mt-5 flex items-center gap-3">
                    <span className="flex size-9 shrink-0 origin-center cursor-pointer items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary shadow-sm transition-transform duration-200 ease-out hover:scale-[1.6] hover:bg-primary hover:text-primary-foreground hover:shadow-lg">
                      {review.initials}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-foreground">
                        {review.name}
                      </span>
                      <span className="block truncate text-xs text-foreground/70">
                        {review.role}
                      </span>
                    </span>
                  </figcaption>
                </figure>
              ) : (
                <div
                  key={`placeholder-${i}`}
                  className="flex w-72 shrink-0 snap-start flex-col items-center justify-center rounded-2xl border border-dashed border-border p-5 text-center sm:w-80"
                >
                  <span className="flex size-9 items-center justify-center rounded-full border border-dashed border-border text-muted-foreground">
                    +
                  </span>
                  <p className="mt-3 text-sm font-medium text-foreground/70">
                    A teammate&apos;s review, coming soon
                  </p>
                </div>
                ),
              )}
            </div>
            {/* Scrollable affordance — left */}
            <div className="pointer-events-none absolute inset-y-0 left-0 flex w-16 items-center justify-start bg-gradient-to-r from-background/70 to-transparent pl-1">
              <button
                type="button"
                aria-label="Scroll reviews left"
                onClick={() => scrollRef.current?.scrollBy({ left: -320, behavior: "smooth" })}
                className="pointer-events-auto grid size-8 origin-center place-items-center rounded-full border border-white/30 bg-background/60 text-foreground shadow-sm ring-1 ring-inset ring-white/20 backdrop-blur-md transition-transform duration-200 ease-out hover:scale-125"
              >
                <ChevronLeft className="landing-nudge-left size-4" aria-hidden />
              </button>
            </div>
            {/* Scrollable affordance — right */}
            <div className="pointer-events-none absolute inset-y-0 right-0 flex w-16 items-center justify-end bg-gradient-to-l from-background/70 to-transparent pr-1">
              <button
                type="button"
                aria-label="Scroll reviews right"
                onClick={() => scrollRef.current?.scrollBy({ left: 320, behavior: "smooth" })}
                className="pointer-events-auto grid size-8 origin-center place-items-center rounded-full border border-white/30 bg-background/60 text-foreground shadow-sm ring-1 ring-inset ring-white/20 backdrop-blur-md transition-transform duration-200 ease-out hover:scale-125"
              >
                <ChevronRight className="landing-nudge size-4" aria-hidden />
              </button>
            </div>
          </div>
        </GlassPanel>
        <ScrollCue />
      </div>
    </section>
  );
}
