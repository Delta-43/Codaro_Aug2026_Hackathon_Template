// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Day/night switch, shared by the landing nav pill and the docs header.
 * Renders the neutral icon until mounted — `resolvedTheme` is unknown during
 * SSR, so painting a definite icon first would flash the wrong one.
 */
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      aria-label={isDark ? "Switch to day" : "Switch to night"}
      title={isDark ? "Day" : "Night"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "grid size-8 place-items-center rounded-full text-muted-foreground transition-all hover:bg-muted hover:text-foreground",
        buttonFx.icon,
        className,
      )}
    >
      {isDark ? <Moon className="size-4" aria-hidden /> : <Sun className="size-4" aria-hidden />}
    </button>
  );
}
