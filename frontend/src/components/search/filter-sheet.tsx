"use client";

/**
 * "Filters" panel — opened by the Filter button in the search toolbar. Holds the
 * controls kept off the main surface: location (city), the range sliders (max
 * price, minimum rating, max distance), and sort order. Category stays a visible
 * inline quick-filter, so it isn't repeated here. Binds directly to the search
 * page's state, so changes apply live (results refilter/re-sort behind the
 * sheet); "Show results" just closes it.
 */
import { Check, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/modal";
import { formatMoney } from "@/lib/format";
import { DIR_ICON, ORDER_META, type OrderKey, type SortDir } from "@/lib/order-by";
import { cn } from "@/lib/utils";

const INPUT =
  "h-11 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

export function FilterSheet({
  open,
  onClose,
  near,
  onNearChange,
  showLocation,
  maxPrice,
  onMaxPriceChange,
  priceLo,
  priceHi,
  priceCurrency,
  showPrice,
  minRating,
  onMinRatingChange,
  maxDist,
  onMaxDistChange,
  distHi,
  showDistance,
  orderKeys,
  orderBy,
  dir,
  onPickOrder,
  onClearAll,
  resultCount,
}: {
  open: boolean;
  onClose: () => void;
  near: string;
  onNearChange: (value: string) => void;
  showLocation: boolean;
  maxPrice: number | null;
  onMaxPriceChange: (value: number | null) => void;
  priceLo: number;
  priceHi: number;
  priceCurrency: string;
  showPrice: boolean;
  minRating: number;
  onMinRatingChange: (value: number) => void;
  maxDist: number | null;
  onMaxDistChange: (value: number | null) => void;
  distHi: number;
  showDistance: boolean;
  orderKeys: OrderKey[];
  orderBy: OrderKey;
  dir: SortDir;
  onPickOrder: (key: OrderKey) => void;
  onClearAll: () => void;
  resultCount: number;
}) {
  const Arrow = DIR_ICON[dir];

  return (
    <Modal open={open} onClose={onClose} title="Filters">
      {/* Location — only for verticals with a physical place. */}
      {showLocation ? (
        <>
          <label htmlFor="filter-location" className="mb-1.5 block text-sm font-medium">
            Location
          </label>
          <div className="relative">
            <MapPin
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              id="filter-location"
              value={near}
              onChange={(e) => onNearChange(e.target.value)}
              placeholder="Any city"
              className={INPUT}
            />
          </div>
        </>
      ) : null}

      {/* Range sliders (cursors) */}
      {showPrice ? (
        <SliderRow
          label="Max price"
          readout={maxPrice == null ? "Any" : `Up to ${formatMoney(maxPrice, priceCurrency)}`}
          min={priceLo}
          max={priceHi}
          step={100}
          value={maxPrice ?? priceHi}
          onChange={(v) => onMaxPriceChange(v >= priceHi ? null : v)}
        />
      ) : null}

      <SliderRow
        label="Minimum rating"
        readout={minRating === 0 ? "Any" : `${minRating.toFixed(1)}★ & up`}
        min={0}
        max={5}
        step={0.5}
        value={minRating}
        onChange={onMinRatingChange}
      />

      {showDistance ? (
        <SliderRow
          label="Max distance"
          readout={maxDist == null ? "Any" : `Within ${maxDist} km`}
          min={0}
          max={distHi}
          step={1}
          value={maxDist ?? distHi}
          onChange={(v) => onMaxDistChange(v >= distHi ? null : v)}
        />
      ) : null}

      {/* Sort — a vertical, scrollable list of options (not horizontal pills).
          Hidden when the vertical's facets leave only one dimension. */}
      {orderKeys.length > 1 ? (
        <>
          <p className="mb-2 mt-6 text-sm font-medium">Sort by</p>
          <div
            role="radiogroup"
            aria-label="Order results by"
            className="max-h-56 divide-y divide-border overflow-y-auto rounded-lg border border-border"
          >
            {orderKeys.map((key) => {
              const { label, icon: Icon } = ORDER_META[key];
              const active = orderBy === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  aria-label={
                    active
                      ? `${label}, ${dir === "asc" ? "ascending" : "descending"}`
                      : `Sort by ${label}`
                  }
                  title={active ? "Tap to reverse order" : `Sort by ${label}`}
                  onClick={() => onPickOrder(key)}
                  className={cn(
                    "flex w-full items-center gap-3 px-3 py-3 text-left text-sm font-medium transition-colors",
                    active ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  <Icon className="size-4 shrink-0" aria-hidden />
                  <span className="flex-1">{label}</span>
                  {active ? (
                    <span className="inline-flex items-center gap-1 text-primary">
                      <Arrow className="size-4" aria-hidden />
                      <Check className="size-4" aria-hidden />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </>
      ) : null}

      {/* Actions */}
      <div className="mt-6 flex gap-2">
        <Button variant="outline" className="flex-1" onPress={onClearAll}>
          Clear all
        </Button>
        <Button className="flex-1" onPress={onClose}>
          Show {resultCount} {resultCount === 1 ? "result" : "results"}
        </Button>
      </div>
    </Modal>
  );
}

/** A labelled native range slider (the "cursor"), with a live value readout. */
function SliderRow({
  label,
  readout,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  readout: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="mt-4">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{readout}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-full cursor-pointer accent-primary"
      />
    </div>
  );
}
