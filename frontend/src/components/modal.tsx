// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Lightweight modal: bottom sheet on mobile, centred dialog on desktop.
 * Escape and overlay-click close it; focus moves into the panel on open and
 * body scroll is locked. A drop-in target for shadcn `Dialog` later — callers
 * only depend on `open`/`onClose`.
 */
import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function Modal({
  open,
  onClose,
  title,
  className,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "relative z-10 max-h-[88dvh] w-full overflow-y-auto border border-border bg-card shadow-xl outline-none",
          "rounded-t-2xl pb-[max(1rem,env(safe-area-inset-bottom))] md:max-w-md md:rounded-2xl md:pb-4",
          className,
        )}
      >
        {title ? (
          <div className="sticky top-0 flex items-center justify-between border-b border-border bg-card/95 px-4 py-3 backdrop-blur">
            <h2 className="text-sm font-semibold">{title}</h2>
            <button
              onClick={onClose}
              aria-label="Close"
              className={cn(
                "flex size-8 items-center justify-center rounded-full text-muted-foreground transition-all hover:bg-muted hover:text-foreground",
                buttonFx.press,
              )}
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ) : null}
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
