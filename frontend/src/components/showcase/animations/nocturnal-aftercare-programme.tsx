import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Nocturnal Aftercare Programme" — an after-hours arrangement for
 * light-sensitive families: chapel opened after sunset, west windows
 * shuttered, mirrors in the foyer covered "as a matter of course." Drawn
 * dead straight, no wink to camera: a small gothic chapel silhouette under
 * a crescent moon, one shutter that occasionally rattles loose in the
 * night air, and — the literal, funniest detail in the brief — a
 * free-standing mirror on the porch, fully veiled under a dust sheet, that
 * gives one small unexplained shiver partway through the loop.
 *
 * Cartoon cel-shaded style: flat fills + bold dark outlines, a tight night
 * palette (navy/charcoal chapel, cream moon + veil, wood stand, silver
 * trim). Legible on near-black. Every class/keyframe is prefixed
 * `nocturnal-` so this file's injected <style> can't collide with sibling
 * showcase animations mounted on the same page.
 */
export const NocturnalAftercareAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* night-sky panel */}
        <rect x="1" y="1" width="62" height="62" rx="5" fill="#0a0e1c" stroke="#1c2340" strokeWidth="1.5" />
        <rect x="2.5" y="54" width="59" height="8" rx="2" fill="#10142a" />

        {/* stars, twinkling out of sync */}
        <g className="nocturnal-stars">
          <circle cx="10" cy="9" r="0.9" fill="#9aa3c2" />
          <circle cx="21" cy="6" r="0.7" fill="#9aa3c2" />
          <circle cx="7" cy="21" r="0.6" fill="#9aa3c2" />
          <circle cx="58" cy="24" r="0.8" fill="#9aa3c2" />
          <circle cx="44" cy="7" r="0.6" fill="#9aa3c2" />
        </g>

        {/* crescent moon with a soft pulsing glow */}
        <g transform="translate(50, 12)">
          <circle className="nocturnal-glow" r="10" fill="#f2e6c4" opacity="0.15" />
          <circle r="6" fill="#f2e6c4" />
          <circle cx="3" cy="-2" r="5.4" fill="#0a0e1c" />
        </g>

        {/* steeple cross */}
        <line x1="32" y1="-3" x2="32" y2="2" stroke="#9aa3c2" strokeWidth="1.3" strokeLinecap="round" />
        <line x1="30" y1="0" x2="34" y2="0" stroke="#9aa3c2" strokeWidth="1.3" strokeLinecap="round" />

        {/* steeple */}
        <path d="M28 10 L32 2 L36 10 Z" fill="#141830" stroke="#05060d" strokeWidth="1.5" strokeLinejoin="round" />
        <rect x="29" y="10" width="6" height="10" fill="#141830" stroke="#05060d" strokeWidth="1.5" />

        {/* main gable roof */}
        <path d="M14 38 L32 20 L50 38 Z" fill="#141830" stroke="#05060d" strokeWidth="1.5" strokeLinejoin="round" />

        {/* round gable window, shuttered */}
        <g transform="translate(32, 30)">
          <circle r="4" fill="#141830" stroke="#05060d" strokeWidth="1.3" />
          <line x1="-3" y1="-1.5" x2="3" y2="-1.5" stroke="#9aa3c2" strokeWidth="0.8" />
          <line x1="-3.5" y1="0.5" x2="3.5" y2="0.5" stroke="#9aa3c2" strokeWidth="0.8" />
          <line x1="-3" y1="2.5" x2="3" y2="2.5" stroke="#9aa3c2" strokeWidth="0.8" />
        </g>

        {/* chapel walls */}
        <rect x="16" y="38" width="32" height="18" fill="#262c47" stroke="#05060d" strokeWidth="1.5" />

        {/* left window, fully shuttered, still */}
        <g transform="translate(21, 47)">
          <rect x="-4" y="-5" width="8" height="10" rx="1" fill="#141830" stroke="#05060d" strokeWidth="1.3" />
          <line x1="0" y1="-5" x2="0" y2="5" stroke="#05060d" strokeWidth="1" />
          <line x1="-2.5" y1="-3" x2="2.5" y2="-3" stroke="#9aa3c2" strokeWidth="0.7" />
          <line x1="-2.5" y1="0" x2="2.5" y2="0" stroke="#9aa3c2" strokeWidth="0.7" />
          <line x1="-2.5" y1="3" x2="2.5" y2="3" stroke="#9aa3c2" strokeWidth="0.7" />
        </g>

        {/* right (west) window, shuttered — one flap rattles loose now and then */}
        <g transform="translate(43, 47)">
          <rect x="-4" y="-5" width="8" height="10" rx="1" fill="#141830" stroke="#05060d" strokeWidth="1.3" />
          <line x1="0" y1="-5" x2="0" y2="5" stroke="#05060d" strokeWidth="1" />
          <line x1="-2.5" y1="-3" x2="-0.3" y2="-3" stroke="#9aa3c2" strokeWidth="0.7" />
          <line x1="-2.5" y1="0" x2="-0.3" y2="0" stroke="#9aa3c2" strokeWidth="0.7" />
          <line x1="-2.5" y1="3" x2="-0.3" y2="3" stroke="#9aa3c2" strokeWidth="0.7" />
          <g className="nocturnal-shutter" transform="translate(0.3, 0)">
            <rect x="0" y="-5" width="3.7" height="10" fill="#141830" stroke="#05060d" strokeWidth="1" />
            <line x1="0.7" y1="-3" x2="3.2" y2="-3" stroke="#9aa3c2" strokeWidth="0.6" />
            <line x1="0.7" y1="0" x2="3.2" y2="0" stroke="#9aa3c2" strokeWidth="0.6" />
            <line x1="0.7" y1="3" x2="3.2" y2="3" stroke="#9aa3c2" strokeWidth="0.6" />
          </g>
        </g>

        {/* closed double doors */}
        <g transform="translate(32, 0)">
          <path d="M-5 56 L-5 48 Q-5 44 0 44 Q5 44 5 48 L5 56 Z" fill="#141830" stroke="#05060d" strokeWidth="1.5" />
          <line x1="0" y1="44" x2="0" y2="56" stroke="#9aa3c2" strokeWidth="0.8" />
          <circle cx="-2" cy="51" r="0.6" fill="#9aa3c2" />
          <circle cx="2" cy="51" r="0.6" fill="#9aa3c2" />
        </g>

        {/* the mirror on the porch — completely veiled, as a matter of course */}
        <g className="nocturnal-mirror" transform="translate(10, 50)">
          <path d="M-4 8 L-2 -4 M4 8 L2 -4" stroke="#5b4636" strokeWidth="2" strokeLinecap="round" fill="none" />
          <line x1="-3" y1="2" x2="3" y2="2" stroke="#5b4636" strokeWidth="1.6" strokeLinecap="round" />
          <ellipse cx="0" cy="-6" rx="5.4" ry="7.4" fill="#5b4636" stroke="#05060d" strokeWidth="1.4" />
          <g className="nocturnal-veil" transform="translate(0, -6)">
            <path
              d="M-5.6 -7.6 Q0 -10 5.6 -7.6 L5.6 3 Q3 6.5 0 5 Q-3 6.5 -5.6 3 Z"
              fill="#ece2cc"
              stroke="#05060d"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
            <path d="M-3 -6 Q-3 0 -2.4 4.5" fill="none" stroke="#c9bfa0" strokeWidth="0.7" strokeLinecap="round" opacity="0.7" />
            <path d="M2.6 -6 Q2.6 0 2 4.6" fill="none" stroke="#c9bfa0" strokeWidth="0.7" strokeLinecap="round" opacity="0.7" />
          </g>
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .nocturnal-glow { animation: nocturnal-glow-pulse 4s ease-in-out infinite; }
        @keyframes nocturnal-glow-pulse {
          0%, 100% { opacity: 0.12; transform: scale(1); }
          50% { opacity: 0.28; transform: scale(1.12); }
        }

        .nocturnal-stars circle { animation: nocturnal-twinkle 3s ease-in-out infinite; }
        .nocturnal-stars circle:nth-child(1) { animation-delay: 0s; }
        .nocturnal-stars circle:nth-child(2) { animation-delay: 0.5s; }
        .nocturnal-stars circle:nth-child(3) { animation-delay: 1s; }
        .nocturnal-stars circle:nth-child(4) { animation-delay: 1.6s; }
        .nocturnal-stars circle:nth-child(5) { animation-delay: 2.1s; }
        @keyframes nocturnal-twinkle {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 1; }
        }

        .nocturnal-shutter { animation: nocturnal-creak 5s ease-in-out infinite; }
        @keyframes nocturnal-creak {
          0%, 85%, 100% { transform: translate(0.3px, 0px) rotate(0deg); }
          90% { transform: translate(0.3px, 0px) rotate(-14deg); }
          95% { transform: translate(0.3px, 0px) rotate(-6deg); }
        }

        .nocturnal-veil { animation: nocturnal-veil-sway 4s ease-in-out infinite; }
        @keyframes nocturnal-veil-sway {
          0%, 100% { transform: translate(0px, -6px) rotate(0deg) scaleX(1); }
          50% { transform: translate(0px, -6px) rotate(1.5deg) scaleX(1.02); }
        }

        .nocturnal-mirror { animation: nocturnal-shiver 6s ease-in-out infinite; }
        @keyframes nocturnal-shiver {
          0%, 68% { transform: translate(10px, 50px) rotate(0deg); }
          71% { transform: translate(10.3px, 49.7px) rotate(-2.5deg); }
          74% { transform: translate(9.7px, 50.3px) rotate(2.5deg); }
          77% { transform: translate(10.2px, 49.8px) rotate(-1.2deg); }
          80%, 100% { transform: translate(10px, 50px) rotate(0deg); }
        }

        @media (prefers-reduced-motion: reduce) {
          .nocturnal-glow,
          .nocturnal-stars circle,
          .nocturnal-shutter,
          .nocturnal-veil,
          .nocturnal-mirror {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
