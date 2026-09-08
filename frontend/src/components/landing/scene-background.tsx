// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Full-page, theme-aware backdrop behind the whole landing page.
 *
 * Deliberately plain and colourless (as installed in issue 81): a solid
 * black/white base — white in light mode, black in dark — with only the sparse
 * *monochrome* particle field (see `Particles`) gathering along the bottom edge.
 * No gradient, no colour blooms: the liquid-glass plates read their cleanest,
 * footer-perfect frost when the backdrop they refract is neutral. (Colour blooms
 * tint and muddy the same glass — that regression is what this restores.) Fixed,
 * so the glass chapters float over it.
 *
 * It also hosts the `#liquid-glass-distortion` SVG filter + the `.liquid-glass`
 * class the plates use — the `.liquid-glass` blur/saturate is what frosts the
 * backdrop behind each plate.
 */
import { Particles } from "@/components/landing/particles";

export function SceneBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Plain black/white base — white in light mode, black in dark */}
      <div className="absolute inset-0 bg-white dark:bg-black" />

      {/* Bottom-weighted monochrome particle field (hover to repulse) — the only
          texture the glass frosts, kept neutral so the frost stays clean. */}
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
        /* Liquid-glass material: frost + saturate the backdrop behind a plate.
           (The url() displacement is a Chromium-only nicety; every browser at
           least gets the blur/saturate, which is the look that matters here.) */
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
