"use client";

/**
 * Social-proof chapter — bereaved families on the farewells we arranged for
 * them. Deadpan fictional reviews for the funeral-home pivot (fixed page copy,
 * not engine data / not config-driven), each nodding at one of the products the
 * business offers. Laid out as a horizontal, snap-scrolling row.
 */
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Quote, Star } from "lucide-react";
import { GlassPanel, useScrollMotion } from "@/components/landing/scroll-reveal";
import { cn } from "@/lib/utils";

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
    name: "Margaret Holloway",
    role: "Widow",
    initials: "MH",
    rating: 5,
    message:
      "My Harold is now a one-carat diamond on my finger. He always said he'd put a ring on it eventually. Ashes-to-Diamond, five stars. 💍",
  },
  {
    kind: "review",
    name: "Piotr Kowalczyk",
    role: "Bereaved son",
    initials: "PK",
    rating: 5,
    message:
      "We planted Dad as an oak. He's finally putting down roots and giving back oxygen, which is more than he managed in life. The memorial tree is lovely.",
  },
  {
    kind: "review",
    name: "Deborah Vance",
    role: "Next of kin",
    initials: "DV",
    rating: 5,
    message:
      "Bought Mum a star in her name. My kids can now honestly say grandma is watching over them from up there. Made a childhood dream come true. ⭐",
  },
  {
    kind: "review",
    name: "Alban Mercier",
    role: "Estate executor",
    initials: "AM",
    rating: 5,
    message:
      "Nana still texts me happy birthday. The AI voice companion nailed her passive-aggression perfectly. Genuinely can't tell the difference.",
  },
  {
    kind: "review",
    name: "The Ashcombe Family",
    role: "The whole family",
    initials: "AF",
    rating: 5,
    message:
      "No date to choose, no decisions, no stress. A director rang within the week and handled everything. Discreet, punctual, done. Thank you. 🕊️",
  },
];

export function Testimonials() {
  const { ref, style } = useScrollMotion<HTMLDivElement>();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  // Same rule as the nav chevrons: track which end of the reviews row we're at,
  // so the matching arrow dims + disables when there's nothing left that way.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => {
      const max = el.scrollWidth - el.clientWidth;
      setAtStart(el.scrollLeft <= 1);
      setAtEnd(el.scrollLeft >= max - 1);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.addEventListener("scroll", measure, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", measure);
    };
  }, []);

  return (
    <section id="reviews" className="flex min-h-[92vh] snap-start snap-always scroll-mt-24 items-center px-4 py-20">
      <div ref={ref} style={style} className="mx-auto w-full max-w-4xl">
        <GlassPanel className="px-6 py-12 sm:px-10 sm:py-14">
          <div className="mb-6 flex justify-center">
            <span className="flex size-12 origin-center cursor-pointer items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm transition-all duration-200 ease-out hover:scale-[1.4] hover:-translate-y-1 hover:bg-primary hover:text-primary-foreground hover:shadow-xl">
              <Quote className="size-6" aria-hidden />
            </span>
          </div>
          <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Families we&apos;ve helped say goodbye.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-center text-foreground/80">
            Real farewells, in the words of the bereaved.
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
                  className="flex w-72 shrink-0 snap-start snap-always flex-col rounded-2xl border border-border/60 bg-card/60 p-5 backdrop-blur-sm sm:w-80"
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
                  className="flex w-72 shrink-0 snap-start snap-always flex-col items-center justify-center rounded-2xl border border-dashed border-border p-5 text-center sm:w-80"
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
            {/* Scrollable affordance — left. No gradient scrim: in dark mode a
                `background`-based fade renders as a near-black band the cards
                scroll under. The chevron carries its own glass bg, so it reads
                fine on its own. */}
            <div className="pointer-events-none absolute inset-y-0 left-0 flex w-16 items-center justify-start pl-1">
              <button
                type="button"
                aria-label="Scroll reviews left"
                disabled={atStart}
                onClick={() => scrollRef.current?.scrollBy({ left: -320, behavior: "smooth" })}
                className="pointer-events-auto grid size-8 origin-center place-items-center rounded-full border border-white/30 bg-background/60 text-foreground shadow-sm ring-1 ring-inset ring-white/20 backdrop-blur-md transition-all duration-200 ease-out hover:scale-125 disabled:pointer-events-none disabled:opacity-25"
              >
                <ChevronLeft className={cn("size-4", !atStart && "landing-nudge-left")} aria-hidden />
              </button>
            </div>
            {/* Scrollable affordance — right (no dark scrim, see left). */}
            <div className="pointer-events-none absolute inset-y-0 right-0 flex w-16 items-center justify-end pr-1">
              <button
                type="button"
                aria-label="Scroll reviews right"
                disabled={atEnd}
                onClick={() => scrollRef.current?.scrollBy({ left: 320, behavior: "smooth" })}
                className="pointer-events-auto grid size-8 origin-center place-items-center rounded-full border border-white/30 bg-background/60 text-foreground shadow-sm ring-1 ring-inset ring-white/20 backdrop-blur-md transition-all duration-200 ease-out hover:scale-125 disabled:pointer-events-none disabled:opacity-25"
              >
                <ChevronRight className={cn("size-4", !atEnd && "landing-nudge")} aria-hidden />
              </button>
            </div>
          </div>
        </GlassPanel>      </div>
    </section>
  );
}
