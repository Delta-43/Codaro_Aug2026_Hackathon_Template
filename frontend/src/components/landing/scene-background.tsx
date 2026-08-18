/**
 * Full-page, theme-aware backdrop behind the whole landing page.
 *
 * No photographic scene anymore — just a soft themed gradient with a couple of
 * blurred colour blooms, so the liquid-glass plates have something coloured to
 * refract and sit over. Plus gently drifting petals. Fixed, so the glass
 * chapters float over it. All motion is pure CSS, disabled under
 * prefers-reduced-motion.
 *
 * It also hosts the `#liquid-glass-distortion` SVG filter + the `.liquid-glass`
 * class the plates use: `backdrop-filter: url(#…)` runs a feDisplacementMap over
 * whatever sits behind each plate, so the background bends/warps through the
 * glass (real refraction/lensing) instead of only blurring. Safari (which
 * ignores url() filters in backdrop-filter) falls back to a plain frosted blur.
 */
const PETALS = Array.from({ length: 30 }, (_, i) => ({
  left: `${(i * 3.27 + 2) % 99}%`,
  size: 4 + ((i * 7) % 8),
  delay: (i * 1.1) % 15,
  dur: 12 + ((i * 5) % 11),
  o: 0.45 + ((i * 3) % 5) / 10,
}));

export function SceneBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Soft themed gradient base */}
      <div className="absolute inset-0 bg-gradient-to-br from-sky-100 via-background to-pink-100 dark:from-slate-950 dark:via-background dark:to-slate-900" />

      {/* Blurred colour blooms — give the glass something to bend, add depth */}
      <div className="absolute -top-1/4 -left-16 size-[55%] rounded-full bg-primary/25 blur-[120px] dark:bg-primary/20" />
      <div className="absolute -bottom-1/4 -right-10 size-[55%] rounded-full bg-pink-400/20 blur-[130px] dark:bg-fuchsia-500/15" />
      <div className="absolute top-1/3 left-1/2 size-[40%] -translate-x-1/2 rounded-full bg-sky-300/15 blur-[120px] dark:bg-sky-500/10" />

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

        /* Petals */
        .landing-petal { opacity: 0; animation-name: landing-drift; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }
        @keyframes landing-drift {
          0%   { transform: translate(0,0) rotate(0deg); opacity: 0; }
          12%  { opacity: var(--o, .5); }
          88%  { opacity: var(--o, .5); }
          100% { transform: translate(60px, -220px) rotate(160deg); opacity: 0; }
        }

        /* Chevron scroll-affordance (used by the nav): a gentle horizontal nudge */
        .landing-nudge { animation: landing-nudge 1.3s ease-in-out infinite; }
        @keyframes landing-nudge { 0%,100% { transform: translateX(0); } 50% { transform: translateX(3px); } }
        .landing-nudge-left { animation: landing-nudge-left 1.3s ease-in-out infinite; }
        @keyframes landing-nudge-left { 0%,100% { transform: translateX(0); } 50% { transform: translateX(-3px); } }

        @media (prefers-reduced-motion: reduce) {
          .landing-nudge, .landing-nudge-left { animation: none; }
          .landing-petal { animation: none; opacity: 0; }
        }
          `,
        }}
      />
    </div>
  );
}
