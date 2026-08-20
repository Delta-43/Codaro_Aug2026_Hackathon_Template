"use client";

/**
 * Generated, on-brand illustration for business mode.
 *
 * The brief calls for AI-generated profile pictures and social content that
 * "logically follow the business offer" (a flashy car, a muddy 4x4, a
 * graduation cap, a yogini at sunset…). This environment has no raster
 * image-generation tool, so instead each offer gets a hand-built, deterministic
 * SVG *scene* — self-contained, theme-agnostic, and CSP-safe (no network). The
 * scene key is chosen by vertical in `business-view.ts`; swap `<BusinessArt>`
 * for real photography whenever assets exist.
 */
import { useId } from "react";
import { cn } from "@/lib/utils";

type Palette = { sky: [string, string]; ground: string; accent: string };

/** A stylised side-profile car, reused across the fleet scenes. */
function Car({ mud, roof = true }: { mud?: boolean; roof?: boolean }) {
  return (
    <g>
      {/* shadow */}
      <ellipse cx="200" cy="238" rx="150" ry="14" fill="#000" opacity="0.18" />
      {roof && (
        <path
          d="M132 176 L168 138 Q174 132 184 132 L250 132 Q262 132 270 140 L300 176 Z"
          fill="#ffffff"
          opacity="0.92"
        />
      )}
      {roof && <rect x="176" y="140" width="42" height="30" rx="4" fill="#1e293b" opacity="0.55" />}
      {roof && <rect x="224" y="140" width="44" height="30" rx="4" fill="#1e293b" opacity="0.55" />}
      <rect x="70" y="172" width="264" height="48" rx="18" fill="currentColor" />
      <rect x="70" y="172" width="264" height="20" rx="12" fill="#ffffff" opacity="0.14" />
      {/* wheels */}
      <circle cx="138" cy="222" r="30" fill="#0f172a" />
      <circle cx="138" cy="222" r="13" fill="#cbd5e1" />
      <circle cx="286" cy="222" r="30" fill="#0f172a" />
      <circle cx="286" cy="222" r="13" fill="#cbd5e1" />
      {/* headlight */}
      <circle cx="326" cy="192" r="6" fill="#fde68a" />
      {mud && (
        <g fill="#7c4a1e" opacity="0.8">
          <circle cx="120" cy="205" r="5" />
          <circle cx="150" cy="212" r="4" />
          <circle cx="300" cy="208" r="5" />
          <circle cx="270" cy="214" r="3" />
          <circle cx="200" cy="216" r="4" />
        </g>
      )}
    </g>
  );
}

/** Seated meditation figure, reused across the group/yoga scenes. */
function LotusFigure({ fill = "#0f172a" }: { fill?: string }) {
  return (
    <g fill={fill}>
      <circle cx="200" cy="150" r="20" />
      <path d="M200 172 q40 6 46 44 q-46 16 -92 0 q6 -38 46 -44 Z" />
      <path d="M156 212 q44 14 88 0 q4 12 -6 18 q-38 12 -76 0 q-10 -6 -6 -18 Z" />
    </g>
  );
}

/** Standing tree-pose figure. */
function StandingFigure({ fill = "#0f172a" }: { fill?: string }) {
  return (
    <g fill={fill}>
      <circle cx="200" cy="96" r="15" />
      <path d="M193 116 h14 v52 l14 66 h-12 l-9 -46 v46 h-10 v-88 Z" />
      <path d="M200 130 q-34 -8 -44 -30 q22 4 44 22 q22 -18 44 -22 q-10 22 -44 30 Z" opacity="0.9" />
      <path d="M198 178 q-22 6 -26 26 q16 -2 28 -18 Z" />
    </g>
  );
}

function GradCap() {
  return (
    <g>
      <path d="M200 92 L128 128 L200 164 L272 128 Z" fill="#0f172a" />
      <path d="M200 108 L162 127 L200 146 L238 127 Z" fill="#ffffff" opacity="0.28" />
      <rect x="196" y="146" width="8" height="34" fill="#0f172a" />
      <path d="M204 152 h34 v40" stroke="#0f172a" strokeWidth="4" fill="none" />
      <circle cx="238" cy="196" r="8" fill="#fbbf24" />
    </g>
  );
}

function OpenBook({ y = 176 }: { y?: number }) {
  return (
    <g>
      <path d={`M200 ${y} q-40 -18 -78 -8 v54 q38 -10 78 8 Z`} fill="#ffffff" opacity="0.95" />
      <path d={`M200 ${y} q40 -18 78 -8 v54 q-38 -10 -78 8 Z`} fill="#e2e8f0" />
      <path d={`M200 ${y} v54`} stroke="#94a3b8" strokeWidth="3" />
      <g stroke="#94a3b8" strokeWidth="2" opacity="0.7">
        <path d={`M140 ${y + 4} h44`} />
        <path d={`M140 ${y + 16} h44`} />
        <path d={`M216 ${y + 4} h44`} />
        <path d={`M216 ${y + 16} h44`} />
      </g>
    </g>
  );
}

function scene(key: string, uid: string) {
  const g = (id: string) => `${id}-${uid}`;

  const carPalettes: Record<string, Palette & { car: string; mud?: boolean; roof?: boolean; back?: string }> = {
    "car-hero": { sky: ["#38bdf8", "#6366f1"], ground: "#1e293b", accent: "#fef08a", car: "#e11d48", back: "mountains" },
    "car-offroad": { sky: ["#a3672f", "#5b3a1a"], ground: "#6b4423", accent: "#fbbf24", car: "#166534", mud: true, back: "dunes" },
    "car-convertible": { sky: ["#fb7185", "#f59e0b"], ground: "#7c2d12", accent: "#fde68a", car: "#0ea5e9", roof: false, back: "sea" },
    "car-city": { sky: ["#7dd3fc", "#22c55e"], ground: "#334155", accent: "#fef9c3", car: "#f97316", back: "buildings" },
    "car-night": { sky: ["#1e1b4b", "#4c1d95"], ground: "#0f172a", accent: "#fde68a", car: "#e2e8f0", back: "stars" },
    "car-buggy": { sky: ["#facc15", "#f97316"], ground: "#a16207", accent: "#fff", car: "#7c3aed", roof: false, back: "dunes" },
  };

  if (carPalettes[key]) {
    const p = carPalettes[key];
    return (
      <>
        <defs>
          <linearGradient id={g("sky")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={p.sky[0]} />
            <stop offset="1" stopColor={p.sky[1]} />
          </linearGradient>
        </defs>
        <rect width="400" height="300" fill={`url(#${g("sky")})`} />
        {p.back === "stars" &&
          [...Array(18)].map((_, i) => (
            <circle key={i} cx={(i * 53) % 400} cy={(i * 37) % 150} r={i % 3 === 0 ? 2 : 1} fill="#fff" opacity="0.8" />
          ))}
        {(p.back === "mountains" || p.back === "dunes") && (
          <path
            d="M0 190 L70 120 L140 175 L220 110 L300 180 L400 130 L400 220 L0 220 Z"
            fill="#000"
            opacity={p.back === "dunes" ? 0.18 : 0.22}
          />
        )}
        {p.back === "buildings" && (
          <g fill="#000" opacity="0.18">
            <rect x="20" y="120" width="40" height="100" />
            <rect x="72" y="90" width="46" height="130" />
            <rect x="130" y="140" width="34" height="80" />
            <rect x="300" y="100" width="44" height="120" />
            <rect x="352" y="130" width="38" height="90" />
          </g>
        )}
        {p.back === "sea" && <rect x="0" y="196" width="400" height="30" fill="#0ea5e9" opacity="0.5" />}
        <circle cx="322" cy="70" r={p.back === "stars" ? 22 : 34} fill={p.accent} opacity={p.back === "stars" ? 0.9 : 0.85} />
        <rect x="0" y="220" width="400" height="80" fill={p.ground} />
        <g style={{ color: p.car }}>
          <Car mud={p.mud} roof={p.roof} />
        </g>
      </>
    );
  }

  switch (key) {
    case "tutor-hero":
      return (
        <>
          <defs>
            <linearGradient id={g("t")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#0f766e" />
              <stop offset="1" stopColor="#134e4a" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("t")})`} />
          <g fill="#fff" opacity="0.14" fontFamily="Outfit, sans-serif" fontSize="30" fontWeight="600">
            <text x="40" y="70">A B C</text>
            <text x="250" y="240">1 2 3</text>
            <text x="60" y="250">π √ ∑</text>
          </g>
          <GradCap />
          <OpenBook y={206} />
        </>
      );
    case "tutor-flag":
      return (
        <>
          <rect width="400" height="100" fill="#c60b1e" />
          <rect y="100" width="400" height="100" fill="#ffc400" />
          <rect y="200" width="400" height="100" fill="#c60b1e" />
          <circle cx="200" cy="150" r="54" fill="#ffffff" opacity="0.16" />
          <OpenBook y={150} />
        </>
      );
    case "tutor-board":
      return (
        <>
          <rect width="400" height="300" fill="#e2e8f0" />
          <rect x="30" y="34" width="340" height="200" rx="8" fill="#ffffff" stroke="#94a3b8" strokeWidth="4" />
          <g stroke="#0f766e" strokeWidth="4" fill="none" strokeLinecap="round">
            <path d="M60 80 q30 -30 60 0 t60 0" />
            <path d="M60 130 h120" />
            <path d="M60 160 h180" />
          </g>
          <text x="250" y="120" fontFamily="Outfit, sans-serif" fontSize="40" fontWeight="700" fill="#e11d48">
            x²
          </text>
          <rect x="300" y="150" width="12" height="90" rx="6" fill="#f59e0b" transform="rotate(24 306 195)" />
        </>
      );
    case "tutor-online":
      return (
        <>
          <defs>
            <linearGradient id={g("o")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#6366f1" />
              <stop offset="1" stopColor="#0ea5e9" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("o")})`} />
          <rect x="80" y="70" width="240" height="150" rx="10" fill="#0f172a" />
          <rect x="92" y="82" width="216" height="126" rx="6" fill="#e2e8f0" />
          <circle cx="200" cy="130" r="24" fill="#94a3b8" />
          <path d="M170 190 q30 -34 60 0 Z" fill="#94a3b8" />
          <rect x="150" y="222" width="100" height="12" rx="6" fill="#0f172a" />
          <path d="M186 132 l22 12 l-22 12 Z" fill="#fff" />
        </>
      );
    case "tutor-cap":
      return (
        <>
          <defs>
            <radialGradient id={g("c")} cx="0.5" cy="0.4" r="0.7">
              <stop offset="0" stopColor="#334155" />
              <stop offset="1" stopColor="#0f172a" />
            </radialGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("c")})`} />
          <g transform="translate(0 20) scale(1.15) translate(-26 -18)">
            <GradCap />
          </g>
        </>
      );
    case "tutor-books":
      return (
        <>
          <rect width="400" height="300" fill="#fee2e2" />
          <g>
            <rect x="120" y="188" width="170" height="26" rx="4" fill="#0ea5e9" />
            <rect x="130" y="160" width="160" height="26" rx="4" fill="#f59e0b" />
            <rect x="112" y="132" width="176" height="26" rx="4" fill="#e11d48" />
            <rect x="140" y="104" width="140" height="26" rx="4" fill="#22c55e" />
          </g>
        </>
      );

    case "yoga-hero":
      return (
        <>
          <defs>
            <linearGradient id={g("y")} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#f472b6" />
              <stop offset="0.5" stopColor="#fb923c" />
              <stop offset="1" stopColor="#7c3aed" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("y")})`} />
          <circle cx="200" cy="150" r="66" fill="#fde68a" opacity="0.9" />
          <path d="M0 210 L90 160 L180 200 L280 155 L400 205 L400 300 L0 300 Z" fill="#4c1d95" opacity="0.55" />
          <LotusFigure fill="#2e1065" />
        </>
      );
    case "yoga-beach":
      return (
        <>
          <defs>
            <linearGradient id={g("yb")} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#38bdf8" />
              <stop offset="1" stopColor="#0369a1" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("yb")})`} />
          <circle cx="300" cy="80" r="30" fill="#fde68a" />
          <rect x="0" y="196" width="400" height="104" fill="#fcd9a8" />
          <path d="M0 196 q100 -16 200 0 t200 0 v10 H0 Z" fill="#0ea5e9" opacity="0.5" />
          <g stroke="#166534" strokeWidth="8" fill="none">
            <path d="M70 196 q-6 -60 -2 -90" />
          </g>
          <path d="M66 96 q40 -18 60 6 q-40 -4 -60 -6 Z" fill="#22c55e" />
          <LotusFigure fill="#7c2d12" />
        </>
      );
    case "yoga-pose":
      return (
        <>
          <defs>
            <radialGradient id={g("yp")} cx="0.5" cy="0.45" r="0.7">
              <stop offset="0" stopColor="#fda4af" />
              <stop offset="1" stopColor="#be123c" />
            </radialGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("yp")})`} />
          {[...Array(12)].map((_, i) => (
            <rect
              key={i}
              x="198"
              y="30"
              width="4"
              height="120"
              fill="#fff"
              opacity="0.22"
              transform={`rotate(${i * 30} 200 150)`}
            />
          ))}
          <StandingFigure fill="#4c0519" />
        </>
      );
    case "yoga-studio":
      return (
        <>
          <defs>
            <linearGradient id={g("ys")} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#fed7aa" />
              <stop offset="1" stopColor="#fb923c" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("ys")})`} />
          <rect x="60" y="60" width="90" height="120" rx="45" fill="#fff" opacity="0.35" />
          <rect x="250" y="60" width="90" height="120" rx="45" fill="#fff" opacity="0.35" />
          <rect x="120" y="238" width="160" height="16" rx="8" fill="#7c2d12" />
          <path d="M300 200 q10 -60 -6 -80 q28 12 30 44 q-2 26 -24 36 Z" fill="#166534" />
          <LotusFigure fill="#7c2d12" />
        </>
      );
    case "yoga-breath":
      return (
        <>
          <defs>
            <radialGradient id={g("yr")} cx="0.5" cy="0.5" r="0.6">
              <stop offset="0" stopColor="#5eead4" />
              <stop offset="1" stopColor="#0f766e" />
            </radialGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("yr")})`} />
          {[90, 66, 44].map((r, i) => (
            <circle key={i} cx="200" cy="150" r={r} fill="none" stroke="#fff" strokeWidth="3" opacity={0.25 + i * 0.12} />
          ))}
          <LotusFigure fill="#042f2e" />
        </>
      );
    case "yoga-candle":
      return (
        <>
          <rect width="400" height="300" fill="#1c1917" />
          {[100, 200, 300].map((x, i) => (
            <g key={i}>
              <circle cx={x} cy={110} r={26} fill="#f59e0b" opacity="0.25" />
              <ellipse cx={x} cy={112} r="6" ry="12" rx="6" fill="#fde68a" />
              <rect x={x - 6} y="120" width="12" height="30" rx="3" fill="#fbbf24" opacity="0.8" />
            </g>
          ))}
          <LotusFigure fill="#7c2d12" />
        </>
      );

    case "hotel-hero":
      return (
        <>
          <defs>
            <linearGradient id={g("hh")} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#38bdf8" />
              <stop offset="1" stopColor="#0284c7" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("hh")})`} />
          <circle cx="330" cy="60" r="28" fill="#fde68a" />
          <rect x="118" y="66" width="164" height="158" rx="6" fill="#f8fafc" />
          {[...Array(4)].map((_, row) =>
            [...Array(4)].map((__, col) => (
              <rect key={`${row}-${col}`} x={136 + col * 34} y={84 + row * 34} width="20" height="22" rx="2" fill="#38bdf8" opacity="0.55" />
            )),
          )}
          <rect x="0" y="224" width="400" height="76" fill="#0ea5e9" />
          <rect x="0" y="224" width="400" height="10" fill="#7dd3fc" opacity="0.7" />
        </>
      );
    case "hotel-room":
      return (
        <>
          <rect width="400" height="300" fill="#fde9c8" />
          <rect x="40" y="40" width="120" height="90" rx="4" fill="#7dd3fc" opacity="0.7" />
          <rect x="40" y="40" width="120" height="90" rx="4" fill="none" stroke="#fff" strokeWidth="6" />
          <rect x="60" y="180" width="290" height="70" rx="8" fill="#fff" />
          <rect x="60" y="150" width="290" height="40" rx="8" fill="#f1f5f9" />
          <rect x="70" y="120" width="80" height="40" rx="6" fill="#fca5a5" />
          <rect x="90" y="250" width="230" height="30" fill="#e2e8f0" />
        </>
      );
    case "venue-hero":
    case "venue-stage":
      return (
        <>
          <defs>
            <radialGradient id={g("vh")} cx="0.5" cy="0.2" r="0.9">
              <stop offset="0" stopColor="#6d28d9" />
              <stop offset="1" stopColor="#1e1b4b" />
            </radialGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("vh")})`} />
          {[120, 200, 280].map((x, i) => (
            <path key={i} d={`M${x} 20 L${x - 60} 260 L${x + 60} 260 Z`} fill="#a78bfa" opacity="0.22" />
          ))}
          <ellipse cx="200" cy="252" rx="150" ry="26" fill="#f472b6" opacity="0.35" />
          <path d="M120 250 q80 -70 160 0 Z" fill="#0f172a" opacity="0.6" />
          {[150, 200, 250].map((x, i) => (
            <circle key={i} cx={x} cy={40} r="8" fill="#fde68a" />
          ))}
        </>
      );
    case "catering-hero":
      return (
        <>
          <defs>
            <linearGradient id={g("ch")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#fb923c" />
              <stop offset="1" stopColor="#b45309" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("ch")})`} />
          <ellipse cx="200" cy="170" rx="120" ry="30" fill="#000" opacity="0.15" />
          <circle cx="200" cy="160" r="96" fill="#f8fafc" />
          <circle cx="200" cy="160" r="70" fill="#fef3c7" />
          <circle cx="200" cy="150" r="34" fill="#65a30d" />
          <circle cx="176" cy="176" r="16" fill="#dc2626" />
          <circle cx="228" cy="176" r="14" fill="#f59e0b" />
          <path d="M120 90 q80 -30 160 0" stroke="#fff" strokeWidth="5" fill="none" opacity="0.6" />
        </>
      );
    case "catering-table":
      return (
        <>
          <rect width="400" height="300" fill="#fef3c7" />
          <rect x="0" y="200" width="400" height="100" fill="#d97706" opacity="0.35" />
          {[80, 200, 320].map((x, i) => (
            <g key={i}>
              <circle cx={x} cy={190} r="40" fill="#f8fafc" />
              <circle cx={x} cy={185} r="22" fill={["#65a30d", "#dc2626", "#f59e0b"][i]} />
            </g>
          ))}
        </>
      );
    case "equipment-hero":
    case "equipment-drill":
      return (
        <>
          <defs>
            <linearGradient id={g("eh")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#f59e0b" />
              <stop offset="1" stopColor="#78350f" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("eh")})`} />
          {/* drill body */}
          <rect x="120" y="120" width="120" height="50" rx="12" fill="#111827" />
          <rect x="230" y="132" width="70" height="26" rx="6" fill="#374151" />
          <rect x="300" y="138" width="34" height="14" rx="4" fill="#e5e7eb" />
          <path d="M140 170 l24 0 l-6 60 l-12 0 Z" fill="#111827" />
          <rect x="150" y="150" width="24" height="60" rx="6" fill="#f59e0b" />
          <circle cx="330" cy="145" r="8" fill="#fbbf24" />
        </>
      );
    case "services-hero":
      return (
        <>
          <defs>
            <linearGradient id={g("sh")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#f472b6" />
              <stop offset="1" stopColor="#7c3aed" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("sh")})`} />
          {/* scissors */}
          <circle cx="150" cy="210" r="20" fill="none" stroke="#fff" strokeWidth="8" />
          <circle cx="150" cy="150" r="20" fill="none" stroke="#fff" strokeWidth="8" />
          <path d="M162 200 L280 90" stroke="#fff" strokeWidth="8" strokeLinecap="round" />
          <path d="M162 160 L280 120" stroke="#fff" strokeWidth="8" strokeLinecap="round" />
          <path d="M120 70 l10 24 26 4 -20 18 6 26 -22 -14 -22 14 6 -26 -20 -18 26 -4 Z" fill="#fde68a" opacity="0.9" />
        </>
      );
    case "trades-hero":
    case "trades-tools":
      return (
        <>
          <defs>
            <linearGradient id={g("th2")} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#fbbf24" />
              <stop offset="1" stopColor="#b45309" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("th2")})`} />
          {/* wrench */}
          <path d="M110 200 l70 -70 q-24 -30 6 -54 l18 18 -14 14 14 14 14 -14 18 18 q-24 30 -54 6 l-70 70 q-8 8 -16 0 t0 -16 Z" fill="#e5e7eb" stroke="#334155" strokeWidth="3" />
          {/* hammer */}
          <rect x="236" y="90" width="70" height="26" rx="4" fill="#334155" />
          <rect x="250" y="116" width="14" height="110" rx="4" fill="#a16207" />
          {/* hard hat */}
          <path d="M150 70 q40 -40 80 0 Z" fill="#f97316" />
          <rect x="140" y="66" width="100" height="10" rx="5" fill="#f97316" />
        </>
      );
    case "cleaning-hero":
    case "cleaning-spray":
      return (
        <>
          <defs>
            <linearGradient id={g("cl")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#22d3ee" />
              <stop offset="1" stopColor="#0e7490" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("cl")})`} />
          {/* spray bottle */}
          <rect x="150" y="120" width="70" height="110" rx="12" fill="#f8fafc" />
          <rect x="165" y="150" width="40" height="50" rx="4" fill="#5eead4" opacity="0.8" />
          <rect x="170" y="96" width="30" height="30" fill="#e2e8f0" />
          <path d="M170 108 l-40 -6 0 -14 40 6 Z" fill="#e2e8f0" />
          {/* sparkles */}
          {[[260, 90], [300, 150], [250, 190], [320, 100]].map(([x, y], i) => (
            <path key={i} d={`M${x} ${y - 12} l4 8 8 4 -8 4 -4 8 -4 -8 -8 -4 8 -4 Z`} fill="#fff" opacity="0.9" />
          ))}
        </>
      );
    case "consulting-hero":
    case "consulting-chart":
      return (
        <>
          <defs>
            <linearGradient id={g("co")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#0ea5e9" />
              <stop offset="1" stopColor="#1e3a8a" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("co")})`} />
          {[[110, 90], [160, 70], [210, 110], [260, 60], [310, 40]].map(([x, y], i) => (
            <rect key={i} x={x - 16} y={230 - y} width="32" height={y} rx="4" fill="#fff" opacity={0.55 + i * 0.08} />
          ))}
          <path d="M96 190 L150 150 L200 178 L250 130 L326 96" stroke="#fde68a" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M300 96 l26 0 0 26" stroke="#fde68a" strokeWidth="5" fill="none" strokeLinecap="round" />
        </>
      );

    case "grad-teal":
    case "grad-rose":
    case "grad-amber": {
      const pal =
        key === "grad-teal"
          ? ["#2dd4bf", "#0f766e"]
          : key === "grad-rose"
            ? ["#fb7185", "#be123c"]
            : ["#fbbf24", "#d97706"];
      return (
        <>
          <defs>
            <linearGradient id={g("gr")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor={pal[0]} />
              <stop offset="1" stopColor={pal[1]} />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("gr")})`} />
          <circle cx="120" cy="90" r="70" fill="#fff" opacity="0.12" />
          <circle cx="300" cy="220" r="90" fill="#fff" opacity="0.1" />
          <path d="M300 60 l8 20 22 4 -16 15 4 22 -18 -11 -18 11 4 -22 -16 -15 22 -4 Z" fill="#fff" opacity="0.6" />
        </>
      );
    }

    default:
      return (
        <>
          <defs>
            <linearGradient id={g("f")} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#6366f1" />
              <stop offset="1" stopColor="#e11d48" />
            </linearGradient>
          </defs>
          <rect width="400" height="300" fill={`url(#${g("f")})`} />
          <path d="M200 96 l16 40 42 4 -32 28 10 42 -36 -24 -36 24 10 -42 -32 -28 42 -4 Z" fill="#fff" opacity="0.9" />
        </>
      );
  }
}

export function BusinessArt({ scene: key, className }: { scene: string; className?: string }) {
  const uid = useId().replace(/:/g, "");
  return (
    <svg
      viewBox="0 0 400 300"
      preserveAspectRatio="xMidYMid slice"
      className={cn("block h-full w-full", className)}
      role="img"
      aria-hidden
    >
      {scene(key, uid)}
    </svg>
  );
}
