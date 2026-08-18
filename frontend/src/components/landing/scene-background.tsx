"use client";

/**
 * Full-page, theme-aware scenery behind the whole landing page.
 *   light → /public/scene-day.jpg  + a soft warm sun glow (no hard rays)
 *   dark  → /public/scene-night.jpg + flowing aurora curtains
 * Both modes get gently drifting petals. Fixed, so the glass chapters float
 * and frost over it. All motion is pure CSS, disabled under
 * prefers-reduced-motion.
 *
 * Day↔night crossfade: both photos (and the sun / aurora layers) stay mounted
 * and we animate their `opacity` — `background-image` and `display` can't be
 * transitioned. The active layer is chosen by our own `dark` state, NOT the
 * `.dark` class: the ThemeProvider runs `disableTransitionOnChange`, which
 * injects a one-frame `transition: none !important` around the class swap that
 * would otherwise kill the fade. We read `resolvedTheme` and commit the flip
 * inside `requestAnimationFrame`, one frame later, once that suppression style
 * is gone — so only this background crossfades while the rest of the app still
 * swaps instantly.
 */
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

const PETALS = Array.from({ length: 30 }, (_, i) => ({
  left: `${(i * 3.27 + 2) % 99}%`,
  size: 4 + ((i * 7) % 8),
  delay: (i * 1.1) % 15,
  dur: 12 + ((i * 5) % 11),
  o: 0.45 + ((i * 3) % 5) / 10,
}));

// Vertical aurora "curtains" — each waves independently for a flowing look.
const CURTAINS = [
  { left: 6, w: 15, h: 66, delay: 0, dur: 8.5, c: "74,222,160" },
  { left: 20, w: 12, h: 58, delay: 1.6, dur: 11, c: "45,212,191" },
  { left: 35, w: 18, h: 70, delay: 0.7, dur: 7.5, c: "74,222,160" },
  { left: 52, w: 13, h: 60, delay: 2.4, dur: 12.5, c: "129,236,255" },
  { left: 66, w: 16, h: 67, delay: 1.1, dur: 9.5, c: "45,212,191" },
  { left: 82, w: 13, h: 56, delay: 3, dur: 10.5, c: "74,222,160" },
];

export function SceneBackground() {
  const { resolvedTheme } = useTheme();
  // Start light so SSR (no theme class) and the first client render match; the
  // effect below reconciles to the real theme (a soft fade-in for dark users).
  const [dark, setDark] = useState(false);

  useEffect(() => {
    // Defer one frame past next-themes' `disableTransitionOnChange` suppression
    // so the opacity change actually animates instead of snapping.
    const id = requestAnimationFrame(() => setDark(resolvedTheme === "dark"));
    return () => cancelAnimationFrame(id);
  }, [resolvedTheme]);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Day photo — permanent OPAQUE base. It never fades, so there's always a
          fully-covering image under the crossfade; the page background can't
          bleed through mid-transition (that was the black/white flash). */}
      <div className="absolute inset-0 bg-[url('/scene-day.jpg')] bg-cover bg-center bg-no-repeat" />
      {/* Night photo — the only thing that fades: opacity 0→1 dissolves it in
          over the opaque day image (and back out), a natural day↔night blend. */}
      <div
        className={cn(
          "scene-fade absolute inset-0 bg-[url('/scene-night.jpg')] bg-cover bg-center bg-no-repeat",
          dark ? "opacity-100" : "opacity-0",
        )}
      />

      {/* Soft sun glow — light only, fades out into night */}
      <div className={cn("scene-fade absolute inset-0", dark ? "opacity-0" : "opacity-100")}>
        <div className="landing-sun absolute" />
      </div>

      {/* Aurora curtains — dark only, fades in from day */}
      <div className={cn("scene-fade absolute inset-0", dark ? "opacity-100" : "opacity-0")}>
        <div className="landing-aurora-glow" />
        {CURTAINS.map((c, i) => (
          <div
            key={i}
            className="landing-curtain absolute"
            style={{
              left: `${c.left}%`,
              width: `${c.w}%`,
              height: `${c.h}%`,
              background: `linear-gradient(to bottom, transparent 0%, rgba(${c.c},0.4) 30%, rgba(${c.c},0.32) 55%, transparent 92%)`,
              animationDelay: `${c.delay}s`,
              animationDuration: `${c.dur}s`,
            }}
          />
        ))}
      </div>

      {/* Legibility scrim (kept light so the scene stays vivid) */}
      <div className="absolute inset-0 bg-gradient-to-b from-background/20 via-transparent to-background/35" />

      {/* Drifting petals */}
      <div className="absolute inset-0">
        {PETALS.map((p, i) => (
          <span
            key={i}
            className="landing-petal absolute rounded-full bg-white/80 shadow-[0_0_8px_rgba(255,255,255,0.7)] dark:bg-primary/70"
            style={{
              left: p.left,
              bottom: "14%",
              width: p.size,
              height: p.size,
              // @ts-expect-error custom property consumed by the keyframe
              "--o": p.o,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.dur}s`,
            }}
          />
        ))}
      </div>

      {/* Raw CSS via dangerouslySetInnerHTML so SSR and client output match
          byte-for-byte; an inline style template escapes special chars in the
          server HTML but not on hydration, which would trip a mismatch. */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        /* Day↔night crossfade for the stacked scene layers — long + eased so it
           reads as a gradual dusk/dawn rather than a swap. */
        .scene-fade { transition: opacity 1400ms ease-in-out; will-change: opacity; }

        /* Sun — one soft radial bloom, fully faded edges */
        .landing-sun {
          top: -20%; right: 2%; width: 60%; height: 80%;
          background: radial-gradient(closest-side, rgba(255,244,214,0.55), rgba(255,236,190,0.18) 45%, transparent 70%);
          filter: blur(20px);
          animation: landing-sun-pulse 9s ease-in-out infinite;
        }
        @keyframes landing-sun-pulse { 0%,100% { opacity: .8; } 50% { opacity: 1; } }

        /* Aurora: ambient glow + flowing vertical curtains */
        .landing-aurora-glow {
          position: absolute; top: -10%; left: 10%; width: 80%; height: 55%;
          background: radial-gradient(ellipse 60% 100% at 50% 0%, rgba(74,222,160,0.28), transparent 70%);
          filter: blur(50px); mix-blend-mode: screen;
          animation: landing-aurora-breathe 10s ease-in-out infinite;
        }
        @keyframes landing-aurora-breathe { 0%,100% { opacity: .5; } 50% { opacity: .95; } }

        .landing-curtain {
          top: -6%;
          border-radius: 45% 45% 60% 60% / 70% 70% 40% 40%;
          filter: blur(40px);
          mix-blend-mode: screen;
          transform-origin: top center;
          animation-name: landing-curtain-wave;
          animation-timing-function: cubic-bezier(0.45, 0, 0.55, 1);
          animation-iteration-count: infinite;
          animation-direction: alternate;
          /* Adopt the dim first-keyframe state during animation-delay, so a
             curtain doesn't flash at full base brightness for its delay (up
             to 3s) right after switching into dark mode. */
          animation-fill-mode: backwards;
          opacity: .28;
        }
        /* Gentler, more organic drift — small skew, soft opacity breathing */
        @keyframes landing-curtain-wave {
          0%   { transform: translateX(-5%) skewX(-4deg) scaleY(0.92) scaleX(0.96); opacity: .28; }
          50%  { transform: translateX(4%)  skewX(3deg)  scaleY(1.08) scaleX(1.04); opacity: .62; }
          100% { transform: translateX(-2%) skewX(-2deg) scaleY(1.0)  scaleX(0.98); opacity: .4; }
        }

        /* Petals */
        .landing-petal { opacity: 0; animation-name: landing-drift; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }
        @keyframes landing-drift {
          0%   { transform: translate(0,0) rotate(0deg); opacity: 0; }
          12%  { opacity: var(--o, .5); }
          88%  { opacity: var(--o, .5); }
          100% { transform: translate(60px, -220px) rotate(160deg); opacity: 0; }
        }

        /* Chevron scroll-affordance: a gentle horizontal nudge */
        .landing-nudge { animation: landing-nudge 1.3s ease-in-out infinite; }
        @keyframes landing-nudge { 0%,100% { transform: translateX(0); } 50% { transform: translateX(3px); } }
        .landing-nudge-left { animation: landing-nudge-left 1.3s ease-in-out infinite; }
        @keyframes landing-nudge-left { 0%,100% { transform: translateX(0); } 50% { transform: translateX(-3px); } }

        @media (prefers-reduced-motion: reduce) {
          .scene-fade { transition: none; }
          .landing-sun, .landing-aurora-glow, .landing-curtain, .landing-nudge, .landing-nudge-left { animation: none; }
          .landing-petal { animation: none; opacity: 0; }
        }
          `,
        }}
      />
    </div>
  );
}
