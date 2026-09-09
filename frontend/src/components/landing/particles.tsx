// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Sparse particle field pinned to the bottom of the landing backdrop.
 *
 * A tiny canvas effect (no library, the reference particles.js config only
 * informed the parameters). Each dot has a fixed "rest" spot weighted toward the
 * bottom of the viewport and a soft spring that pulls it back there, so the
 * field naturally gathers low and settles down after any disturbance. Colour
 * follows the theme, near-black dots in light mode, near-white in dark, and
 * updates live on theme switch.
 *
 * The web of links between near neighbours is the point, not decoration: it is
 * the shape the landing copy describes, one neutral spine with everything
 * hanging off it. So the pointer joins the web rather than only scattering it.
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
  restYUp: number;
  /** Depth, 0 (far) to 1 (near). Drives size, opacity and spring rate together,
   *  which is what reads as volume rather than a flat sheet of identical dots. */
  z: number;
  r: number;
  a: number;
  ky: number;
};

const LINK = 150; // connect dots closer than this (px)
const LINK2 = LINK * LINK; // compared against squared distance, so no sqrt
const R = 130; // pointer influence radius
const R2 = R * R;
const MAX_LINK_ALPHA = 0.4;
/** Links are bucketed by opacity and stroked once per bucket. One path per link
 *  is thousands of draw calls a frame; eight buckets is eight, and the banding
 *  is invisible at these alphas. */
const BUCKETS = 8;

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

    // Count scales with viewport AREA, so the density (and the connecting-line
    // web, whose reach is a fixed 150px) looks the same at every size instead
    // of the same absolute number crowding small screens / thinning big ones.
    const countFor = (w: number, h: number) =>
      Math.max(16, Math.min(130, Math.round((w * h) / 20000)));

    const makeParticle = (): P => {
      // Rest spot: full width, but biased into the bottom ~half of the screen.
      const bias = Math.pow(Math.random(), 1.6); // skew toward the bottom edge
      const restX = Math.random() * W;
      const restY = H - bias * H * 0.5;
      // Independent upper-half rest spot for the bottom-of-page state, the
      // same bottom-weighted formula mirrored to the top edge. Drawn on its
      // own (not reflected from restY) so *every* dot gets a real destination
      // up top: reflecting restY would pin any dot resting near the middle to
      // the middle line, leaving stragglers stuck there mid-migration.
      const biasUp = Math.pow(Math.random(), 1.6);
      const restYUp = biasUp * H * 0.5;
      const z = Math.random();
      return {
        x: restX + (Math.random() - 0.5) * 80,
        y: restY + (Math.random() - 0.5) * 80,
        vx: 0,
        vy: 0,
        restX,
        restY,
        restYUp,
        z,
        r: 0.8 + z * 2.2,
        a: 0.15 + z * 0.4,
        // Per-dot vertical spring rate, scaled by depth so near dots answer
        // faster than far ones. Varying it (instead of one shared constant)
        // means dots settle, and migrate up at the bottom of the page, at
        // their own pace, so the field never moves as one rigid sheet. That
        // staggering dissolves the migration instead of sweeping a visible
        // line through the middle.
        ky: (0.0009 + Math.random() * 0.0025) * (0.55 + z * 0.75),
      };
    };

    const resizeCanvas = () => {
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const build = () => {
      W = window.innerWidth;
      H = window.innerHeight;
      resizeCanvas();
      particles = Array.from({ length: countFor(W, H) }, makeParticle);
    };

    /** Rescale the existing field into the new viewport instead of rebuilding
     *  it. A rebuild re-randomises every rest spot, so resizing used to jolt
     *  the whole field; scaling keeps each dot where it was, proportionally. */
    const reflow = () => {
      const prevW = W || window.innerWidth;
      const prevH = H || window.innerHeight;
      W = window.innerWidth;
      H = window.innerHeight;
      resizeCanvas();

      const sx = W / prevW;
      const sy = H / prevH;
      for (const p of particles) {
        p.x *= sx;
        p.y *= sy;
        p.restX *= sx;
        p.restY *= sy;
        p.restYUp *= sy;
      }

      const want = countFor(W, H);
      while (particles.length < want) particles.push(makeParticle());
      if (particles.length > want) particles.length = want;
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const rgb = colorRef.current;

      // Connecting lines first, so the dots sit on top of the web. Collected
      // into opacity buckets and stroked once each, rather than a path per link.
      ctx.lineWidth = 1;
      const buckets: Path2D[] = Array.from({ length: BUCKETS }, () => new Path2D());
      const addLink = (ax: number, ay: number, bx: number, by: number, alpha: number) => {
        const i = Math.min(BUCKETS - 1, Math.max(0, Math.floor(alpha * BUCKETS)));
        buckets[i].moveTo(ax, ay);
        buckets[i].lineTo(bx, by);
      };

      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          // Squared compare: `Math.hypot` here ran ~500k times a second and is
          // slow by design (it guards against overflow). Only the few pairs
          // that pass need a real distance.
          const d2 = dx * dx + dy * dy;
          if (d2 >= LINK2) continue;
          const dist = Math.sqrt(d2);
          // Fade with distance, then again with the pair's depth, so the web
          // recedes with the dots it joins instead of sitting flat on top.
          addLink(a.x, a.y, b.x, b.y, (1 - dist / LINK) * ((a.z + b.z) / 2));
        }
      }

      // The pointer joins the web: lines from the cursor to whatever is near it.
      if (mouse.on) {
        for (const p of particles) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const d2 = dx * dx + dy * dy;
          if (d2 >= LINK2) continue;
          addLink(mouse.x, mouse.y, p.x, p.y, (1 - Math.sqrt(d2) / LINK) * 0.9);
        }
      }

      for (let i = 0; i < BUCKETS; i++) {
        ctx.strokeStyle = `rgba(${rgb},${(((i + 0.5) / BUCKETS) * MAX_LINK_ALPHA).toFixed(3)})`;
        ctx.stroke(buckets[i]);
      }

      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},${p.a})`;
        ctx.fill();
      }
    };

    // Pointer target (viewport/CSS px === canvas px, canvas is fixed full-page).
    const mouse = { x: 0, y: 0, on: false };
    const onMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.on = true;
    };
    const onLeave = () => {
      mouse.on = false;
    };
    // Touch gets the same interaction. Without this the field is inert on
    // phones, which is where a shared link is most often opened.
    const onTouch = (e: TouchEvent) => {
      const t = e.touches[0];
      if (!t) return;
      mouse.x = t.clientX;
      mouse.y = t.clientY;
      mouse.on = true;
    };

    // The field normally gathers in the lower half of the screen. When you reach
    // the very bottom of the landing page, i.e. the ARBOR wordmark scrolls into
    // view, the whole field migrates up, mirroring the same distribution into
    // the *upper* half instead, so it clears the footer/wordmark entirely. The
    // footer mounts alongside this background; resolve it lazily (canvas is fixed
    // & full-viewport, so viewport px === canvas px).
    let wordEl: HTMLElement | null = null;
    let raf = 0;
    const tick = () => {
      if (!wordEl) wordEl = document.querySelector<HTMLElement>("[data-wordmark]");
      // "At the bottom of the page" once the wordmark overlaps the viewport.
      let atBottom = false;
      if (wordEl) {
        const r = wordEl.getBoundingClientRect();
        atBottom = r.width > 0 && r.bottom > 0 && r.top < H;
      }
      for (const p of particles) {
        // Soft spring back to the resting spot. Horizontally it's always the
        // same; vertically the target flips to the mirrored upper-half position
        // at the bottom of the page, so the field glides from the lower half up
        // into the upper half (and back down when you scroll away).
        const targetY = atBottom ? p.restYUp : p.restY;
        p.vx += (p.restX - p.x) * 0.0009;
        p.vy += (targetY - p.y) * p.ky;
        // A little life so the field never looks frozen.
        p.vx += (Math.random() - 0.5) * 0.04;
        p.vy += (Math.random() - 0.5) * 0.04;
        // Push away from the pointer. Gentler than a plain repulse because the
        // cursor is now linked into the web: shoving hard would tear the very
        // lines it just drew.
        if (mouse.on) {
          const dx = p.x - mouse.x;
          const dy = p.y - mouse.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < R2 && d2 > 0) {
            const dist = Math.sqrt(d2);
            // Nearer dots shove more, so the parallax survives the interaction.
            const f = (1 - dist / R) * 2.2 * (0.6 + p.z * 0.6);
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

    // Debounced: a window drag fires resize continuously, and each one both
    // reallocates the field and repaints the canvas.
    let resizeTimer = 0;
    const onResize = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(reflow, 150);
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseout", onLeave, { passive: true });
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    window.addEventListener("touchend", onLeave, { passive: true });
    window.addEventListener("resize", onResize);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(resizeTimer);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseout", onLeave);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("touchmove", onTouch);
      window.removeEventListener("touchend", onLeave);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden className="absolute inset-0" />;
}
