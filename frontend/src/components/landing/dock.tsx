"use client";

/**
 * macOS-dock-style magnification. `Dock` tracks the cursor's X position; each
 * `DockItem` scales by how close the cursor is to its centre, so the hovered
 * icon grows most and its neighbours grow a little — the Finder dock effect.
 * Falls back to no scaling with a keyboard/reduced-motion audience (scale only
 * responds to pointer movement, and transitions are short).
 */
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

type DockPos = { x: number; y: number };
const DockContext = createContext<DockPos | null>(null);

export function Dock({ children, className }: { children: ReactNode; className?: string }) {
  const [pos, setPos] = useState<DockPos | null>(null);
  return (
    <div
      className={className}
      // Only a real mouse drives the magnify. Touch synthesises pointer events
      // with no reliable "leave", which left the icons stuck enlarged/misaligned
      // on mobile — so ignore non-mouse pointers and keep them at rest.
      onPointerMove={(e) => setPos(e.pointerType === "mouse" ? { x: e.clientX, y: e.clientY } : null)}
      onPointerLeave={() => setPos(null)}
      onPointerCancel={() => setPos(null)}
    >
      <DockContext.Provider value={pos}>{children}</DockContext.Provider>
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
  const pos = useContext(DockContext);
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const el = ref.current;
    if (!pos || !el) {
      setScale(1);
      return;
    }
    const rect = el.getBoundingClientRect();
    // 2D distance so the effect stays local whether the icons sit in a row
    // (desktop) or stack into a column (narrow screens) — otherwise a shared X
    // made every icon in a column respond to any one being hovered.
    const dx = pos.x - (rect.left + rect.width / 2);
    const dy = pos.y - (rect.top + rect.height / 2);
    const dist = Math.hypot(dx, dy);
    setScale(dist >= radius ? 1 : 1 + (maxScale - 1) * (1 - dist / radius));
  }, [pos, maxScale, radius]);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        transform: `scale(${scale})`,
        transformOrigin: "bottom center",
        transition: "transform 120ms ease-out, background-color 150ms ease-out, color 150ms ease-out",
      }}
    >
      {children}
    </div>
  );
}
