import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Orbital Committal" — vitrification + launch to a 620km stable low-Earth
 * orbit, four centuries up there before re-entry. This is a literal launch,
 * not a metaphor, so the joke is drawn dead straight: a coffin, strapped
 * down with cargo webbing like any other payload, riding a stubby cartoon
 * booster off the pad — mission-patch deadpan, not spooky. The orbit arc and
 * a scattering of stars in the backdrop are what sell "this really goes to
 * space" at a glance.
 */
export const OrbitalCommittalAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* Background: distant stars */}
        <path className="orbital-star orbital-star-1" d="M7,6.8 L7.7,8.4 L9.3,9 L7.7,9.6 L7,11.2 L6.3,9.6 L4.7,9 L6.3,8.4 Z" fill="#eaf7ff" />
        <path className="orbital-star orbital-star-2" d="M9,45 L9.6,46.4 L11,47 L9.6,47.6 L9,49 L8.4,47.6 L7,47 L8.4,46.4 Z" fill="#eaf7ff" />
        <path className="orbital-star orbital-star-3" d="M56,50 L56.6,51.4 L58,52 L56.6,52.6 L56,54 L55.4,52.6 L54,52 L55.4,51.4 Z" fill="#eaf7ff" />
        <path className="orbital-star orbital-star-4" d="M58,32 L58.6,33.4 L60,34 L58.6,34.6 L58,36 L57.4,34.6 L56,34 L57.4,33.4 Z" fill="#eaf7ff" />

        {/* Orbit ring — the "stable low Earth orbit" detail */}
        <g className="orbital-orbit-spin">
          <ellipse
            cx="45"
            cy="17"
            rx="15"
            ry="5.5"
            transform="rotate(-18 45 17)"
            fill="none"
            stroke="#8fd9e8"
            strokeWidth="1.1"
            strokeDasharray="3 3"
            opacity="0.75"
          />
        </g>

        {/* Rocket + payload, statically placed then wobbled by CSS */}
        <g transform="translate(32,30)">
          <g className="orbital-launch">
            {/* exhaust flame (behind nozzle so it reads as coming from underneath) */}
            <g className="orbital-flame">
              <path d="M-3.4,19 C-6.5,25 -4.5,31.5 0,34.5 C4.5,31.5 6.5,25 3.4,19 Z" fill="#ff8a2b" stroke="#4a2200" strokeWidth="1.2" strokeLinejoin="round" />
              <path d="M-1.8,19.5 C-3.4,23.5 -2.2,28 0,30 C2.2,28 3.4,23.5 1.8,19.5 Z" fill="#ffd94a" />
            </g>

            {/* engine nozzle */}
            <path d="M-2.6,15.5 L2.6,15.5 L2,20 L-2,20 Z" fill="#2b2b2b" stroke="#140f0b" strokeWidth="1.2" strokeLinejoin="round" />

            {/* fins */}
            <path d="M-3,9.5 L-10.5,18.5 L-3,16.5 Z" fill="#a3271d" stroke="#140f0b" strokeWidth="1.2" strokeLinejoin="round" />
            <path d="M3,9.5 L10.5,18.5 L3,16.5 Z" fill="#a3271d" stroke="#140f0b" strokeWidth="1.2" strokeLinejoin="round" />

            {/* coffin fuselage */}
            <polygon
              points="-3,-10 -6.2,-2 -6.2,8 -3,16 3,16 6.2,8 6.2,-2 3,-10"
              fill="#8a5a30"
              stroke="#140f0b"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
            {/* wood-grain highlight */}
            <path d="M-4.4,-6 L-4.4,12" fill="none" stroke="#a9713f" strokeWidth="1" strokeLinecap="round" opacity="0.8" />

            {/* cargo straps */}
            <rect x="-7.2" y="-2" width="14.4" height="2" rx="0.6" fill="#1c1c1c" stroke="#140f0b" strokeWidth="0.6" />
            <rect x="-7.2" y="8.4" width="14.4" height="2" rx="0.6" fill="#1c1c1c" stroke="#140f0b" strokeWidth="0.6" />
            <rect x="-1.6" y="-2.4" width="3.2" height="2.8" rx="0.5" fill="#c9a53b" stroke="#140f0b" strokeWidth="0.6" />
            <rect x="-1.6" y="7.8" width="3.2" height="2.8" rx="0.5" fill="#c9a53b" stroke="#140f0b" strokeWidth="0.6" />

            {/* brass memorial plaque */}
            <rect x="-2.6" y="2" width="5.2" height="3.2" rx="0.7" fill="#d4af37" stroke="#140f0b" strokeWidth="0.8" />

            {/* nose cone */}
            <path
              d="M-4,-10 C-4,-16 -2.2,-19.4 0,-20.6 C2.2,-19.4 4,-16 4,-10 Z"
              fill="#c0392b"
              stroke="#140f0b"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
            {/* porthole */}
            <circle cx="0" cy="-13" r="1.7" fill="#bfeaff" stroke="#140f0b" strokeWidth="0.9" />
          </g>

          {/* smoke puffs trailing below the flame */}
          <circle className="orbital-smoke orbital-smoke-1" cx="0" cy="22" r="2.2" fill="#b8b8b8" />
          <circle className="orbital-smoke orbital-smoke-2" cx="-2" cy="23" r="2.2" fill="#b8b8b8" />
          <circle className="orbital-smoke orbital-smoke-3" cx="3" cy="24" r="2.2" fill="#b8b8b8" />
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .orbital-launch {
          transform-origin: 0px 6px;
          animation: orbital-launch-bounce 2.6s ease-in-out infinite;
        }
        @keyframes orbital-launch-bounce {
          0%   { transform: translate(0px, 0px) rotate(0deg); }
          30%  { transform: translate(-0.8px, -3.2px) rotate(-2.5deg); }
          60%  { transform: translate(0.8px, -1.6px) rotate(2deg); }
          100% { transform: translate(0px, 0px) rotate(0deg); }
        }

        .orbital-flame {
          transform-origin: 0px 19px;
          animation: orbital-flame-flicker 0.5s ease-in-out infinite alternate;
        }
        @keyframes orbital-flame-flicker {
          0%   { transform: scale(1, 1); }
          50%  { transform: scale(0.88, 1.18); }
          100% { transform: scale(1.08, 0.92); }
        }

        .orbital-smoke { opacity: 0; }
        .orbital-smoke-1 { animation: orbital-smoke-rise 2.4s ease-out infinite; animation-delay: 0s; }
        .orbital-smoke-2 { animation: orbital-smoke-rise 2.4s ease-out infinite; animation-delay: 0.8s; }
        .orbital-smoke-3 { animation: orbital-smoke-rise 2.4s ease-out infinite; animation-delay: 1.6s; }
        @keyframes orbital-smoke-rise {
          0%   { transform: translate(0px, 0px) scale(0.5); opacity: 0.65; }
          70%  { opacity: 0.35; }
          100% { transform: translate(0px, 11px) scale(1.6); opacity: 0; }
        }

        .orbital-orbit-spin {
          transform-origin: 45px 17px;
          animation: orbital-orbit-turn 9s linear infinite;
        }
        @keyframes orbital-orbit-turn {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }

        .orbital-star { animation: orbital-twinkle 2.2s ease-in-out infinite; }
        .orbital-star-1 { animation-delay: 0s; }
        .orbital-star-2 { animation-delay: 0.5s; }
        .orbital-star-3 { animation-delay: 1s; }
        .orbital-star-4 { animation-delay: 1.5s; }
        @keyframes orbital-twinkle {
          0%, 100% { opacity: 0.35; }
          50%      { opacity: 1; }
        }

        @media (prefers-reduced-motion: reduce) {
          .orbital-launch,
          .orbital-flame,
          .orbital-smoke-1,
          .orbital-smoke-2,
          .orbital-smoke-3,
          .orbital-orbit-spin,
          .orbital-star {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
