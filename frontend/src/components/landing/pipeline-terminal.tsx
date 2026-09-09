// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * A stylized terminal showing the engine's booking pipeline (request → owner
 * approval → confirmed), not a generic dev-tool prop, inspired by
 * dannypostma.com's landing page. Frosted-glass surface. Entrance is staggered
 * via tw-animate-css's `animate-in` utilities (Tailwind v4 auto-generates them
 * from the `--animate-*` theme keys in globals.css), no custom keyframes or
 * client JS needed.
 */
const STEPS = [
  { cmd: "POST /bookings", result: "pending: rules resolved per service" },
  { cmd: "owner approves", result: "slot held, capacity decremented" },
  { cmd: "GET /availability", result: "confirmed, same spine, any vertical" },
];

export function PipelineTerminal() {
  return (
    <div className="w-full max-w-md rounded-2xl border border-background/10 bg-foreground/85 p-5 text-left font-mono text-sm shadow-sm backdrop-blur-xl">
      {/* macOS traffic-light window buttons (their literal colours, no token
          exists for these, so hex is intentional here). Interactive: they
          magnify on hover like the page's other icons. */}
      <div className="mb-3 flex gap-2" aria-hidden>
        <span className="size-3 origin-center cursor-pointer rounded-full bg-[#ff5f56] transition-transform duration-200 ease-out hover:scale-150" />
        <span className="size-3 origin-center cursor-pointer rounded-full bg-[#febc2e] transition-transform duration-200 ease-out hover:scale-150" />
        <span className="size-3 origin-center cursor-pointer rounded-full bg-[#28c840] transition-transform duration-200 ease-out hover:scale-150" />
      </div>
      {STEPS.map((step, i) => (
        <div
          key={step.cmd}
          className="animate-in fade-in slide-in-from-bottom-2 fill-mode-both mb-2.5 last:mb-0"
          style={{ animationDelay: `${i * 400}ms`, animationDuration: "500ms" }}
        >
          <p className="text-background/60">
            <span className="text-primary">{">"}</span> {step.cmd}
          </p>
          <p className="text-background">
            <span className="text-primary">{"✓"}</span> {step.result}
          </p>
        </div>
      ))}
      <span
        className="animate-in fade-in fill-mode-both inline-block"
        style={{ animationDelay: `${STEPS.length * 400}ms` }}
      >
        <span className="animate-caret-blink text-primary">{"_"}</span>
      </span>
    </div>
  );
}
