"use client";

/**
 * Compact appearance control for the Account header — a small, icon-only 3-way
 * segmented toggle (Light · Dark · Smart) with an "Appearance" caption above.
 * "Smart" maps to next-themes' built-in "system" theme, which follows the OS
 * (macOS / iOS / Android) light-or-dark preference live. Default is Light on
 * first load; the choice is persisted by next-themes (localStorage).
 */
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Option = { value: string; label: string; icon: LucideIcon };

const OPTIONS: Option[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Smart", icon: Monitor },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  // next-themes can't know the persisted theme until it mounts on the client, so
  // reflect the selection only after mount to avoid a hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Appearance
      </span>
      <div
        role="radiogroup"
        aria-label="Theme"
        className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5"
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
                "grid size-7 place-items-center rounded-md transition-colors",
                selected
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-3.5" aria-hidden />
            </button>
          );
        })}
      </div>
    </div>
  );
}
