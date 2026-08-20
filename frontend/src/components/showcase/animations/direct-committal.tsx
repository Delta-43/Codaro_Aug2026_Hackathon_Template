import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Direct Committal" — no mourners, no ceremony: collection, documentation
 * and committal only, with the family telephoned once it's complete. Drawn
 * as a plain, unadorned coffin resting on a low plinth (no flowers, no
 * chairs, no crowd) beside a small old-fashioned candlestick telephone on
 * its own plinth. The only motion in the whole scene is three gold ring
 * lines pulsing off the phone's mouthpiece — that's the entire story this
 * animation tells: it's done, and now someone is being called. Everything
 * else is deliberately still, to match the starkness of the arrangement
 * itself.
 *
 * All class names / keyframes are prefixed `direct-` so this file's injected
 * <style> tag never collides with the ten sibling per-service animations
 * mounted alongside it on the showcase page.
 */
export const DirectCommittalAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* ground line — quiet, no set-dressing */}
        <line x1="2" y1="52" x2="62" y2="52" stroke="#3a3230" strokeWidth="1" opacity="0.4" />

        {/* coffin plinth */}
        <rect x="7" y="46" width="35" height="3" rx="0.6" fill="#33241a" stroke="#140b06" strokeWidth="1" />

        {/* coffin body — plain hexagonal box, tapered at head and foot */}
        <polygon
          points="12,32 34,32 40,36 40,44 34,48 12,48 6,44 6,36"
          fill="#5c3a24"
          stroke="#140b06"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {/* lid panel — subtle two-tone for a cel-shaded read, not decoration */}
        <polygon
          points="14,34 32,34 36,36.5 36,38 14,38"
          fill="#7a4f30"
          stroke="#140b06"
          strokeWidth="1"
          strokeLinejoin="round"
        />
        {/* lid seam */}
        <line x1="23" y1="32" x2="23" y2="48" stroke="#140b06" strokeWidth="1" opacity="0.5" />

        {/* phone plinth */}
        <rect x="46" y="45.4" width="15" height="2.6" rx="0.5" fill="#33241a" stroke="#140b06" strokeWidth="1" />

        {/* candlestick telephone */}
        <g>
          <ellipse cx="53.2" cy="43.4" rx="4.6" ry="1.5" fill="#232323" stroke="#140b06" strokeWidth="1" />
          <rect x="51.8" y="31.5" width="2.8" height="12" rx="1.2" fill="#2b2b2b" stroke="#140b06" strokeWidth="1" />
          <circle cx="53.2" cy="29.4" r="3.2" fill="#2b2b2b" stroke="#140b06" strokeWidth="1.2" />
          <circle cx="53.2" cy="29.4" r="1.1" fill="#d4af37" opacity="0.85" />
          {/* hook arm + resting receiver */}
          <path d="M56 34 Q60.5 32.4 63 35.2" fill="none" stroke="#140b06" strokeWidth="1.2" strokeLinecap="round" />
          <ellipse
            cx="61.5"
            cy="36.6"
            rx="4"
            ry="1.9"
            fill="#2b2b2b"
            stroke="#140b06"
            strokeWidth="1"
            transform="rotate(-22 61.5 36.6)"
          />

          {/* ring lines — the one piece of motion */}
          <path
            className="direct-wave direct-wave-1"
            d="M56.5,26 Q59.5,23.2 57,20"
            fill="none"
            stroke="#d4af37"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            className="direct-wave direct-wave-2"
            d="M58.5,27.6 Q63.5,22.6 59.5,17.6"
            fill="none"
            stroke="#d4af37"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            className="direct-wave direct-wave-3"
            d="M60.5,29.4 Q67.5,22.4 62,15.4"
            fill="none"
            stroke="#d4af37"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </g>
      </svg>

      {/* Raw CSS via dangerouslySetInnerHTML so SSR and client output match
          byte-for-byte (no styled-jsx / CSS module). */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .direct-wave {
          opacity: 0;
          transform-box: fill-box;
          transform-origin: 0% 50%;
          animation: direct-ring-pulse 2.6s ease-in-out infinite;
        }
        .direct-wave-1 { animation-delay: 0s; }
        .direct-wave-2 { animation-delay: 0.22s; }
        .direct-wave-3 { animation-delay: 0.44s; }

        @keyframes direct-ring-pulse {
          0%   { opacity: 0; transform: scale(0.85); }
          18%  { opacity: 1; transform: scale(1); }
          55%  { opacity: 1; transform: scale(1); }
          80%  { opacity: 0; transform: scale(1.08); }
          100% { opacity: 0; transform: scale(1.08); }
        }

        @media (prefers-reduced-motion: reduce) {
          .direct-wave-1, .direct-wave-2, .direct-wave-3 { animation: none; opacity: 0.9; }
        }
          `,
        }}
      />
    </>
  );
};
