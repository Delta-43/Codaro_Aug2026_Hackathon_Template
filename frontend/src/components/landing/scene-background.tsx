/**
 * Full-page, theme-aware backdrop behind the whole landing page.
 *
 * No photographic scene — a soft themed gradient with a couple of blurred colour
 * blooms, so the liquid-glass plates have something coloured to refract and sit
 * over. A sparse particle field (see `Particles`) gathers along the bottom edge.
 * Fixed, so the glass chapters float over it.
 *
 * It also hosts the `#liquid-glass-distortion` SVG filter + the `.liquid-glass`
 * class the plates use: `backdrop-filter: url(#…)` runs a feDisplacementMap over
 * whatever sits behind each plate, so the background bends/warps through the
 * glass (real refraction/lensing) instead of only blurring. Safari (which
 * ignores url() filters in backdrop-filter) falls back to a plain frosted blur.
 */
import { Particles } from "@/components/landing/particles";

export function SceneBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Soft themed gradient base */}
      <div className="absolute inset-0 bg-gradient-to-br from-sky-100 via-background to-pink-100 dark:from-slate-950 dark:via-background dark:to-slate-900" />

      {/* Blurred colour blooms — give the glass something to bend, add depth */}
      <div className="absolute -top-1/4 -left-16 size-[55%] rounded-full bg-primary/25 blur-[120px] dark:bg-primary/20" />
      <div className="absolute -bottom-1/4 -right-10 size-[55%] rounded-full bg-pink-400/20 blur-[130px] dark:bg-fuchsia-500/15" />
      <div className="absolute top-1/3 left-1/2 size-[40%] -translate-x-1/2 rounded-full bg-sky-300/15 blur-[120px] dark:bg-sky-500/10" />

      {/* Bottom-weighted particle field (hover to repulse) */}
      <Particles />

      {/* Refraction filter for the liquid-glass plates. Zero-size, just a def. */}
      <svg aria-hidden className="absolute size-0" focusable="false">
        <filter id="liquid-glass-distortion" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.012 0.016" numOctaves="2" seed="7" result="noise" />
          <feGaussianBlur in="noise" stdDeviation="2.5" result="softNoise" />
          <feDisplacementMap in="SourceGraphic" in2="softNoise" scale="55" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>

      {/* Raw CSS via dangerouslySetInnerHTML so SSR and client output match
          byte-for-byte; an inline style template escapes special chars in the
          server HTML but not on hydration, which would trip a mismatch. */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        /* Liquid-glass material: refract the backdrop through a displacement
           map (Chromium) + saturate it; Safari ignores url() here and gets a
           plain frosted blur instead. */
        .liquid-glass {
          -webkit-backdrop-filter: blur(11px) saturate(180%);
          backdrop-filter: blur(2px) saturate(180%) url(#liquid-glass-distortion);
        }

        /* Chevron scroll-affordance (used by the nav): a gentle horizontal nudge */
        .landing-nudge { animation: landing-nudge 1.3s ease-in-out infinite; }
        @keyframes landing-nudge { 0%,100% { transform: translateX(0); } 50% { transform: translateX(3px); } }
        .landing-nudge-left { animation: landing-nudge-left 1.3s ease-in-out infinite; }
        @keyframes landing-nudge-left { 0%,100% { transform: translateX(0); } 50% { transform: translateX(-3px); } }

        @media (prefers-reduced-motion: reduce) {
          .landing-nudge, .landing-nudge-left { animation: none; }
        }
          `,
        }}
      />
    </div>
  );
}
