/**
 * Full-page, theme-aware backdrop behind the whole landing page.
 *
 * Deliberately plain and colourless: a solid black/white base (white in light
 * mode, black in dark) with a few slow *monochrome* flecks drifting across it —
 * no pink, no gradient. The flecks exist only to give the liquid-glass plates a
 * subtle neutral texture to frost/blur (the effect only reads when there's
 * something behind the glass). Spread over the full height so every plate, not
 * just the footer, gets the same blurred backdrop. Fixed, so the glass chapters
 * float over it. All motion is pure CSS, disabled under prefers-reduced-motion.
 *
 * It also hosts the `#liquid-glass-distortion` SVG filter + the `.liquid-glass`
 * class the plates use — the `.liquid-glass` blur/saturate is what frosts the
 * backdrop behind each plate.
 */
const FLECKS = Array.from({ length: 30 }, (_, i) => ({
  left: `${(i * 3.27 + 2) % 99}%`,
  top: `${(i * 6.13 + 5) % 94}%`,
  size: 4 + ((i * 7) % 8),
  delay: (i * 1.1) % 15,
  dur: 12 + ((i * 5) % 11),
  o: 0.35 + ((i * 3) % 5) / 12,
}));

export function SceneBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Plain black/white base — white in light mode, black in dark */}
      <div className="absolute inset-0 bg-white dark:bg-black" />

      {/* Slow monochrome flecks — a neutral texture for the glass to blur */}
      <div className="absolute inset-0">
        {FLECKS.map((p, i) => (
          <span
            key={i}
            className="landing-fleck absolute rounded-full bg-black/10 dark:bg-white/40"
            style={{
              left: p.left,
              top: p.top,
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
        /* Liquid-glass material: frost + saturate the backdrop behind a plate.
           (The url() displacement is a Chromium-only nicety; every browser at
           least gets the blur/saturate, which is the look that matters here.) */
        .liquid-glass {
          -webkit-backdrop-filter: blur(11px) saturate(180%);
          backdrop-filter: blur(2px) saturate(180%) url(#liquid-glass-distortion);
        }

        /* Drifting monochrome flecks */
        .landing-fleck { opacity: 0; animation-name: landing-drift; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }
        @keyframes landing-drift {
          0%   { transform: translate(0,0); opacity: 0; }
          12%  { opacity: var(--o, .4); }
          88%  { opacity: var(--o, .4); }
          100% { transform: translate(50px, -180px); opacity: 0; }
        }

        /* Chevron scroll-affordance (used by the nav): a gentle horizontal nudge */
        .landing-nudge { animation: landing-nudge 1.3s ease-in-out infinite; }
        @keyframes landing-nudge { 0%,100% { transform: translateX(0); } 50% { transform: translateX(3px); } }
        .landing-nudge-left { animation: landing-nudge-left 1.3s ease-in-out infinite; }
        @keyframes landing-nudge-left { 0%,100% { transform: translateX(0); } 50% { transform: translateX(-3px); } }

        @media (prefers-reduced-motion: reduce) {
          .landing-nudge, .landing-nudge-left { animation: none; }
          .landing-fleck { animation: none; opacity: 0; }
        }
          `,
        }}
      />
    </div>
  );
}
