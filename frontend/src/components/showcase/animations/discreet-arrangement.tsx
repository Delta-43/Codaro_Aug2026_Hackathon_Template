import { cn } from "@/lib/utils";
import type { ServiceAnimationProps } from "./service-animation-contract";

// Flat cartoon palette — kept to five colors so the whole scene reads as one
// cel-shaded object, not a patchwork. Bone-white outline keeps every shape
// legible against the showcase card's near-black background.
const OUTLINE = "#f2ede4"; // bone-white — every stroke
const SHADE = "#333a58"; // dusky indigo — coat, hat, van body (all "unmarked")
const SHADE_DARK = "#20233a"; // deeper shade — hat crown, neck gap, wheels, window
const PAPER = "#eaddc0"; // sealed envelope
const WAX = "#8c2735"; // wax seal — the one warm accent
const GLOW = "#f2d585"; // moonlight / stars / the van's one lit eye

/**
 * Discreet Arrangement — a shadowy, faceless figure in a wide-brimmed hat and
 * long coat, tiptoeing a sealed envelope out to an unmarked van under a
 * crescent moon. Plays "collection is unmarked and out of hours" as a
 * comic-noir gag (the hat brim hides the face entirely; the van's single
 * headlight gives the viewer a conspiratorial wink) rather than anything
 * actually sinister.
 *
 * Motion: the figure has a continuous tiptoe bob with two independently
 * stepping feet, a periodic paranoid glance back (the hat swivels, not the
 * whole body), and a swinging envelope with an occasional wax-seal glint. The
 * van idles low on its springs and winks its headlight on a slow, comic
 * timer. Moon and stars twinkle quietly in the background. All motion loops
 * cleanly — nothing translates off and resets.
 */
export function DiscreetArrangementAnimation({ className, title }: ServiceAnimationProps) {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* night sky */}
        <g className="discreet-moon-glow">
          <path
            d="M13,4 C8,4 5,7.5 5,11.5 C5,15.5 8,19 13,19 C10,17 8,14.5 8,11.5 C8,8.5 10,6 13,4 Z"
            fill={GLOW}
            opacity={0.9}
          />
        </g>
        <circle className="discreet-star-1" cx="44" cy="9" r="0.8" fill={GLOW} />
        <circle className="discreet-star-2" cx="52" cy="14" r="0.7" fill={GLOW} />
        <circle className="discreet-star-3" cx="57" cy="7" r="0.6" fill={GLOW} />

        {/* ground */}
        <line x1="3" y1="55" x2="62" y2="55" stroke={OUTLINE} strokeWidth={1} strokeDasharray="1.5 3" strokeLinecap="round" opacity={0.3} />
        <ellipse cx="19" cy="54" rx="13" ry="2" fill="#000000" opacity={0.35} />
        <ellipse cx="51" cy="50" rx="13" ry="2" fill="#000000" opacity={0.35} />

        {/* the unmarked van */}
        <g className="discreet-van-idle" style={{ transformOrigin: "51px 49px" }}>
          <path
            d="M39,48 L39,40 Q39,36 42,36 L45,36 L49,31 L59,31 Q62,31 62,34 L62,46 Q62,48 60,48 Z"
            fill={SHADE}
            stroke={OUTLINE}
            strokeWidth={1.6}
            strokeLinejoin="round"
          />
          {/* tinted cab window — no driver visible, naturally */}
          <path d="M46,35.5 L49,32 L53,32 L53,35.5 Z" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1} strokeLinejoin="round" />
          {/* seam between cab and windowless cargo box */}
          <line x1="49" y1="31.5" x2="49" y2="48" stroke={OUTLINE} strokeWidth={1} opacity={0.4} />
          {/* wheels */}
          <circle cx="44" cy="48" r="4" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1.3} />
          <circle cx="44" cy="48" r="1.2" fill={OUTLINE} />
          <circle cx="57" cy="48" r="4" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1.3} />
          <circle cx="57" cy="48" r="1.2" fill={OUTLINE} />
          {/* the one lit eye — winks on a slow comic timer */}
          <g className="discreet-headlight-wink" style={{ transformOrigin: "40px 44px" }}>
            <circle cx="40" cy="44" r="2.1" fill={GLOW} stroke={OUTLINE} strokeWidth={1} />
          </g>
        </g>

        {/* the figure — tiptoeing the envelope out */}
        <g className="discreet-figure-bob" style={{ transformOrigin: "19px 55px" }}>
          {/* hat + the shadow where a face would be — swivels for the "glance back" */}
          <g className="discreet-glance" style={{ transformOrigin: "19px 21px" }}>
            <path d="M13,20 Q13,10 19,10 Q25,10 25,20 Z" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1.5} strokeLinejoin="round" />
            <ellipse cx="19" cy="20.5" rx="11" ry="2.6" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1.5} />
            <path d="M13.5,21 L24.5,21 L22.5,27 L15.5,27 Z" fill={SHADE_DARK} />
          </g>

          {/* long coat */}
          <path
            d="M13.5,26 C8,29 5,38 4,49 Q4,51 6,51 L32,51 Q34,51 33,49 C32,38 29,29 24.5,26 Z"
            fill={SHADE}
            stroke={OUTLINE}
            strokeWidth={1.7}
            strokeLinejoin="round"
          />

          {/* sleeve reaching for the envelope */}
          <path d="M24,32 L33,36 L28,42 L21,38 Z" fill={SHADE} stroke={OUTLINE} strokeWidth={1.4} strokeLinejoin="round" />

          {/* sealed envelope, held out, sways as it's carried */}
          <g className="discreet-envelope-sway" style={{ transformOrigin: "31px 33px" }}>
            <g transform="translate(31 37)">
              <rect x="-6" y="-4" width="12" height="9" rx="1" fill={PAPER} stroke={OUTLINE} strokeWidth={1.3} />
              <path d="M-6,-4 L0,1.5 L6,-4" fill="none" stroke={OUTLINE} strokeWidth={1.1} strokeLinejoin="round" />
              <circle cx="0" cy="1.6" r="2.3" fill={WAX} stroke={OUTLINE} strokeWidth={1} />
              <ellipse className="discreet-seal-glint" cx="-0.8" cy="0.7" rx="0.9" ry="0.5" fill={PAPER} opacity={0.15} />
            </g>
          </g>

          {/* tiptoe feet, stepping out of phase */}
          <g className="discreet-step-left" style={{ transformOrigin: "10.5px 51px" }}>
            <path d="M8,51 L13,51 L9,54 Z" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1} strokeLinejoin="round" />
          </g>
          <g className="discreet-step-right" style={{ transformOrigin: "25.5px 51px" }}>
            <path d="M23,51 L28,51 L26,54 Z" fill={SHADE_DARK} stroke={OUTLINE} strokeWidth={1} strokeLinejoin="round" />
          </g>
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        /* Whole figure — a continuous, quiet tiptoe bob */
        .discreet-figure-bob { animation: discreet-figure-bob 2.6s ease-in-out infinite; }
        @keyframes discreet-figure-bob {
          0%, 100% { transform: translateY(0) rotate(-1deg); }
          50% { transform: translateY(-1.4px) rotate(1deg); }
        }

        /* Hat swivels for a paranoid over-the-shoulder glance; mostly still */
        .discreet-glance { animation: discreet-glance 4.8s ease-in-out infinite; }
        @keyframes discreet-glance {
          0%, 55%, 100% { transform: rotate(0deg); }
          65%, 75% { transform: rotate(-14deg); }
          85% { transform: rotate(0deg); }
        }

        /* Envelope swings gently as it's carried */
        .discreet-envelope-sway { animation: discreet-envelope-sway 2.6s ease-in-out infinite; }
        @keyframes discreet-envelope-sway {
          0%, 100% { transform: rotate(-4deg); }
          50% { transform: rotate(4deg); }
        }

        /* Faint glint crossing the wax seal */
        .discreet-seal-glint { animation: discreet-seal-glint 3s ease-in-out infinite; }
        @keyframes discreet-seal-glint {
          0%, 75%, 100% { opacity: 0.1; }
          88% { opacity: 0.75; }
        }

        /* Tiptoe feet, out of phase with each other */
        .discreet-step-left, .discreet-step-right { animation: discreet-step 2.6s ease-in-out infinite; }
        .discreet-step-right { animation-delay: -1.3s; }
        @keyframes discreet-step {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-1.6px); }
        }

        /* Van idles low on its springs */
        .discreet-van-idle { animation: discreet-van-idle 3.4s ease-in-out infinite; }
        @keyframes discreet-van-idle {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-1px); }
        }

        /* The van's one lit eye — a slow, comic wink */
        .discreet-headlight-wink { animation: discreet-headlight-wink 4.2s ease-in-out infinite; }
        @keyframes discreet-headlight-wink {
          0%, 60%, 100% { transform: scaleY(1); }
          65% { transform: scaleY(0.15); }
          70% { transform: scaleY(1); }
        }

        /* Moon breathes very slowly */
        .discreet-moon-glow { animation: discreet-moon-glow 5s ease-in-out infinite; }
        @keyframes discreet-moon-glow {
          0%, 100% { opacity: 0.85; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.05); }
        }

        /* Stars twinkle, staggered */
        .discreet-star-1, .discreet-star-2, .discreet-star-3 { animation: discreet-star-twinkle 2.4s ease-in-out infinite; }
        .discreet-star-2 { animation-delay: -0.8s; }
        .discreet-star-3 { animation-delay: -1.6s; }
        @keyframes discreet-star-twinkle {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 1; }
        }

        @media (prefers-reduced-motion: reduce) {
          .discreet-figure-bob,
          .discreet-glance,
          .discreet-envelope-sway,
          .discreet-seal-glint,
          .discreet-step-left,
          .discreet-step-right,
          .discreet-van-idle,
          .discreet-headlight-wink,
          .discreet-moon-glow,
          .discreet-star-1,
          .discreet-star-2,
          .discreet-star-3 {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
}
