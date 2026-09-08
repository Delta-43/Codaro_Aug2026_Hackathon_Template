// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import snapshot from "@/showcase-catalogue.generated.json";
import type { Provider, Service } from "@/types/domain";

/**
 * What `/showcase` actually renders, which is far less than the API returns.
 *
 * Derived with `Pick` from the real types rather than declared independently:
 * if `Service.description` is ever renamed, this stops compiling instead of
 * silently rendering blanks. Live rows satisfy these structurally, so the same
 * components take API data and snapshot data without a cast.
 */
export type ShowcaseService = Pick<
  Service,
  | "id"
  | "providerId"
  | "name"
  | "description"
  // `formatOffer` reads these four to render the price line.
  | "priceMinorUnits"
  | "currency"
  | "pricingModel"
  | "rateUnit"
>;
export type ShowcaseProvider = Pick<Provider, "id" | "name">;

/**
 * The catalogue as it stood when `scripts/gen_showcase_snapshot.py` last ran.
 * Used only in `SHOWCASE_ONLY` builds; regenerate it if the seed data changes.
 */
export const CATALOGUE: {
  services: ShowcaseService[];
  providers: ShowcaseProvider[];
} = snapshot;
