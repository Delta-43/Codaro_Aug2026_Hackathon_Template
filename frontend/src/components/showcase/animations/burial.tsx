// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Burial" — interment at the cemetery: the grave is prepared, six bearers
 * lower the coffin, and the office sorts out depth/permissions/deed before
 * any of that happens. The literal payoff is drawn straight: a coffin on
 * ropes easing down into an open grave, a mound of freshly turned earth with
 * a spade stuck upright in it, and a plain headstone standing by. Dignified,
 * not spooky — no ghosts, no skulls, just the classic interment scene with a
 * little cartoon bounce in the lowering motion.
 *
 * Cartoon cel-shaded style: flat fills + bold outlines, a small palette
 * (green ground / brown earth+wood / grey stone / tan rope), legible on
 * near-black. All classes/keyframes are prefixed `burial-` so this file's
 * injected <style> can't collide with sibling showcase animations mounted
 * on the same page.
 */
export const BurialAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* ground */}
        <rect x="0" y="51" width="64" height="13" fill="#3d6b45" />
        <line x1="0" y1="51" x2="64" y2="51" stroke="#2c4d31" strokeWidth="1.2" />

        {/* open grave */}
        <path
          d="M16,51 L39,51 L34,60 L21,60 Z"
          fill="#3a2a1d"
          stroke="#140e09"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M19.5,53.5 L35.5,53.5 L31.5,58 L23.5,58 Z" fill="#140e09" />

        {/* plain headstone */}
        <path
          d="M4,51 L4,36 Q4,30 8.5,30 Q13,30 13,36 L13,51 Z"
          fill="#9a9ea6"
          stroke="#33363b"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <line x1="6" y1="38" x2="11" y2="38" stroke="#6d7178" strokeWidth="1" strokeLinecap="round" />
        <line x1="6" y1="41.5" x2="11" y2="41.5" stroke="#6d7178" strokeWidth="1" strokeLinecap="round" />

        {/* spade blade — buried end, drawn under the mound so it reads as stuck in */}
        <path
          d="M46.5,45 L51,45 L49.5,52 L48,52 Z"
          fill="#9aa0aa"
          stroke="#2a2d33"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />

        {/* mound of freshly turned earth beside the grave */}
        <path
          d="M40,52 Q41,45 46,44 Q48,40 51,43 Q54,39 57,44 Q59,47 58,52 Z"
          fill="#5b4327"
          stroke="#241a10"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <ellipse cx="46" cy="46" rx="3" ry="1.8" fill="#4a3620" opacity="0.55" />
        <ellipse cx="53" cy="44.5" rx="2.6" ry="1.6" fill="#4a3620" opacity="0.55" />

        {/* spade handle + grip — the part that sticks up out of the mound, animated */}
        <g className="burial-spade">
          <line x1="48" y1="42" x2="43" y2="20" stroke="#8a5a2e" strokeWidth="2.2" strokeLinecap="round" />
          <ellipse
            cx="42.5"
            cy="18.5"
            rx="3.2"
            ry="4.2"
            fill="none"
            stroke="#8a5a2e"
            strokeWidth="2"
            transform="rotate(-12 42.5 18.5)"
          />
        </g>

        {/* dust puffs kicked up as the coffin settles */}
        <circle className="burial-dust burial-dust1" cx="24" cy="50" r="2" fill="#8a8478" opacity="0" />
        <circle className="burial-dust burial-dust2" cx="31" cy="49" r="1.6" fill="#8a8478" opacity="0" />

        {/* coffin on ropes, lowered by the (implied, off-canvas) bearers */}
        <g className="burial-rig" transform="translate(27,34)">
          <line x1="-7" y1="-5" x2="-7" y2="-34" stroke="#c9b98a" strokeWidth="1.6" strokeLinecap="round" />
          <line x1="7" y1="-5" x2="7" y2="-34" stroke="#c9b98a" strokeWidth="1.6" strokeLinecap="round" />
          <path
            d="M-11,0 L-7,-5 L7,-5 L11,0 L7,5 L-7,5 Z"
            fill="#6b4226"
            stroke="#2a160a"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          <rect x="-8" y="-1" width="16" height="2" rx="1" fill="#8a5a34" opacity="0.5" />
          <ellipse cx="-9" cy="0" rx="1.3" ry="2.1" fill="#c9a53e" stroke="#5a4620" strokeWidth="0.8" />
          <ellipse cx="9" cy="0" rx="1.3" ry="2.1" fill="#c9a53e" stroke="#5a4620" strokeWidth="0.8" />
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .burial-rig {
          transform: translate(27px, 34px) rotate(0deg);
          transform-origin: 0px 0px;
          animation: burial-lower 4.5s ease-in-out infinite;
        }
        @keyframes burial-lower {
          0%   { transform: translate(27px, 34px) rotate(0deg); }
          15%  { transform: translate(27px, 36px) rotate(-2deg); }
          40%  { transform: translate(27px, 50px) rotate(2deg); }
          55%  { transform: translate(27px, 50px) rotate(0deg); }
          80%  { transform: translate(27px, 34px) rotate(-1deg); }
          100% { transform: translate(27px, 34px) rotate(0deg); }
        }

        .burial-spade {
          transform-origin: 48px 42px;
          animation: burial-spade-wobble 3s ease-in-out infinite;
        }
        @keyframes burial-spade-wobble {
          0%, 100% { transform: rotate(0deg); }
          50% { transform: rotate(2.5deg); }
        }

        .burial-dust1 { animation: burial-dust 4.5s ease-out infinite; }
        .burial-dust2 { animation: burial-dust 4.5s ease-out infinite; animation-delay: 0.3s; }
        @keyframes burial-dust {
          0%, 38%  { opacity: 0; transform: translateY(0px); }
          45%      { opacity: 0.7; transform: translateY(0px); }
          65%      { opacity: 0; transform: translateY(-4px); }
          100%     { opacity: 0; transform: translateY(-4px); }
        }

        @media (prefers-reduced-motion: reduce) {
          .burial-rig,
          .burial-spade,
          .burial-dust1,
          .burial-dust2 {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
