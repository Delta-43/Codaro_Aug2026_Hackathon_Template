import { cn } from "@/lib/utils";
import type { ServiceAnimationProps } from "@/components/showcase/animations/service-animation-contract";

/**
 * Traditional Funeral Service — the description's single most vivid detail
 * is the director walking in front of the hearse to the corner of the
 * street ("the last thing most families remember of the day"), so that is
 * the whole scene: a top-hatted director a few dignified steps ahead of a
 * boxy cartoon hearse, both processing toward a lamppost marking the
 * corner. Wheels spin, legs swing, the whole cortège shuffles forward a
 * hair and settles back — a slow, respectful loop, not a joyride.
 */
export function TraditionalFuneralServiceAnimation({ className, title }: ServiceAnimationProps) {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* street */}
        <line x1="2" y1="52" x2="62" y2="52" stroke="#6b5b78" strokeWidth="1" strokeLinecap="round" opacity="0.55" />

        {/* corner lamppost — the fixed landmark the cortège is walking toward */}
        <g>
          <circle className="cortege-lamp-glow-outer" cx="57" cy="26.5" r="5.4" fill="#f4c968" opacity="0.18" />
          <circle className="cortege-lamp-glow-inner" cx="57" cy="26.5" r="3" fill="#f6d685" opacity="0.4" />
          <rect x="56.3" y="30" width="1.4" height="22" fill="#3f3549" stroke="#1c1030" strokeWidth="0.6" />
          <rect x="54.4" y="27.6" width="5.2" height="2.2" rx="0.6" fill="#3f3549" stroke="#1c1030" strokeWidth="0.6" />
          <circle cx="57" cy="26.5" r="1.6" fill="#fff3cf" stroke="#c98f2e" strokeWidth="0.5" />
        </g>

        {/* the cortège: hearse + director, drifting a hair forward-and-back each cycle */}
        <g className="cortege-convoy">
          {/* ground shadows (kept out of the vertical bob so they read as flat contact points) */}
          <ellipse cx="17.5" cy="49.5" rx="13" ry="1.6" fill="#000" opacity="0.35" />
          <ellipse cx="40" cy="50.3" rx="5.2" ry="1" fill="#000" opacity="0.35" />

          {/* hearse */}
          <g className="cortege-hearse">
            <path
              d="M29,46 L29,40 L26,38 L25,32 L11,32 L10,35 L6,37 L6,46 Z"
              fill="#3a2a4a"
              stroke="#1c1030"
              strokeWidth="1.1"
              strokeLinejoin="round"
            />
            {/* casket-window band */}
            <polygon points="12,33 24,33 23,36.5 11.6,36.2" fill="#b9c4bb" stroke="#1c1030" strokeWidth="0.6" />
            <line x1="17.6" y1="33" x2="17.3" y2="36.35" stroke="#1c1030" strokeWidth="0.5" opacity="0.6" />
            {/* small wreath emblem on the rear door */}
            <circle cx="8.4" cy="41" r="1.4" fill="none" stroke="#b98ca6" strokeWidth="0.8" />
            <circle cx="8.4" cy="39.7" r="0.5" fill="#b98ca6" />
            <circle cx="9.6" cy="41.4" r="0.5" fill="#b98ca6" />
            <circle cx="7.2" cy="41.4" r="0.5" fill="#b98ca6" />
            {/* chrome sill */}
            <line x1="6.4" y1="44.5" x2="28.6" y2="44.5" stroke="#cfd3d6" strokeWidth="0.8" opacity="0.7" />
            {/* headlamp */}
            <ellipse className="cortege-headlight" cx="29.4" cy="42" rx="1" ry="1.3" fill="#ffe9a8" stroke="#c98f2e" strokeWidth="0.5" />

            <g className="cortege-wheel">
              <circle cx="13" cy="46.3" r="3.3" fill="#22182c" stroke="#0e0a13" strokeWidth="1" />
              <circle cx="13" cy="46.3" r="1.3" fill="#cfd3d6" stroke="#0e0a13" strokeWidth="0.5" />
              <line x1="13" y1="44.3" x2="13" y2="48.3" stroke="#0e0a13" strokeWidth="0.5" />
              <line x1="11" y1="46.3" x2="15" y2="46.3" stroke="#0e0a13" strokeWidth="0.5" />
            </g>
            <g className="cortege-wheel">
              <circle cx="24" cy="46.3" r="3.3" fill="#22182c" stroke="#0e0a13" strokeWidth="1" />
              <circle cx="24" cy="46.3" r="1.3" fill="#cfd3d6" stroke="#0e0a13" strokeWidth="0.5" />
              <line x1="24" y1="44.3" x2="24" y2="48.3" stroke="#0e0a13" strokeWidth="0.5" />
              <line x1="22" y1="46.3" x2="26" y2="46.3" stroke="#0e0a13" strokeWidth="0.5" />
            </g>
          </g>

          {/* director, a few dignified steps ahead */}
          <g className="cortege-director">
            <g className="cortege-leg-back">
              <rect x="37.6" y="42" width="1.8" height="7" rx="0.7" fill="#201829" stroke="#0e0a13" strokeWidth="0.8" />
              <ellipse cx="38.5" cy="49.3" rx="1.6" ry="0.8" fill="#0e0a13" />
            </g>
            <g className="cortege-leg-front">
              <rect x="40.6" y="42" width="1.8" height="7" rx="0.7" fill="#201829" stroke="#0e0a13" strokeWidth="0.8" />
              <ellipse cx="41.5" cy="49.3" rx="1.6" ry="0.8" fill="#0e0a13" />
            </g>

            <path d="M37,32.6 L43,32.6 L45,43 L35,43 Z" fill="#5c3d78" stroke="#1c1030" strokeWidth="1.1" strokeLinejoin="round" />
            <line x1="40" y1="33.1" x2="40" y2="42.6" stroke="#1c1030" strokeWidth="0.5" opacity="0.5" />

            <g className="cortege-arm-cane">
              <rect x="43" y="33" width="1.6" height="6" rx="0.7" fill="#5c3d78" stroke="#1c1030" strokeWidth="0.9" transform="rotate(12 43.8 33)" />
              <line x1="44.7" y1="39" x2="45.3" y2="50" stroke="#c9a15b" strokeWidth="0.9" strokeLinecap="round" />
              <circle cx="44.7" cy="39" r="0.8" fill="#c9a15b" stroke="#1c1030" strokeWidth="0.4" />
            </g>

            <rect x="38.7" y="32.1" width="2.6" height="1.2" fill="#f0e6d2" stroke="#1c1030" strokeWidth="0.5" />
            <circle cx="40" cy="30.6" r="1.9" fill="#e8c9a8" stroke="#1c1030" strokeWidth="0.7" />
            <rect x="37.5" y="25" width="5" height="3.4" rx="0.4" fill="#201829" stroke="#0e0a13" strokeWidth="1" />
            <ellipse cx="40" cy="28.4" rx="4.2" ry="1" fill="#201829" stroke="#0e0a13" strokeWidth="1" />
            <rect x="37.5" y="27.3" width="5" height="0.8" fill="#7a5a9c" />
          </g>
        </g>
      </svg>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .cortege-convoy { animation: cortege-drift 2.4s ease-in-out infinite; }
        @keyframes cortege-drift { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(1.2px); } }

        .cortege-director {
          animation: cortege-bob 2.4s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: 50% 100%;
        }
        .cortege-hearse {
          animation: cortege-bob 2.4s ease-in-out infinite;
          animation-delay: -0.2s;
          transform-box: fill-box;
          transform-origin: 50% 100%;
        }
        @keyframes cortege-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-0.8px); } }

        .cortege-leg-back {
          animation: cortege-leg-swing-a 1.2s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: 50% 0%;
        }
        .cortege-leg-front {
          animation: cortege-leg-swing-b 1.2s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: 50% 0%;
        }
        @keyframes cortege-leg-swing-a { 0%, 100% { transform: rotate(14deg); } 50% { transform: rotate(-14deg); } }
        @keyframes cortege-leg-swing-b { 0%, 100% { transform: rotate(-14deg); } 50% { transform: rotate(14deg); } }

        .cortege-arm-cane {
          animation: cortege-cane-tap 2.4s ease-in-out infinite;
          transform-box: fill-box;
          transform-origin: 20% 0%;
        }
        @keyframes cortege-cane-tap {
          0%, 20% { transform: rotate(0deg); }
          30% { transform: rotate(-10deg); }
          50%, 100% { transform: rotate(0deg); }
        }

        .cortege-wheel {
          animation: cortege-wheel-spin 1.4s linear infinite;
          transform-box: fill-box;
          transform-origin: 50% 50%;
        }
        @keyframes cortege-wheel-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .cortege-headlight,
        .cortege-lamp-glow-outer,
        .cortege-lamp-glow-inner {
          animation: cortege-glow-pulse 2.8s ease-in-out infinite;
        }
        .cortege-lamp-glow-inner { animation-delay: -1.4s; }
        @keyframes cortege-glow-pulse { 0%, 100% { opacity: 0.45; } 50% { opacity: 0.95; } }

        @media (prefers-reduced-motion: reduce) {
          .cortege-convoy,
          .cortege-director,
          .cortege-hearse,
          .cortege-leg-back,
          .cortege-leg-front,
          .cortege-arm-cane,
          .cortege-wheel,
          .cortege-headlight,
          .cortege-lamp-glow-outer,
          .cortege-lamp-glow-inner {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
}
