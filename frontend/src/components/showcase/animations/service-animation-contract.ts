// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { ReactElement } from "react";

/**
 * Contract every bespoke per-service animation is built against. One
 * component per real service (not a shared taxonomy of reusable "kinds" —
 * that generic system was removed in favor of an animation authored
 * specifically for each service's actual description).
 */
export interface ServiceAnimationProps {
  /** Merged onto the root <svg>. Controls size; never hardcode dimensions
   *  inside an animation component. */
  className?: string;
  /** Accessible name. Omit for a purely decorative instance — the component
   *  must default to aria-hidden when this is absent. */
  title?: string;
}

export type ServiceAnimationComponent = (props: ServiceAnimationProps) => ReactElement;
