import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Memorial Gathering" — a seated service with no committal and no time
 * limit: family and friends can hold it whenever they're ready, even years
 * later. Drawn as a small semicircle of empty folding chairs fanned out in
 * front of a photo propped on an easel, flanked by two patiently flickering
 * candles and a small open book (the included readings/music) resting on
 * the front chair. Nothing here is urgent — the flames flicker gently, a
 * few warm embers drift upward at their own pace, and a page of the open
 * book turns slowly — the whole scene reads as "waiting, whenever you are,"
 * not grief.
 *
 * All class names / keyframes / ids are prefixed `gathering-` so this file's
 * injected <style> and <defs> ids never collide with the ten sibling
 * per-service animations mounted alongside it on the showcase page.
 */
export const MemorialGatheringAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        <defs>
          <radialGradient id="gathering-frame-glow" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor="#ffcf7d" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ffcf7d" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* ground shadows for grounding */}
        <ellipse cx="32" cy="39.5" rx="11" ry="1.6" fill="#000" opacity="0.28" />
        <ellipse cx="32" cy="59.5" rx="10" ry="1.4" fill="#000" opacity="0.25" />

        {/* patient warm glow behind the easel */}
        <circle className="gathering-glow" cx="32" cy="19" r="17" fill="url(#gathering-frame-glow)" />

        {/* outer back chairs (drawn first, further from viewer) */}
        <ChairIcon x={9} y={46} scale={0.82} />
        <ChairIcon x={55} y={46} scale={0.82} />

        {/* easel + candles sit behind the front chair row */}
        <EaselAndCandles />

        {/* front chairs, including the one with the open book */}
        <ChairIcon x={20} y={55} scale={1} />
        <ChairWithBook x={32} y={58} scale={1.08} />
        <ChairIcon x={44} y={55} scale={1} />

        {/* slow-drifting embers of candlelight — nothing here is in a hurry */}
        <circle className="gathering-ember-1" cx="14" cy="20" r="1" fill="#ffcf7d" />
        <circle className="gathering-ember-2" cx="50" cy="18" r="0.9" fill="#ffcf7d" />
        <circle className="gathering-ember-3" cx="32" cy="6" r="0.8" fill="#ffe2a8" />
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .gathering-glow { animation: gathering-glow 4.4s ease-in-out infinite; transform-origin: 32px 19px; }
        @keyframes gathering-glow {
          0%, 100% { opacity: 0.35; transform: scale(1); }
          50% { opacity: 0.65; transform: scale(1.06); }
        }

        .gathering-flame-a {
          animation: gathering-flicker 2.3s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: bottom center;
        }
        .gathering-flame-b {
          animation: gathering-flicker 2.7s ease-in-out infinite;
          animation-delay: 0.5s;
          transform-box: fill-box;
          transform-origin: bottom center;
        }
        @keyframes gathering-flicker {
          0%, 100% { transform: scaleY(1) scaleX(1) rotate(0deg); }
          25% { transform: scaleY(1.12) scaleX(0.92) rotate(-3deg); }
          50% { transform: scaleY(0.9) scaleX(1.06) rotate(2deg); }
          75% { transform: scaleY(1.06) scaleX(0.95) rotate(-1.5deg); }
        }

        .gathering-page {
          animation: gathering-page 3.8s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: left center;
        }
        @keyframes gathering-page {
          0%, 100% { transform: scaleX(1) rotate(0deg); }
          50% { transform: scaleX(0.82) rotate(-2deg); }
        }

        .gathering-ember-1, .gathering-ember-2, .gathering-ember-3 {
          animation: gathering-drift 4.6s ease-in infinite;
          transform-box: fill-box;
          transform-origin: center;
        }
        .gathering-ember-2 { animation-duration: 5.1s; animation-delay: 1.3s; }
        .gathering-ember-3 { animation-duration: 4.2s; animation-delay: 2.5s; }
        @keyframes gathering-drift {
          0% { transform: translateY(0) scale(1); opacity: 0; }
          15% { opacity: 0.9; }
          80% { opacity: 0.5; }
          100% { transform: translateY(-15px) scale(0.6); opacity: 0; }
        }

        @media (prefers-reduced-motion: reduce) {
          .gathering-glow,
          .gathering-flame-a,
          .gathering-flame-b,
          .gathering-page,
          .gathering-ember-1,
          .gathering-ember-2,
          .gathering-ember-3 {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};

/** Small cartoon folding chair, origin at its ground-contact point. */
function ChairIcon({ x, y, scale }: { x: number; y: number; scale: number }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      {/* back legs, drawn behind */}
      <path d="M -3 -4 L -3.6 0 M 3 -4 L 3.6 0" stroke="#3a2113" strokeWidth="1.1" strokeLinecap="round" />
      {/* seat back */}
      <rect x="-5" y="-14" width="10" height="7" rx="1.6" fill="#8a5636" stroke="#2b1810" strokeWidth="1.4" />
      {/* seat */}
      <rect x="-6" y="-7.5" width="12" height="3.4" rx="1.2" fill="#6b3f24" stroke="#2b1810" strokeWidth="1.4" />
      {/* front legs */}
      <path d="M -4.4 -4.2 L -5 1 M 4.4 -4.2 L 5 1" stroke="#2b1810" strokeWidth="1.6" strokeLinecap="round" />
    </g>
  );
}

/** Same chair, with a small open book resting on the seat. */
function ChairWithBook({ x, y, scale }: { x: number; y: number; scale: number }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <path d="M -3 -4 L -3.6 0 M 3 -4 L 3.6 0" stroke="#3a2113" strokeWidth="1.1" strokeLinecap="round" />
      <rect x="-5" y="-14" width="10" height="7" rx="1.6" fill="#8a5636" stroke="#2b1810" strokeWidth="1.4" />
      <rect x="-6" y="-7.5" width="12" height="3.4" rx="1.2" fill="#6b3f24" stroke="#2b1810" strokeWidth="1.4" />
      <path d="M -4.4 -4.2 L -5 1 M 4.4 -4.2 L 5 1" stroke="#2b1810" strokeWidth="1.6" strokeLinecap="round" />

      {/* open book, spine at center, resting on the seat */}
      <g transform="translate(0, -9.6)">
        <path d="M 0 -1.6 L -4.4 -0.4 L -4.4 1.6 L 0 0.6 Z" fill="#f4e4c1" stroke="#2b1810" strokeWidth="0.9" strokeLinejoin="round" />
        <path
          className="gathering-page"
          d="M 0 -1.6 L 4.4 -0.4 L 4.4 1.6 L 0 0.6 Z"
          fill="#f4e4c1"
          stroke="#2b1810"
          strokeWidth="0.9"
          strokeLinejoin="round"
        />
        <path d="M -3.2 -0.5 L -0.6 -0.1 M -3.2 0.5 L -0.6 0.9" stroke="#b99a6a" strokeWidth="0.4" />
      </g>
    </g>
  );
}

function EaselAndCandles() {
  return (
    <g>
      {/* easel tripod legs */}
      <path
        d="M 32 30 L 22 41 M 32 30 L 42 41 M 26 33 L 38 33"
        fill="none"
        stroke="#5c3620"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* ledge holding the frame */}
      <rect x="21" y="28.5" width="22" height="2.4" rx="1" fill="#5c3620" stroke="#2b1810" strokeWidth="1.2" />

      {/* photo frame */}
      <rect x="23" y="7" width="18" height="23" rx="2" fill="#f4e4c1" stroke="#2b1810" strokeWidth="1.8" />
      <rect x="25.2" y="9.2" width="13.6" height="18.6" rx="1.2" fill="#d98a6c" stroke="#8a4a35" strokeWidth="1" />
      {/* simple portrait silhouette — no specific likeness, just "a photo of someone" */}
      <circle cx="32" cy="16.5" r="3.4" fill="#b5644a" />
      <path d="M 26.5 27 C 26.5 21.5 37.5 21.5 37.5 27 Z" fill="#b5644a" />
      <ellipse cx="29.6" cy="12.4" rx="1.6" ry="2.2" fill="#fff" opacity="0.22" />

      {/* left candle */}
      <g>
        <ellipse cx="15" cy="34.5" rx="3.4" ry="1.3" fill="#5c3620" stroke="#2b1810" strokeWidth="1" />
        <rect x="13.2" y="24" width="3.6" height="11" rx="1" fill="#f4e4c1" stroke="#2b1810" strokeWidth="1.2" />
        <path
          className="gathering-flame-a"
          d="M 15 24.2 C 13.4 21.8 14.4 19.4 15 18.2 C 15.6 19.4 16.6 21.8 15 24.2 Z"
          fill="#ff9d3e"
          stroke="#c9631a"
          strokeWidth="0.6"
        />
        <path d="M 15 23 C 14.3 21.7 14.8 20.5 15 19.9 C 15.2 20.5 15.7 21.7 15 23 Z" fill="#ffe9b0" />
      </g>

      {/* right candle */}
      <g>
        <ellipse cx="49" cy="34.5" rx="3.4" ry="1.3" fill="#5c3620" stroke="#2b1810" strokeWidth="1" />
        <rect x="47.2" y="24" width="3.6" height="11" rx="1" fill="#f4e4c1" stroke="#2b1810" strokeWidth="1.2" />
        <path
          className="gathering-flame-b"
          d="M 49 24.2 C 47.4 21.8 48.4 19.4 49 18.2 C 49.6 19.4 50.6 21.8 49 24.2 Z"
          fill="#ff9d3e"
          stroke="#c9631a"
          strokeWidth="0.6"
        />
        <path d="M 49 23 C 48.3 21.7 48.8 20.5 49 19.9 C 49.2 20.5 49.7 21.7 49 23 Z" fill="#ffe9b0" />
      </g>
    </g>
  );
}
