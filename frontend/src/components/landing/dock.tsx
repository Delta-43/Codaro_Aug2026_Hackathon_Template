"use client";

/**
 * macOS-dock-style magnification. `Dock` tracks the cursor and each `DockItem`
 * scales by how close the cursor is to its centre, so the hovered icon grows
 * most and its neighbours grow a little — the Finder dock effect.
 *
 * Performance: the cursor fires `pointermove` dozens of times a second. Driving
 * that through React state (one `setState` on the Dock + one `setState` per item
 * per move) meant several re-renders and layout reads *per event*, which is what
 * made the icons feel laggy/janky on hover. Instead the Dock coalesces moves
 * into a single `requestAnimationFrame` and notifies items through a ref-based
 * subscription; each item writes its own `transform` directly to the DOM. No
 * React re-render happens on move, so the magnify tracks the cursor smoothly.
 *
 * Falls back to no scaling for touch (synthetic pointer events with no reliable
 * "leave" left icons stuck enlarged) and keyboard/reduced-motion audiences.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

type DockPos = { x: number; y: number } | null;
type Subscriber = (pos: DockPos) => void;
type DockApi = { subscribe: (fn: Subscriber) => () => void };

const DockContext = createContext<DockApi | null>(null);

export function Dock({ children, className }: { children: ReactNode; className?: string }) {
  const subs = useRef<Set<Subscriber>>(new Set());
  const latest = useRef<DockPos>(null);
  const frame = useRef<number | null>(null);

  const api = useMemo<DockApi>(
    () => ({
      subscribe(fn) {
        subs.current.add(fn);
        fn(latest.current);
        return () => {
          subs.current.delete(fn);
        };
      },
    }),
    [],
  );

  useEffect(() => {
    const pending = frame;
    return () => {
      if (pending.current != null) cancelAnimationFrame(pending.current);
    };
  }, []);

  function schedule(pos: DockPos) {
    latest.current = pos;
    if (frame.current != null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      for (const fn of subs.current) fn(latest.current);
    });
  }

  return (
    <div
      className={className}
      // Only a real mouse drives the magnify; touch has no reliable "leave".
      onPointerMove={(e) => schedule(e.pointerType === "mouse" ? { x: e.clientX, y: e.clientY } : null)}
      onPointerLeave={() => schedule(null)}
      onPointerCancel={() => schedule(null)}
    >
      <DockContext.Provider value={api}>{children}</DockContext.Provider>
    </div>
  );
}

export function DockItem({
  children,
  className,
  maxScale = 1.6,
  radius = 140,
}: {
  children: ReactNode;
  className?: string;
  maxScale?: number;
  radius?: number;
}) {
  const api = useContext(DockContext);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!api || !el) return;
    return api.subscribe((pos) => {
      let scale = 1;
      if (pos) {
        const rect = el.getBoundingClientRect();
        // 2D distance so the effect stays local whether the icons sit in a row
        // (desktop) or stack into a column (narrow screens).
        const dx = pos.x - (rect.left + rect.width / 2);
        const dy = pos.y - (rect.top + rect.height / 2);
        const dist = Math.hypot(dx, dy);
        if (dist < radius) scale = 1 + (maxScale - 1) * (1 - dist / radius);
      }
      el.style.transform = `scale(${scale})`;
    });
  }, [api, maxScale, radius]);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        transform: "scale(1)",
        transformOrigin: "bottom center",
        transition: "transform 120ms ease-out, background-color 150ms ease-out, color 150ms ease-out",
      }}
    >
      {children}
    </div>
  );
}
