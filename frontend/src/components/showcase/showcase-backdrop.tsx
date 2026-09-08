// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Static-in-JS, bespoke backdrop for `/showcase`: a near-black base dressed
 * as a moonlit cemetery — a crescent moon with a soft glow, a scattered
 * star field that twinkles on staggered timers, a low tombstone/cross
 * skyline (plus a wrought-iron fence and a bare tree) silhouetted along the
 * bottom edge, and a handful of translucent "bedsheet ghost" blobs drifting
 * among the graves. Pure CSS/SVG, no canvas, no rAF loop — every motion is a
 * plain `@keyframes` animation, injected the same `dangerouslySetInnerHTML`
 * way `scene-background.tsx` injects its CSS (SSR and client output must
 * match byte-for-byte, which an inline style template can't guarantee).
 *
 * Deliberately theme-agnostic: no `useTheme()`/`next-themes` read. `/showcase`
 * is forced dark via a `.dark` wrapper class regardless of the site-wide
 * toggle, so this backdrop must always render the same dark scene, never
 * conditioned on global theme state.
 *
 * This is ambient background for a page whose foreground is eleven other
 * bespoke per-service animations — every custom class/keyframe name below is
 * prefixed `bg-` so nothing collides with sibling styles injected elsewhere
 * on the same page.
 */

const STARS = [
  { top: "5%", left: "8%", size: 2, delay: 0.2, duration: 3.4 },
  { top: "10%", left: "22%", size: 3, delay: 1.6, duration: 4.1 },
  { top: "4%", left: "38%", size: 2, delay: 0.9, duration: 3.8 },
  { top: "16%", left: "48%", size: 2, delay: 2.4, duration: 3.2 },
  { top: "8%", left: "58%", size: 3, delay: 0.4, duration: 4.6 },
  { top: "20%", left: "6%", size: 2, delay: 3.1, duration: 3.6 },
  { top: "26%", left: "30%", size: 2, delay: 1.1, duration: 4 },
  { top: "14%", left: "68%", size: 2, delay: 2.7, duration: 3.3 },
  { top: "22%", left: "78%", size: 3, delay: 0.7, duration: 4.4 },
  { top: "7%", left: "88%", size: 2, delay: 1.9, duration: 3.7 },
  { top: "30%", left: "92%", size: 2, delay: 3.4, duration: 3.1 },
  { top: "34%", left: "16%", size: 2, delay: 2.1, duration: 4.2 },
  { top: "18%", left: "82%", size: 2, delay: 0.1, duration: 3.9 },
  { top: "28%", left: "62%", size: 3, delay: 1.4, duration: 4.5 },
  { top: "12%", left: "12%", size: 2, delay: 2.9, duration: 3.5 },
];

const GHOSTS = [
  { left: "16%", bottom: "12%", width: 34, opacity: 0.22, duration: 8.5, delay: 0.3, variant: 1 },
  { left: "41%", bottom: "9%", width: 40, opacity: 0.16, duration: 10.5, delay: 2.4, variant: 2 },
  { left: "64%", bottom: "15%", width: 30, opacity: 0.26, duration: 7.8, delay: 1.2, variant: 1 },
  { left: "83%", bottom: "10%", width: 36, opacity: 0.19, duration: 9.6, delay: 3.1, variant: 2 },
];

export function ShowcaseBackdrop() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#07060a]"
    >
      {/* Crescent moon: a pale disc with a soft blurred glow behind it, with
          a same-color-as-base circle offset on top to bite a crescent out
          of the disc — three plain divs, same technique as the fog blooms
          this file used to be built from. */}
      <div className="bg-moon-wrap absolute right-[14%] top-[7%] h-[90px] w-[90px]">
        <div className="bg-moon-glow absolute -inset-[45%] rounded-full" />
        <div className="bg-moon-disc absolute inset-0 rounded-full" />
        <div className="bg-moon-bite absolute -left-[20%] -top-[8%] h-full w-full rounded-full bg-[#07060a]" />
      </div>

      {/* Star field — a dozen-plus twinkling points, each on its own
          staggered delay/duration so they never blink in unison. */}
      {STARS.map((s, i) => (
        <span
          key={i}
          className="bg-star absolute rounded-full bg-white"
          style={{
            top: s.top,
            left: s.left,
            width: s.size,
            height: s.size,
            animationDelay: `${s.delay}s`,
            animationDuration: `${s.duration}s`,
          }}
        />
      ))}

      {/* Cemetery skyline along the bottom edge: tombstones, crosses, a
          wrought-iron fence and a bare tree, one flat silhouette color a
          shade lighter than the base so it reads as atmosphere, not
          foreground. preserveAspectRatio="none" lets it stretch full-bleed
          to any viewport width while keeping a fixed height. */}
      <svg
        className="absolute bottom-0 left-0 h-[22vh] min-h-[170px] w-full"
        viewBox="0 0 1440 260"
        preserveAspectRatio="none"
        focusable="false"
      >
        <g className="bg-cemetery-fill">
          {/* wrought-iron fence, left */}
          <rect x="14" y="150" width="6" height="110" />
          <circle cx="17" cy="146" r="5" />
          <rect x="54" y="150" width="6" height="110" />
          <circle cx="57" cy="146" r="5" />
          <rect x="94" y="150" width="6" height="110" />
          <circle cx="97" cy="146" r="5" />
          <rect x="134" y="150" width="6" height="110" />
          <circle cx="137" cy="146" r="5" />
          <rect x="174" y="150" width="6" height="110" />
          <circle cx="177" cy="146" r="5" />
          <rect x="10" y="188" width="174" height="6" />
          <rect x="10" y="218" width="174" height="6" />

          {/* tombstones + crosses, varied heights/widths for a natural skyline */}
          <path d="M270 260 V190 a20 20 0 0 1 40 0 V260 Z" />
          <rect x="345" y="165" width="10" height="95" />
          <rect x="327" y="188" width="46" height="10" />
          <path d="M410 260 V215 a24 24 0 0 1 48 0 V260 Z" />
          <path d="M500 260 L500 195 L520 168 L540 195 L540 260 Z" />
          <path d="M590 260 V230 a15 15 0 0 1 30 0 V260 Z" />
          <g transform="rotate(-9 660 260)">
            <rect x="656" y="170" width="8" height="90" />
            <rect x="640" y="193" width="40" height="8" />
          </g>
          <path d="M730 260 V160 a28 28 0 0 1 56 0 V260 Z" />
          <rect x="840" y="205" width="46" height="55" rx="6" />
          <rect x="925" y="175" width="9" height="85" />
          <rect x="908" y="198" width="43" height="9" />
          <path d="M1000 260 V205 a22 22 0 0 1 44 0 V260 Z" />
          <path d="M1080 260 L1080 222 L1098 198 L1116 222 L1116 260 Z" />
        </g>

        {/* bare tree, right */}
        <g className="bg-cemetery-stroke" fill="none" strokeWidth="6" strokeLinecap="round">
          <path d="M1330 260 V180" />
          <path d="M1330 210 L1300 160" />
          <path d="M1330 195 L1355 145" />
          <path d="M1330 225 L1365 190" />
          <path d="M1330 225 L1295 205" />
          <path d="M1330 180 L1310 130" />
          <path d="M1330 180 L1350 135" />
        </g>
      </svg>

      {/* A few lingering "bedsheet ghost" blobs — dome body + a scalloped
          hem made from a row of overlapping circles, no face, kept plain
          and iconic. Each drifts (gentle bob + sway) on its own timer. */}
      {GHOSTS.map((g, i) => (
        <div
          key={i}
          className={`bg-ghost absolute bg-ghost-drift-${g.variant}`}
          style={{
            left: g.left,
            bottom: g.bottom,
            width: g.width,
            height: g.width * 1.3,
            opacity: g.opacity,
            animationDuration: `${g.duration}s`,
            animationDelay: `${g.delay}s`,
          }}
        >
          <span className="bg-ghost-body block" />
          <span className="bg-ghost-hem flex">
            <i />
            <i />
            <i />
            <i />
          </span>
        </div>
      ))}

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .bg-moon-glow {
          background: radial-gradient(circle, rgba(245,244,251,0.35) 0%, rgba(245,244,251,0) 70%);
          filter: blur(6px);
          animation: bg-moon-glow-pulse 12s ease-in-out infinite;
        }
        .bg-moon-disc {
          background: #f5f4fb;
          box-shadow: 0 0 26px rgba(245,244,251,0.55), 0 0 60px rgba(245,244,251,0.2);
        }
        @keyframes bg-moon-glow-pulse {
          0%, 100% { opacity: 0.75; }
          50% { opacity: 1; }
        }

        .bg-cemetery-fill { fill: #16121e; }
        .bg-cemetery-stroke { stroke: #16121e; }

        .bg-star {
          opacity: 0.55;
          animation-name: bg-twinkle;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
        }
        @keyframes bg-twinkle {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 1; }
        }

        .bg-ghost-body {
          width: 100%;
          height: 68%;
          background: #f5f4fb;
          border-radius: 50% 50% 10% 10% / 60% 60% 8% 8%;
        }
        .bg-ghost-hem {
          width: 100%;
          height: 34%;
          margin-top: -14%;
          justify-content: space-between;
        }
        .bg-ghost-hem i {
          width: 32%;
          aspect-ratio: 1 / 1;
          background: #f5f4fb;
          border-radius: 50%;
          display: block;
          font-style: normal;
        }
        .bg-ghost-drift-1 {
          animation-name: bg-ghost-drift-a;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
        }
        .bg-ghost-drift-2 {
          animation-name: bg-ghost-drift-b;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
        }
        @keyframes bg-ghost-drift-a {
          0%, 100% { transform: translate(0, 0); }
          25% { transform: translate(4px, -10px); }
          50% { transform: translate(-3px, -16px); }
          75% { transform: translate(-6px, -6px); }
        }
        @keyframes bg-ghost-drift-b {
          0%, 100% { transform: translate(0, 0); }
          25% { transform: translate(-5px, -8px); }
          50% { transform: translate(4px, -14px); }
          75% { transform: translate(6px, -5px); }
        }

        @media (prefers-reduced-motion: reduce) {
          .bg-star, .bg-ghost-drift-1, .bg-ghost-drift-2, .bg-moon-glow {
            animation: none;
          }
        }
          `,
        }}
      />
    </div>
  );
}
