// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Cremation" — a sealed cinerary urn on its pedestal, breathing gently, with
 * a soft double wisp of smoke/ash curling up from the lid and dissolving into
 * drifting gold sparkle motes. One image doing double duty: the wisp reads as
 * the retort's flame, and the motes drifting apart like fireflies read as the
 * "scatter at the garden of remembrance" option — gentle rather than grim.
 *
 * Cel-shaded cartoon: flat bronze urn with a bold dark outline, a translucent
 * lavender-grey smoke ribbon, and warm gold sparkles. Every class/keyframe is
 * prefixed `cremation-` so this file's injected <style> can't collide with
 * the other showcase animations mounted alongside it.
 */
export const CremationAnimation: ServiceAnimationComponent = ({ className, title }) => {
  return (
    <>
      <svg
        viewBox="0 0 64 64"
        className={cn("overflow-visible", className)}
        aria-hidden={!title}
        role={title ? "img" : undefined}
      >
        {title ? <title>{title}</title> : null}

        {/* Ground shadow, breathing opposite the urn's bob for a grounded feel */}
        <ellipse
          className="cremation-shadow"
          cx="32"
          cy="55"
          rx="13"
          ry="2.6"
          fill="#000000"
          opacity="0.35"
        />

        {/* Rising smoke / ash, drawn behind the urn so it emerges from the lid */}
        <g className="cremation-smoke-wrap">
          <path
            className="cremation-smoke-a"
            d="M32,16 C29,13.5 30,10.5 32,9 C34,7.5 30,5 32,3 C34,1 31,-1.5 32,-4"
            fill="none"
            stroke="#b9c6e0"
            strokeWidth="3.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.65"
          />
          <path
            className="cremation-smoke-b"
            d="M33,15.5 C35.5,13 34,10.5 32.5,8.5 C31,6.5 35,4.5 33,2 C31.3,0 34.5,-2 33,-4.5"
            fill="none"
            stroke="#b9c6e0"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.5"
          />
        </g>

        {/* Sparkle motes drifting up and out of the smoke, like fireflies */}
        <g className="cremation-sparkles" fill="#ffd77a">
          <g className="cremation-spark-1" transform="translate(26,10)">
            <path d="M0,-2.4 L0.6,-0.6 L2.4,0 L0.6,0.6 L0,2.4 L-0.6,0.6 L-2.4,0 L-0.6,-0.6 Z" />
          </g>
          <g className="cremation-spark-2" transform="translate(38,7)">
            <path d="M0,-2 L0.5,-0.5 L2,0 L0.5,0.5 L0,2 L-0.5,0.5 L-2,0 L-0.5,-0.5 Z" />
          </g>
          <g className="cremation-spark-3" transform="translate(23,3)">
            <path d="M0,-1.8 L0.45,-0.45 L1.8,0 L0.45,0.45 L0,1.8 L-0.45,0.45 L-1.8,0 L-0.45,-0.45 Z" />
          </g>
          <g className="cremation-spark-4" transform="translate(41,1)">
            <path d="M0,-2.2 L0.55,-0.55 L2.2,0 L0.55,0.55 L0,2.2 L-0.55,0.55 L-2.2,0 L-0.55,-0.55 Z" />
          </g>
          <g className="cremation-spark-5" transform="translate(30,-3)">
            <path d="M0,-1.6 L0.4,-0.4 L1.6,0 L0.4,0.4 L0,1.6 L-0.4,0.4 L-1.6,0 L-0.4,-0.4 Z" />
          </g>
          <g className="cremation-spark-6" transform="translate(35,12)">
            <path d="M0,-2 L0.5,-0.5 L2,0 L0.5,0.5 L0,2 L-0.5,0.5 L-2,0 L-0.5,-0.5 Z" />
          </g>
        </g>

        {/* The urn itself — gently bobs/breathes */}
        <g
          className="cremation-urn-wrap"
          stroke="#1c130c"
          strokeWidth="1.6"
          strokeLinejoin="round"
          strokeLinecap="round"
        >
          {/* pedestal foot */}
          <rect x="25" y="51" width="14" height="4" rx="1.4" fill="#8a5a2b" />

          {/* urn body */}
          <path
            d="M27,24 L37,24 C40,24.5 42,28 42.5,33 C43,38 42,43 38,47.5 C36,50 34,51 32,51 C30,51 28,50 26,47.5 C22,43 21,38 21.5,33 C22,28 24,24.5 27,24 Z"
            fill="#c98a46"
          />

          {/* shine highlight on the body, no stroke of its own */}
          <path
            d="M26.5,29 C24.8,33 24.6,38 27,43.5 C25.2,39.5 25,33.8 26.5,29 Z"
            fill="#eab776"
            stroke="none"
            opacity="0.7"
          />

          {/* lid */}
          <ellipse cx="32" cy="23" rx="6.5" ry="2.6" fill="#b8763a" />
          <rect x="30.4" y="19.6" width="3.2" height="3.4" rx="1.2" fill="#b8763a" />
          <circle cx="32" cy="18.3" r="2.3" fill="#9c6530" />
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .cremation-urn-wrap { animation: cremation-bob 4s ease-in-out infinite; transform-origin: 32px 51px; }
        @keyframes cremation-bob {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-1.2px) scale(1.01, 0.99); }
        }

        .cremation-shadow { animation: cremation-shadow-pulse 4s ease-in-out infinite; transform-origin: 32px 55px; }
        @keyframes cremation-shadow-pulse {
          0%, 100% { transform: scaleX(1); opacity: 0.35; }
          50% { transform: scaleX(0.92); opacity: 0.25; }
        }

        .cremation-smoke-a { animation: cremation-smoke-rise-a 3.8s ease-in-out infinite; transform-origin: 32px 16px; }
        @keyframes cremation-smoke-rise-a {
          0% { transform: translate(0,0) scale(0.6) rotate(-4deg); opacity: 0; }
          15% { opacity: 0.65; }
          55% { transform: translate(-3px,-13px) scale(1) rotate(6deg); opacity: 0.5; }
          100% { transform: translate(2px,-24px) scale(1.15) rotate(-3deg); opacity: 0; }
        }

        .cremation-smoke-b { animation: cremation-smoke-rise-b 4.4s ease-in-out infinite; animation-delay: 1.1s; transform-origin: 33px 15.5px; }
        @keyframes cremation-smoke-rise-b {
          0% { transform: translate(0,0) scale(0.5) rotate(4deg); opacity: 0; }
          18% { opacity: 0.5; }
          60% { transform: translate(4px,-15px) scale(0.95) rotate(-6deg); opacity: 0.35; }
          100% { transform: translate(-2px,-26px) scale(1.1) rotate(4deg); opacity: 0; }
        }

        .cremation-spark-1 { animation: cremation-spark-move-1 3.6s ease-in-out infinite; animation-delay: 0s; }
        @keyframes cremation-spark-move-1 {
          0% { transform: translate(26px,10px) scale(0.3); opacity: 0; }
          20% { opacity: 1; }
          65% { transform: translate(19px,-6px) scale(1); opacity: 0.9; }
          100% { transform: translate(15px,-16px) scale(0.3); opacity: 0; }
        }

        .cremation-spark-2 { animation: cremation-spark-move-2 4.2s ease-in-out infinite; animation-delay: 0.6s; }
        @keyframes cremation-spark-move-2 {
          0% { transform: translate(38px,7px) scale(0.3); opacity: 0; }
          22% { opacity: 1; }
          65% { transform: translate(45px,-9px) scale(1); opacity: 0.85; }
          100% { transform: translate(49px,-19px) scale(0.3); opacity: 0; }
        }

        .cremation-spark-3 { animation: cremation-spark-move-3 3.2s ease-in-out infinite; animation-delay: 1.3s; }
        @keyframes cremation-spark-move-3 {
          0% { transform: translate(23px,3px) scale(0.25); opacity: 0; }
          25% { opacity: 0.9; }
          65% { transform: translate(16px,-11px) scale(0.9); opacity: 0.7; }
          100% { transform: translate(12px,-19px) scale(0.25); opacity: 0; }
        }

        .cremation-spark-4 { animation: cremation-spark-move-4 4.6s ease-in-out infinite; animation-delay: 1.9s; }
        @keyframes cremation-spark-move-4 {
          0% { transform: translate(41px,1px) scale(0.3); opacity: 0; }
          20% { opacity: 1; }
          65% { transform: translate(48px,-13px) scale(1); opacity: 0.85; }
          100% { transform: translate(52px,-24px) scale(0.3); opacity: 0; }
        }

        .cremation-spark-5 { animation: cremation-spark-move-5 3.4s ease-in-out infinite; animation-delay: 2.4s; }
        @keyframes cremation-spark-move-5 {
          0% { transform: translate(30px,-3px) scale(0.25); opacity: 0; }
          25% { opacity: 0.9; }
          65% { transform: translate(27px,-14px) scale(0.85); opacity: 0.7; }
          100% { transform: translate(25px,-22px) scale(0.25); opacity: 0; }
        }

        .cremation-spark-6 { animation: cremation-spark-move-6 4s ease-in-out infinite; animation-delay: 0.3s; }
        @keyframes cremation-spark-move-6 {
          0% { transform: translate(35px,12px) scale(0.3); opacity: 0; }
          20% { opacity: 1; }
          65% { transform: translate(40px,-3px) scale(1); opacity: 0.8; }
          100% { transform: translate(43px,-13px) scale(0.3); opacity: 0; }
        }

        @media (prefers-reduced-motion: reduce) {
          .cremation-urn-wrap,
          .cremation-shadow,
          .cremation-smoke-a,
          .cremation-smoke-b,
          .cremation-spark-1,
          .cremation-spark-2,
          .cremation-spark-3,
          .cremation-spark-4,
          .cremation-spark-5,
          .cremation-spark-6 {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
