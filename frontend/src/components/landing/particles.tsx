"use client";

/**
 * Sparse particle field pinned to the bottom of the landing backdrop.
 *
 * A tiny canvas effect (no library — the reference particles.js config only
 * informed the parameters). Each dot has a fixed "rest" spot weighted toward the
 * bottom of the viewport and a soft spring that pulls it back there, so the
 * field naturally gathers low and settles down after any disturbance. Moving the
 * mouse near a dot repulses it (classic particles.js `onhover: repulse`); the
 * spring then reels it home. Colour follows the theme — near-black dots in light
 * mode, near-white in dark — and updates live on theme switch.
 *
 * Kept deliberately few so it decorates without distracting. Honours
 * `prefers-reduced-motion` (one static frame, no loop, no pointer tracking).
 */
import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";

type P = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  restX: number;
  restY: number;
  r: number;
  a: number;
};

export function Particles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();
  // The rAF loop reads the current colour through a ref so a theme switch
  // recolours the dots without tearing down / restarting the animation.
  const colorRef = useRef("0,0,0");
  colorRef.current = resolvedTheme === "dark" ? "255,255,255" : "0,0,0";

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0;
    let H = 0;
    let particles: P[] = [];

    const build = () => {
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Count scales with viewport AREA, so the density (and the connecting-line
      // web, whose reach is a fixed 150px) looks the same at every size instead
      // of the same absolute number crowding small screens / thinning big ones.
      // ~1 dot per 20k px²: a full-screen Mac laptop lands ~1.5× the old amount.
      // Loose clamps only guard phone-tiny and giant-monitor extremes.
      const count = Math.max(16, Math.min(130, Math.round((W * H) / 20000)));
      particles = Array.from({ length: count }, () => {
        // Rest spot: full width, but biased into the bottom ~half of the screen.
        const bias = Math.pow(Math.random(), 1.6); // skew toward the bottom edge
        const restX = Math.random() * W;
        const restY = H - bias * H * 0.5;
        return {
          x: restX + (Math.random() - 0.5) * 80,
          y: restY + (Math.random() - 0.5) * 80,
          vx: 0,
          vy: 0,
          restX,
          restY,
          r: 1 + Math.random() * 2,
          a: 0.25 + Math.random() * 0.3,
        };
      });
    };

    const LINK = 150; // connect dots closer than this (px)
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const rgb = colorRef.current;
      // Connecting lines first, so the dots sit on top of the web.
      ctx.lineWidth = 1;
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dist = Math.hypot(a.x - b.x, a.y - b.y);
          if (dist >= LINK) continue;
          // Fade the link out toward the max distance (0.4 max, per the config).
          ctx.strokeStyle = `rgba(${rgb},${(1 - dist / LINK) * 0.4})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},${p.a})`;
        ctx.fill();
      }
    };

    // Repulse target (viewport/CSS px === canvas px, canvas is fixed full-page).
    const mouse = { x: 0, y: 0, on: false };
    const R = 130;
    const onMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.on = true;
    };
    const onLeave = () => {
      mouse.on = false;
    };

    let raf = 0;
    const tick = () => {
      for (const p of particles) {
        // Soft spring back to the resting (bottom-weighted) position.
        p.vx += (p.restX - p.x) * 0.0009;
        p.vy += (p.restY - p.y) * 0.0018;
        // A little life so the field never looks frozen.
        p.vx += (Math.random() - 0.5) * 0.04;
        p.vy += (Math.random() - 0.5) * 0.04;
        // Repulse from the cursor.
        if (mouse.on) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const dist = Math.hypot(dx, dy) || 1;
          if (dist < R) {
            const f = (1 - dist / R) * 4;
            p.vx += (dx / dist) * f;
            p.vy += (dy / dist) * f;
          }
        }
        p.vx *= 0.9;
        p.vy *= 0.9;
        p.x += p.vx;
        p.y += p.vy;
      }
      draw();
      raf = requestAnimationFrame(tick);
    };

    build();
    if (reduce) {
      // Snap to rest and paint one static frame; no loop, no pointer tracking.
      for (const p of particles) {
        p.x = p.restX;
        p.y = p.restY;
      }
      draw();
      return;
    }

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseout", onLeave, { passive: true });
    window.addEventListener("resize", build);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseout", onLeave);
      window.removeEventListener("resize", build);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden className="absolute inset-0" />;
}
