"use client";

/**
 * Tab 1 — Search. Three ways to lock in a provider: text/category/location
 * search, a provider code, and a demo QR scan. Followed providers pin to the
 * top. Tapping a result opens a preview (Follow / Open); Open moves to Tab 2.
 */
import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  MapPin,
  QrCode,
  Search as SearchIcon,
  Star,
  Tag,
} from "lucide-react";
import type { Provider } from "@/types/domain";
import { searchProviders } from "@/api";
import { useApp, useVertical } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ProviderCard } from "@/components/search/provider-card";
import { ProviderPreview } from "@/components/search/provider-preview";
import { CodeModal } from "@/components/search/code-modal";
import { distanceKm, REFERENCE_LOCATION } from "@/lib/geo";
import { cn } from "@/lib/utils";

const INPUT =
  "h-11 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

/** How the result list is ordered. Applied client-side so re-sorting is instant
 *  (no refetch) — and distance can only be ranked here anyway, since the backend
 *  has no viewer coordinates. Followed providers still pin to the top first. */
type OrderKey = "rating" | "distance" | "price";
type SortDir = "asc" | "desc";

/** Each order key maps a provider to one sortable number and declares the
 *  direction that reads as "best" (rating high-first, distance/price low-first).
 *  `value` returns null when the provider has no data for that key — those always
 *  sink to the bottom, whichever direction is active. */
const ORDER_META: Record<
  OrderKey,
  {
    label: string;
    icon: typeof Star;
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

const ORDER_KEYS = Object.keys(ORDER_META) as OrderKey[];

export default function SearchPage() {
  const vertical = useVertical();
  const { user } = useApp();

  const [text, setText] = useState("");
  const [near, setNear] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [orderBy, setOrderBy] = useState<OrderKey>("rating");
  const [dir, setDir] = useState<SortDir>(ORDER_META.rating.defaultDir);
  const [codeOpen, setCodeOpen] = useState(false);
  const [preview, setPreview] = useState<Provider | null>(null);

  const debText = useDebouncedValue(text, 250);
  const debNear = useDebouncedValue(near, 250);
  const followedKey = (user?.followedProviderIds ?? []).join(",");

  const results = useAsync(
    () =>
      searchProviders({
        text: debText || undefined,
        categoryId: categoryId ?? undefined,
        near: debNear || undefined,
      }),
    [debText, debNear, categoryId, followedKey],
  );

  // QR targets come from an unfiltered fetch so the scanner always has codes.
  // Fetched once on mount — the demo targets don't depend on filters or follow
  // ordering, so there's no reason to refetch when those change.
  const allProviders = useAsync(() => searchProviders({}), []);
  const qrTargets = useMemo(() => (allProviders.data ?? []).slice(0, 3), [allProviders.data]);

  const followed = new Set(user?.followedProviderIds ?? []);

  // Order the results client-side: followed pinned to the top (unchanged), then
  // the chosen key/direction. Instant on toggle — no refetch, so these aren't
  // fetch deps. Providers with no value for the key always sink to the bottom.
  const providers = useMemo(() => {
    const list = results.data ?? [];
    const { value } = ORDER_META[orderBy];
    const sign = dir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      const fa = followed.has(a.id) ? 0 : 1;
      const fb = followed.has(b.id) ? 0 : 1;
      if (fa !== fb) return fa - fb;
      const va = value(a);
      const vb = value(b);
      if (va == null || vb == null) return (va == null ? 1 : 0) - (vb == null ? 1 : 0);
      return sign * (va - vb);
    });
    // followedKey stands in for the `followed` set (rebuilt each render).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results.data, orderBy, dir, followedKey]);

  // Clicking the active order toggles its direction; a different order switches
  // to it at its natural "best-first" direction.
  const pickOrder = (key: OrderKey) => {
    if (key === orderBy) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setOrderBy(key);
      setDir(ORDER_META[key].defaultDir);
    }
  };

  const hasFilters = text !== "" || near !== "" || categoryId !== null;
  const clearFilters = () => {
    setText("");
    setNear("");
    setCategoryId(null);
  };

  return (
    <section className="space-y-4 py-4">
      {/* Search bar */}
      <div className="space-y-2">
        <div className="relative">
          <SearchIcon
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={vertical.searchPlaceholder}
            aria-label={vertical.searchPlaceholder}
            className={cn(INPUT, "pr-[4.75rem]")}
          />
          <Button
            variant="ghost"
            size="sm"
            aria-label="Enter or scan a provider code"
            className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground"
            onPress={() => setCodeOpen(true)}
          >
            <QrCode className="size-4" aria-hidden />
            Code
          </Button>
        </div>
        <div className="relative">
          <MapPin
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={near}
            onChange={(e) => setNear(e.target.value)}
            placeholder="Location (city)"
            aria-label="Location"
            className={INPUT}
          />
        </div>
      </div>

      {/* Category chips — one horizontally-scrollable line (never wraps).
          Provider-code entry lives in the search-bar icon → dialog. */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
        <Chip active={categoryId === null} onClick={() => setCategoryId(null)}>
          All
        </Chip>
        {vertical.categories.map((c) => (
          <Chip
            key={c.id}
            active={categoryId === c.id}
            onClick={() => setCategoryId((prev) => (prev === c.id ? null : c.id))}
          >
            {c.label}
          </Chip>
        ))}
      </div>

      {/* Order by — its own row: a sort, distinct from the filter chips above. */}
      <div className="flex items-center gap-2">
        <span className="shrink-0 text-xs font-medium text-muted-foreground">Order by</span>
        <div
          role="radiogroup"
          aria-label="Order results by"
          className="inline-flex rounded-lg border border-border bg-card p-0.5"
        >
          {ORDER_KEYS.map((key) => {
            const { label, icon: Icon } = ORDER_META[key];
            const active = orderBy === key;
            const Arrow = dir === "asc" ? ArrowUp : ArrowDown;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={active}
                aria-label={
                  active ? `${label}, ${dir === "asc" ? "ascending" : "descending"}` : `Order by ${label}`
                }
                title={active ? "Tap to reverse order" : `Order by ${label}`}
                onClick={() => pickOrder(key)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-3.5" aria-hidden />
                {label}
                {active ? <Arrow className="size-3.5" aria-hidden /> : null}
              </button>
            );
          })}
        </div>
      </div>

      {/* Result count / clear — slim meta line above the list. */}
      {results.data && !results.error ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {providers.length} {providers.length === 1 ? "result" : "results"}
          </span>
          {hasFilters ? (
            <button
              type="button"
              onClick={clearFilters}
              className="font-medium text-primary hover:underline"
            >
              Clear
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Results */}
      <div className="space-y-2">
        {results.loading && !results.data ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3 rounded-xl border border-border p-3">
              <Skeleton className="size-12 shrink-0 rounded-full" />
              <div className="flex-1 space-y-2 py-1">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </div>
          ))
        ) : results.error ? (
          <EmptyState
            title="Couldn't load results"
            body="Something interrupted the search."
          >
            <Button className="mt-1" onPress={results.reload}>
              Try again
            </Button>
          </EmptyState>
        ) : providers.length === 0 ? (
          <EmptyState
            icon={<SearchIcon className="size-8" aria-hidden />}
            title="No matches"
            body="Try a different term, category, or location."
          />
        ) : (
          providers.map((p) => (
            <ProviderCard
              key={p.id}
              provider={p}
              isFollowed={followed.has(p.id)}
              onOpen={setPreview}
            />
          ))
        )}
      </div>

      <CodeModal
        open={codeOpen}
        onClose={() => setCodeOpen(false)}
        targets={qrTargets}
        onResolved={(p) => {
          setCodeOpen(false);
          setPreview(p);
        }}
      />
      <ProviderPreview
        provider={preview}
        open={preview !== null}
        onClose={() => setPreview(null)}
      />
    </section>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
