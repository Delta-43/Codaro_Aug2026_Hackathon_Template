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

const DockContext = createContext<number | null>(null);

export function Dock({ children, className }: { children: ReactNode; className?: string }) {
  const [mouseX, setMouseX] = useState<number | null>(null);
  return (
    <div
      className={className}
      onMouseMove={(e) => setMouseX(e.clientX)}
      onMouseLeave={() => setMouseX(null)}
    >
      <DockContext.Provider value={mouseX}>{children}</DockContext.Provider>
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
  const mouseX = useContext(DockContext);
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const el = ref.current;
    if (mouseX == null || !el) {
      setScale(1);
      return;
    }
    const rect = el.getBoundingClientRect();
    const center = rect.left + rect.width / 2;
    const dist = Math.abs(mouseX - center);
    setScale(dist >= radius ? 1 : 1 + (maxScale - 1) * (1 - dist / radius));
  }, [mouseX, maxScale, radius]);

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
