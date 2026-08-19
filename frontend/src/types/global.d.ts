/**
 * `window.Arbor` — the public open/close API `public/embed.js` exposes once
 * loaded (see plugin_sdk/CLAUDE.md). The landing page loads that same script
 * in buttonless mode and calls `window.Arbor.open()` from its own Login/Get
 * Started/Sign in buttons instead of the script's floating launcher.
 */
export {};

declare global {
  interface Window {
    Arbor?: {
      open: () => void;
      close: () => void;
    };
  }
}
