/**
 * The gold "Business" chip that rides beside the Arbor wordmark.
 *
 * It used to be written inline in two places with two different type
 * treatments — a 10px uppercase, letter-spaced chip on the sign-in plate and a
 * 12px sentence-case one in the console shell — so the same tag read as two
 * different marks depending on where you saw it. Here it is one component that
 * borrows the wordmark's own typography: same weight, same tight tracking, same
 * sentence case, so it reads as the second word of the lockup rather than a
 * badge stapled to it. Only the colour separates them, which is the point — the
 * gold is what says "business account".
 *
 * The chip also carries a small downward nudge: flex centering puts it on the
 * line box's middle, which sits a touch above the optical middle of a
 * cap-height-only word like "Arbor". The nudge is in `em` too, so it stays
 * proportional at every size the lockup is used at.
 *
 * The chip's own `ml` is the *only* gap back to the wordmark — both call sites
 * space the mark and the word themselves rather than putting a `gap` on the
 * lockup row, so nothing stacks on top of this one number. It is deliberately
 * tight: "Arbor Business" should read as one lockup, not a word and a separate
 * badge.
 *
 * Everything is sized in `em`, so the chip scales with whatever font-size the
 * wordmark is set at (1.125rem in the shell, 1.5rem on the sign-in plate)
 * instead of two hand-tuned pixel sizes drifting apart on the next tweak.
 */
import { cn } from "@/lib/utils";

export function BusinessTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "ml-[0.35em] rounded-full bg-amber-400/15 px-[0.55em] py-[0.2em] text-[0.62em]",
        "font-semibold leading-none tracking-tight text-amber-600 dark:text-amber-400",
        "translate-y-[0.12em]",
        className,
      )}
    >
      Business
    </span>
  );
}
