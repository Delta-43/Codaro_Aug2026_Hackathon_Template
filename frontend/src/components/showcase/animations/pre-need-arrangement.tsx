import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Pre-Need Arrangement" — a consultation where a person calmly writes up
 * their own funeral plans in advance and locks the price in for good. The
 * literal, deliberately anticlimactic payoff of the service ("nothing at
 * all is delivered on the day... except tea and a folder") is drawn
 * straight: a seated figure signing an open folder at a desk, a steaming
 * teacup beside them, and a small hourglass quietly turning in the
 * background to hint the file just sits there, held indefinitely.
 *
 * Cartoon cel-shaded style: flat fills + bold outlines, a small palette,
 * legible on near-black. All classes/keyframes are prefixed `preneed-` so
 * this file's injected <style> can't collide with sibling showcase
 * animations mounted on the same page.
 */
export const PreNeedArrangementAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* background hourglass, faint — "held indefinitely" */}
        <g className="preneed-hourglass" transform="translate(48, 14)">
          <path
            d="M -5 -7 L 5 -7 L 5 -5 L 1 0 L 5 5 L 5 7 L -5 7 L -5 5 L -1 0 L -5 -5 Z"
            fill="#3a3f4a"
            stroke="#6b7280"
            strokeWidth="1"
            strokeLinejoin="round"
          />
          <path d="M -3.5 -5.5 L 3.5 -5.5 L 0 -0.6 Z" fill="#8b93a3" />
          <path className="preneed-sand" d="M -3 6.2 L 3 6.2 L 0 1.6 Z" fill="#8b93a3" />
        </g>

        {/* desk */}
        <rect x="6" y="46" width="46" height="4" rx="1" fill="#5b4636" stroke="#2e2115" strokeWidth="1.5" />
        <rect x="9" y="50" width="4" height="8" fill="#4a3829" stroke="#2e2115" strokeWidth="1.5" />
        <rect x="45" y="50" width="4" height="8" fill="#4a3829" stroke="#2e2115" strokeWidth="1.5" />

        {/* teacup with steam, deliberately small and mundane */}
        <g className="preneed-steam" transform="translate(44, 32)">
          <path
            d="M -1.5 0 Q -3 -3 -1 -5 Q 0.5 -7 -1 -9"
            fill="none"
            stroke="#c9cdd6"
            strokeWidth="1.3"
            strokeLinecap="round"
            opacity="0.8"
          />
          <path
            d="M 2 0 Q 0.5 -3 2.5 -5 Q 4 -7 2.5 -9"
            fill="none"
            stroke="#c9cdd6"
            strokeWidth="1.3"
            strokeLinecap="round"
            opacity="0.6"
          />
        </g>
        <g transform="translate(44, 40)">
          <path d="M -5 0 L 5 0 L 4 5 Q 4 7 0 7 Q -4 7 -4 5 Z" fill="#e8ddce" stroke="#2e2115" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="M 4 1 Q 8 1 8 3.5 Q 8 6 4.5 5.5" fill="none" stroke="#2e2115" strokeWidth="1.3" strokeLinecap="round" />
          <ellipse cx="0" cy="0" rx="5" ry="1.3" fill="#6b4a2f" stroke="#2e2115" strokeWidth="1.3" />
        </g>

        {/* open folder + paper on desk */}
        <g transform="translate(22, 41)">
          <path d="M -12 5 L -9 -3 L 9 -3 L 12 5 Z" fill="#d8c9a3" stroke="#2e2115" strokeWidth="1.5" strokeLinejoin="round" />
          <rect x="-8" y="-2" width="16" height="6.5" rx="0.5" fill="#f5efe0" stroke="#2e2115" strokeWidth="1" />
          <line x1="-6" y1="0.3" x2="4" y2="0.3" stroke="#9a8f78" strokeWidth="0.7" />
          <line x1="-6" y1="1.8" x2="2" y2="1.8" stroke="#9a8f78" strokeWidth="0.7" />
          <path d="M -12 5 L 12 5 L 10.5 8 L -10.5 8 Z" fill="#c2a97e" stroke="#2e2115" strokeWidth="1.5" strokeLinejoin="round" />
        </g>

        {/* seated figure: calm, upright, writing */}
        <g className="preneed-figure" transform="translate(24, 20)">
          {/* chair back */}
          <rect x="-9" y="4" width="4" height="20" rx="1.5" fill="#2b2f38" stroke="#15171c" strokeWidth="1.3" />

          {/* torso */}
          <path d="M -6 10 Q -7 22 -5 28 L 9 28 Q 11 22 9 10 Q 2 5 -6 10 Z" fill="#3f5d54" stroke="#15171c" strokeWidth="1.5" strokeLinejoin="round" />

          {/* head */}
          <g className="preneed-nod">
            <circle cx="2" cy="2" r="7" fill="#e4c9a8" stroke="#15171c" strokeWidth="1.5" />
            {/* simple hair */}
            <path d="M -5 -1 Q -6 -8 2 -8 Q 9 -8 8 -1 Q 4 -4 2 -3 Q -1 -4 -5 -1 Z" fill="#2b2f38" stroke="#15171c" strokeWidth="1.3" strokeLinejoin="round" />
            {/* calm closed-ish eyes */}
            <path d="M -1.5 2 Q -0.3 3 1 2" fill="none" stroke="#15171c" strokeWidth="1" strokeLinecap="round" />
            <path d="M 3 2 Q 4.3 3 5.6 2" fill="none" stroke="#15171c" strokeWidth="1" strokeLinecap="round" />
            {/* faint content smile */}
            <path d="M 0.5 6 Q 2.5 7.3 4.5 6" fill="none" stroke="#15171c" strokeWidth="1" strokeLinecap="round" />
          </g>

          {/* far arm, resting */}
          <path d="M 8 13 Q 13 16 12 21" fill="none" stroke="#3f5d54" strokeWidth="5" strokeLinecap="round" />

          {/* near arm + hand, writing, animated at the wrist */}
          <g className="preneed-write" transform="translate(-4, 20)">
            <path d="M 0 -7 Q -6 -3 -4 3" fill="none" stroke="#3f5d54" strokeWidth="5" strokeLinecap="round" />
            <circle cx="-4" cy="3" r="2.6" fill="#e4c9a8" stroke="#15171c" strokeWidth="1.2" />
            {/* pen */}
            <path d="M -4 3 L -9 6" stroke="#c9a63e" strokeWidth="1.6" strokeLinecap="round" />
            <path d="M -9 6 L -10.5 7" stroke="#15171c" strokeWidth="1.6" strokeLinecap="round" />
          </g>
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .preneed-figure { animation: preneed-breathe 4s ease-in-out infinite; transform-origin: 24px 44px; }
        @keyframes preneed-breathe {
          0%, 100% { transform: translate(24px, 20px) scale(1); }
          50% { transform: translate(24px, 19.4px) scale(1.01); }
        }

        .preneed-nod { animation: preneed-nod 4s ease-in-out infinite; transform-origin: 2px 2px; }
        @keyframes preneed-nod {
          0%, 40%, 100% { transform: rotate(0deg); }
          20% { transform: rotate(-3deg); }
        }

        .preneed-write { animation: preneed-write 2.2s ease-in-out infinite; transform-origin: 0px -7px; }
        @keyframes preneed-write {
          0%, 100% { transform: translate(-4px, 20px) rotate(0deg); }
          25% { transform: translate(-4px, 20px) rotate(-8deg); }
          50% { transform: translate(-4px, 20px) rotate(3deg); }
          75% { transform: translate(-4px, 20px) rotate(-5deg); }
        }

        .preneed-steam { animation: preneed-steam 3s ease-in-out infinite; }
        @keyframes preneed-steam {
          0% { opacity: 0; transform: translate(44px, 32px) translateY(2px); }
          20% { opacity: 0.9; }
          80% { opacity: 0.4; }
          100% { opacity: 0; transform: translate(44px, 32px) translateY(-4px); }
        }

        .preneed-hourglass { animation: preneed-hourglass 5s ease-in-out infinite; transform-origin: 48px 14px; }
        @keyframes preneed-hourglass {
          0%, 45% { transform: translate(48px, 14px) rotate(0deg); }
          50%, 95% { transform: translate(48px, 14px) rotate(180deg); }
          100% { transform: translate(48px, 14px) rotate(180deg); }
        }

        .preneed-sand { animation: preneed-sand 5s linear infinite; transform-origin: 48px 14px; }
        @keyframes preneed-sand {
          0% { transform: scaleY(1); }
          45% { transform: scaleY(0.2); }
          50% { transform: scaleY(1); }
          95% { transform: scaleY(0.2); }
          100% { transform: scaleY(1); }
        }

        @media (prefers-reduced-motion: reduce) {
          .preneed-figure,
          .preneed-nod,
          .preneed-write,
          .preneed-steam,
          .preneed-hourglass,
          .preneed-sand {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
