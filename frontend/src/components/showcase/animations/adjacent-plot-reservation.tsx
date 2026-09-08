// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { cn } from "@/lib/utils";
import type { ServiceAnimationComponent } from "@/components/showcase/animations/service-animation-contract";

/**
 * "Adjacent Plot Reservation" — choose your neighbours, literally. Two
 * headstones side by side: on the left, the existing neighbour — solid,
 * engraved, tended with a couple of small flowers. On the right, the plot
 * being reserved — drawn as a dashed, half-there outline (nobody's home yet)
 * with a tiny hinged "RESERVED" placard staked in front of it, swinging
 * gently like a realtor's for-sale sign. That's the whole joke: real-estate
 * signage grafted onto a cemetery plot.
 *
 * Cartoon cel-shaded style: flat fills + bold dark outlines, a small warm/cool
 * palette, legible on near-black. Every position transform is applied via a
 * static (non-animated) wrapper <g>, with the CSS animation only ever
 * rotating/offsetting an inner, transform-attribute-free <g> — this sidesteps
 * the SVG-attribute-vs-CSS-transform override footgun entirely, so nothing
 * needs its base position re-baked into each keyframe. All classes/keyframes
 * are prefixed `adjacent-` so this file's injected <style> can't collide with
 * sibling showcase animations mounted on the same page.
 */
export const AdjacentPlotReservationAnimation: ServiceAnimationComponent = ({ className, title }) => {
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
        <path d="M0 53 Q16 50 32 52 Q48 54 64 52 L64 64 L0 64 Z" fill="#2f6b40" />
        <path d="M0 53 Q16 50 32 52 Q48 54 64 52" fill="none" stroke="#1c4028" strokeWidth="1.5" />

        {/* left headstone — existing neighbour, solid + engraved */}
        <g transform="translate(18,53)">
          <path
            d="M-8 0 L-8 -18 Q-8 -26 0 -26 Q8 -26 8 -18 L8 0 Z"
            fill="#9aa0a8"
            stroke="#20232b"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          <path d="M0 -21 L0 -14 M-3 -18 L3 -18" fill="none" stroke="#5c6068" strokeWidth="1.2" strokeLinecap="round" />
          <line x1="-4" y1="-9" x2="4" y2="-9" stroke="#5c6068" strokeWidth="1" />
          <line x1="-4" y1="-6" x2="4" y2="-6" stroke="#5c6068" strokeWidth="1" />
          <line x1="-4" y1="-3" x2="4" y2="-3" stroke="#5c6068" strokeWidth="1" />
          <path d="M-8 -3 Q-5 -6 -2 -3 Q-5 0 -8 -3 Z" fill="#3f6b46" opacity="0.6" />
        </g>

        {/* right headstone — the plot being reserved, dashed and half-there */}
        <g transform="translate(44,53)">
          <path
            className="adjacent-dash-march"
            d="M-8 0 L-8 -18 Q-8 -26 0 -26 Q8 -26 8 -18 L8 0 Z"
            fill="#4b505c"
            fillOpacity="0.25"
            stroke="#c7ccd6"
            strokeWidth="1.8"
            strokeDasharray="4 3"
            strokeLinejoin="round"
          />
        </g>

        {/* small flowers tending the existing neighbour's plot */}
        <g transform="translate(11,53)">
          <g className="adjacent-flower-bob">
            <path d="M0 0 Q1 -5 0 -9" fill="none" stroke="#3f6b46" strokeWidth="1.3" strokeLinecap="round" />
            <circle cx="0" cy="-10" r="2.3" fill="#c9536b" stroke="#20232b" strokeWidth="1" />
            <path d="M-3 0 Q-4 -3 -3 -6" fill="none" stroke="#3f6b46" strokeWidth="1" strokeLinecap="round" />
            <circle cx="-3" cy="-6.5" r="1.5" fill="#c9536b" stroke="#20232b" strokeWidth="0.8" />
          </g>
        </g>

        {/* grass tufts, swaying */}
        <g transform="translate(30,54)">
          <g className="adjacent-grass-tuft">
            <path d="M-2 0 Q-3 -5 -1 -6" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
            <path d="M0 0 Q0 -6 1 -7" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
            <path d="M2 0 Q3 -5 2 -6" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
          </g>
        </g>
        <g transform="translate(56,54)">
          <g className="adjacent-grass-tuft">
            <path d="M-2 0 Q-3 -5 -1 -6" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
            <path d="M0 0 Q0 -6 1 -7" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
            <path d="M2 0 Q3 -5 2 -6" stroke="#2f6b40" strokeWidth="1.2" fill="none" strokeLinecap="round" />
          </g>
        </g>

        {/* "RESERVED" sign staked in front of the reserved plot, realtor-style */}
        <g transform="translate(37,55)">
          <rect x="-1.3" y="-15" width="2.6" height="15" fill="#6b4a2f" stroke="#20232b" strokeWidth="1.2" />
          <path d="M-1 -15 L8 -15" stroke="#6b4a2f" strokeWidth="2.4" strokeLinecap="round" />
          <g transform="translate(8,-15)">
            <g className="adjacent-sign-swing">
              <line x1="-3" y1="0" x2="-3" y2="4" stroke="#20232b" strokeWidth="0.9" />
              <line x1="3" y1="0" x2="3" y2="4" stroke="#20232b" strokeWidth="0.9" />
              <rect x="-8" y="4" width="16" height="8" rx="1.2" fill="#f5efe0" stroke="#20232b" strokeWidth="1.4" />
              <text
                x="0"
                y="10.5"
                fontSize="5.2"
                fontWeight="700"
                fill="#7a1f1f"
                textAnchor="middle"
                fontFamily="Georgia, serif"
                textLength="14"
                lengthAdjust="spacingAndGlyphs"
              >
                RESERVED
              </text>
            </g>
          </g>
        </g>
      </svg>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .adjacent-sign-swing { animation: adjacent-swing 3s ease-in-out infinite; transform-origin: 0px 0px; }
        @keyframes adjacent-swing {
          0%, 100% { transform: rotate(-5deg); }
          50% { transform: rotate(5deg); }
        }

        .adjacent-dash-march { animation: adjacent-dash 6s linear infinite; }
        @keyframes adjacent-dash {
          from { stroke-dashoffset: 0; }
          to { stroke-dashoffset: -28; }
        }

        .adjacent-flower-bob { animation: adjacent-bob 3.5s ease-in-out infinite; transform-origin: 0px 0px; }
        @keyframes adjacent-bob {
          0%, 100% { transform: rotate(-5deg); }
          50% { transform: rotate(5deg); }
        }

        .adjacent-grass-tuft { animation: adjacent-tuft-sway 4s ease-in-out infinite; transform-origin: 0px 0px; }
        @keyframes adjacent-tuft-sway {
          0%, 100% { transform: rotate(-6deg); }
          50% { transform: rotate(6deg); }
        }

        @media (prefers-reduced-motion: reduce) {
          .adjacent-sign-swing,
          .adjacent-dash-march,
          .adjacent-flower-bob,
          .adjacent-grass-tuft {
            animation: none;
          }
        }
          `,
        }}
      />
    </>
  );
};
