/**
 * Result ordering shared between the search page (which sorts the list) and the
 * Filter panel (which renders the picker). Each key maps a provider to one
 * sortable number and declares the direction that reads as "best" (rating
 * high-first, distance/price low-first). `value` returns null when the provider
 * has no data for that key — those always sink to the bottom, either direction.
 */
import { ArrowDown, ArrowUp, MapPin, Star, Tag, type LucideIcon } from "lucide-react";
import type { Provider } from "@/types/domain";
import { distanceKm, REFERENCE_LOCATION } from "@/lib/geo";

export type OrderKey = "rating" | "distance" | "price";
export type SortDir = "asc" | "desc";

export const ORDER_META: Record<
  OrderKey,
  {
    label: string;
    icon: LucideIcon;
    defaultDir: SortDir;
    value: (p: Provider) => number | null;
  }
> = {
  rating: {
    label: "Rating",
    icon: Star,
    defaultDir: "desc",
    // Fold reviewCount in as a fractional tiebreak so more-reviewed wins ties.
    value: (p) => p.rating + p.reviewCount / 1e6,
  },
  distance: {
    label: "Distance",
    icon: MapPin,
    defaultDir: "asc",
    value: (p) => distanceKm(REFERENCE_LOCATION, p.location),
  },
  price: {
    label: "Price",
    icon: Tag,
    defaultDir: "asc",
    value: (p) => p.priceFromMinorUnits,
  },
};

export const ORDER_KEYS = Object.keys(ORDER_META) as OrderKey[];

export const DIR_ICON: Record<SortDir, LucideIcon> = { asc: ArrowUp, desc: ArrowDown };
