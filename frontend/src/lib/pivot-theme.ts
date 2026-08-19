/**
 * Applies `domain.config.json`'s `theme` block to the live stylesheet.
 *
 * `theme` is `{primaryColor, radius}` and was served from the very first config
 * version while the frontend read none of it — a pivot could set
 * `primaryColor: "#15803d"` and every button stayed the default pink. Both keys
 * map onto tokens `app/globals.css` already defines (`--primary`, `--radius`),
 * and every Tailwind utility in the app derives from those, so overriding the
 * two variables repaints the whole UI without touching a component.
 *
 * Written as an inline style on `:root`, which outranks the stylesheet's own
 * `:root` rule — including the `.dark` block, deliberately: a configured brand
 * colour is the brand in both themes.
 */

const PRIMARY = "--primary";
const PRIMARY_FG = "--primary-foreground";
const RADIUS = "--radius";

/** Relative luminance of a #rgb / #rrggbb colour, or null if it isn't one.
 *  Used only to decide whether text ON the brand colour should be white or
 *  near-black — a mid-green brand with white-on-white label is unreadable, and
 *  globals.css's `--primary-foreground` is tuned for the default pink. */
function hexLuminance(color: string): number | null {
  const hex = color.trim().replace(/^#/, "");
  const full =
    hex.length === 3
      ? hex
          .split("")
          .map((c) => c + c)
          .join("")
      : hex;
  if (!/^[0-9a-fA-F]{6}$/.test(full)) return null;
  const channel = (i: number) => {
    const v = parseInt(full.slice(i * 2, i * 2 + 2), 16) / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

export type PivotTheme = { primaryColor: string | null; radius: string | null };

/** Idempotent: re-applying the same theme is a no-op, and a null field CLEARS
 *  the override rather than leaving the previous pivot's colour behind (which is
 *  what a reload after editing the config back to no-theme must do). */
export function applyPivotTheme(theme: PivotTheme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  if (theme.primaryColor) {
    root.style.setProperty(PRIMARY, theme.primaryColor);
    // Only override the foreground for a colour we can actually measure. A
    // non-hex value (oklch(), a var()) keeps the stylesheet's own pairing.
    const lum = hexLuminance(theme.primaryColor);
    if (lum !== null) root.style.setProperty(PRIMARY_FG, lum > 0.5 ? "#0a0a0a" : "#ffffff");
    else root.style.removeProperty(PRIMARY_FG);
  } else {
    root.style.removeProperty(PRIMARY);
    root.style.removeProperty(PRIMARY_FG);
  }

  if (theme.radius) root.style.setProperty(RADIUS, theme.radius);
  else root.style.removeProperty(RADIUS);
}
