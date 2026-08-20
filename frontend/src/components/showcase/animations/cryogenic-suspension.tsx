import { useId } from "react";
import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * Cryogenic Suspension — a frosty cryo-capsule, drawn deadpan-technical
 * (server-room equipment, not sci-fi horror): a steel pod with a rimed
 * glass viewing window, icicles hanging off the lid, a slow occasional
 * drip, faint rising vapor, and a two-light status panel that blinks like
 * any other piece of monitored cold-storage hardware. Frost patches behind
 * the glass slowly breathe in and out to sell the -196 C detail without
 * ever fully melting.
 */
export const CryogenicSuspensionAnimation: ServiceAnimationComponent = ({ className, title }) => {
  const clipId = useId().replace(/[:]/g, "");
  const glassClip = `cryo-glass-clip-${clipId}`;

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
          <clipPath id={glassClip}>
            <rect x="22" y="24" width="20" height="20" rx="5" />
          </clipPath>
        </defs>

        <g className="cryo-bob">
          {/* rising vapor, behind everything */}
          <path
            className="cryo-vapor-1"
            d="M28 10 C 26 6, 30 5, 28 1"
            fill="none"
            stroke="#f2fbfd"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            className="cryo-vapor-2"
            d="M40 9 C 42 5, 38 4, 40 0"
            fill="none"
            stroke="#f2fbfd"
            strokeWidth="1.4"
            strokeLinecap="round"
          />

          {/* feet */}
          <rect x="20" y="56" width="6" height="5" rx="1.4" fill="#173b4d" stroke="#0d1420" strokeWidth="1.8" />
          <rect x="38" y="56" width="6" height="5" rx="1.4" fill="#173b4d" stroke="#0d1420" strokeWidth="1.8" />

          {/* lid, peeking above the body as a rim */}
          <rect x="16" y="10" width="32" height="10" rx="4.5" fill="#173b4d" stroke="#0d1420" strokeWidth="2.2" />

          {/* main body */}
          <rect x="16" y="16" width="32" height="38" rx="9" fill="#2f6483" stroke="#0d1420" strokeWidth="2.2" />

          {/* icicles hanging off the lid */}
          <path d="M18,20 L22,20 L20,27 Z" fill="#f2fbfd" stroke="#0d1420" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M24,20 L28,20 L26,30 Z" fill="#f2fbfd" stroke="#0d1420" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M30,20 L34,20 L32,26 Z" fill="#f2fbfd" stroke="#0d1420" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M36,20 L40,20 L38,31 Z" fill="#f2fbfd" stroke="#0d1420" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M42,20 L46,20 L44,27 Z" fill="#f2fbfd" stroke="#0d1420" strokeWidth="1.3" strokeLinejoin="round" />

          {/* glass window */}
          <rect x="22" y="24" width="20" height="20" rx="5" fill="#173b4d" stroke="#0d1420" strokeWidth="2" />
          <g clipPath={`url(#${glassClip})`}>
            <rect x="27" y="28" width="10" height="14" rx="4.5" fill="#2f6483" opacity="0.55" />
            <ellipse className="cryo-frost-a" cx="26" cy="29" rx="6" ry="5" fill="#f2fbfd" />
            <ellipse className="cryo-frost-b" cx="39" cy="40" rx="6.5" ry="5.5" fill="#f2fbfd" />
            <ellipse className="cryo-frost-c" cx="30" cy="41" rx="5" ry="4" fill="#f2fbfd" />
            <rect x="22" y="24" width="20" height="20" fill="#f2fbfd" opacity="0.14" />
          </g>
          <rect x="22" y="24" width="20" height="20" rx="5" fill="none" stroke="#0d1420" strokeWidth="2" />

          {/* falling drip, in front of the glass */}
          <circle className="cryo-droplet" cx="38" cy="32" r="1.15" fill="#f2fbfd" stroke="#0d1420" strokeWidth="0.6" />

          {/* control panel */}
          <rect x="24" y="48" width="16" height="7" rx="2" fill="#173b4d" stroke="#0d1420" strokeWidth="1.6" />
          <line x1="36.4" y1="49.3" x2="36.4" y2="53.7" stroke="#2f6483" strokeWidth="0.9" />
          <line x1="38" y1="49.3" x2="38" y2="53.7" stroke="#2f6483" strokeWidth="0.9" />
          <circle className="cryo-light-a" cx="28" cy="51.5" r="1.5" fill="#f5b942" stroke="#0d1420" strokeWidth="0.6" />
          <circle className="cryo-light-b" cx="32.5" cy="51.5" r="1.5" fill="#f2fbfd" stroke="#0d1420" strokeWidth="0.6" />
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .cryo-bob { animation: cryo-bob 4s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
        @keyframes cryo-bob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-1.5px); }
        }

        .cryo-frost-a, .cryo-frost-b, .cryo-frost-c {
          transform-box: fill-box;
          transform-origin: center;
        }
        .cryo-frost-a { animation: cryo-frost-a 6s ease-in-out infinite; }
        .cryo-frost-b { animation: cryo-frost-b 7s ease-in-out infinite 0.6s; }
        .cryo-frost-c { animation: cryo-frost-c 5.5s ease-in-out infinite 1.2s; }
        @keyframes cryo-frost-a {
          0%, 100% { opacity: 0.18; transform: scale(0.85); }
          50% { opacity: 0.75; transform: scale(1.05); }
        }
        @keyframes cryo-frost-b {
          0%, 100% { opacity: 0.22; transform: scale(0.88); }
          50% { opacity: 0.7; transform: scale(1.04); }
        }
        @keyframes cryo-frost-c {
          0%, 100% { opacity: 0.15; transform: scale(0.82); }
          50% { opacity: 0.65; transform: scale(1.06); }
        }

        .cryo-light-a { animation: cryo-light-a 2.4s ease-in-out infinite; }
        .cryo-light-b { animation: cryo-light-b 1.7s ease-in-out infinite 0.4s; }
        @keyframes cryo-light-a {
          0%, 45% { opacity: 1; }
          50%, 95% { opacity: 0.15; }
          100% { opacity: 1; }
        }
        @keyframes cryo-light-b {
          0%, 40% { opacity: 1; }
          46%, 90% { opacity: 0.2; }
          100% { opacity: 1; }
        }

        .cryo-droplet {
          animation: cryo-droplet 3s ease-in infinite;
          transform-box: fill-box;
          transform-origin: center;
        }
        @keyframes cryo-droplet {
          0% { transform: translateY(0); opacity: 1; }
          70% { transform: translateY(9px); opacity: 1; }
          85% { opacity: 0.4; }
          100% { transform: translateY(11px); opacity: 0; }
        }

        .cryo-vapor-1, .cryo-vapor-2 {
          transform-box: fill-box;
          transform-origin: bottom center;
        }
        .cryo-vapor-1 { animation: cryo-vapor 4.5s ease-out infinite; }
        .cryo-vapor-2 { animation: cryo-vapor 5.2s ease-out infinite 1s; }
        @keyframes cryo-vapor {
          0% { opacity: 0; transform: translateY(0) scale(0.9); }
          25% { opacity: 0.55; }
          100% { opacity: 0; transform: translateY(-9px) scale(1.1); }
        }

        @media (prefers-reduced-motion: reduce) {
          .cryo-bob,
          .cryo-frost-a,
          .cryo-frost-b,
          .cryo-frost-c,
          .cryo-light-a,
          .cryo-light-b,
          .cryo-droplet,
          .cryo-vapor-1,
          .cryo-vapor-2 {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
