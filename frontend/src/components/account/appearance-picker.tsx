// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Compact appearance control for the Account header — a small, icon-only 3-way
 * segmented toggle (Light · Dark · Smart) with an "Appearance" caption above.
 *
 * Named apart from `components/theme-toggle.tsx`, which is a different control
 * (a 2-state icon button for the landing nav and docs shell). Both used to
 * export `ThemeToggle`, so which one a file got depended purely on its import
 * path.
 * "Smart" maps to next-themes' built-in "system" theme, which follows the OS
 * (macOS / iOS / Android) light-or-dark preference live. Default is Light on
 * first load; the choice is persisted by next-themes (localStorage).
 */
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

type Option = { value: string; label: string; icon: LucideIcon };

const OPTIONS: Option[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Smart", icon: Monitor },
];

export function AppearancePicker() {
  const { theme, setTheme } = useTheme();

  // next-themes can't know the persisted theme until it mounts on the client, so
  // reflect the selection only after mount to avoid a hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="flex shrink-0 items-center gap-0.5 rounded-lg bg-muted p-0.5"
    >
        {OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const selected = mounted && theme === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={opt.label}
              title={opt.label}
              onClick={() => setTheme(opt.value)}
              className={cn(
                "grid size-7 place-items-center rounded-md transition-all",
                buttonFx.press,
                selected
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-primary",
              )}
            >
              <Icon className="size-3.5" aria-hidden />
            </button>
          );
        })}
    </div>
  );
}
