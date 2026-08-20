"use client";

/**
 * Tab 1 — Search. Three ways to lock in a provider: text/category/location
 * search, a provider code, and a demo QR scan. Followed providers pin to the
 * top. Tapping a result opens a preview (Follow / Open); Open moves to Tab 2.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { QrCode, Search as SearchIcon, SlidersHorizontal } from "lucide-react";
import type { Provider } from "@/types/domain";
import { DEFAULT_FACETS, getSearchFacets, searchProviders } from "@/api";
import { useApp, useVertical } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ProviderCard } from "@/components/search/provider-card";
import { ProviderPreview } from "@/components/search/provider-preview";
import { CodeModal } from "@/components/search/code-modal";
import { FilterSheet } from "@/components/search/filter-sheet";
import { distanceKm, geoOrigin } from "@/lib/geo";
import { ORDER_KEYS, ORDER_META, type OrderKey, type SortDir } from "@/lib/order-by";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";
import { SEARCH_INPUT } from "@/components/search/field-class";

export default function SearchPage() {
  const vertical = useVertical();
  // `ready` flips only after AppProvider has applied the pivot file's
  // location settings, so it is the signal that `geoOrigin()` is final.
  const { user, singleBusiness, ready } = useApp();
  const router = useRouter();

  // Provider discovery doesn't exist in single-business mode — the sole business
  // is implicit. Bounce any stray link/bookmark to the catalog.
  useEffect(() => {
    if (singleBusiness) router.replace("/provider");
  }, [singleBusiness, router]);

  const [text, setText] = useState("");
  const [near, setNear] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [orderBy, setOrderBy] = useState<OrderKey>("rating");
  const [dir, setDir] = useState<SortDir>(ORDER_META.rating.defaultDir);
  // Range filters (the Filter panel's sliders). null = "Any" (no ceiling);
  // minRating 0 = "Any". Applied client-side against the fetched results.
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [minRating, setMinRating] = useState(0);
  const [maxDist, setMaxDist] = useState<number | null>(null);
  const [codeOpen, setCodeOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
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

  // Which filter/sort dimensions this vertical supports — derived server-side
  // from the catalog (GET /config). A free niche → no price; a remote niche →
  // no distance. Defaults to all-on while loading. Sort keys share the facet
  // names, so a disabled facet drops its sort option too.
  const facetsQ = useAsync(() => getSearchFacets(), []);
  const facets = facetsQ.data ?? DEFAULT_FACETS;
  const enabledOrderKeys = useMemo(() => ORDER_KEYS.filter((k) => facets[k]), [facets]);

  // If the active sort key becomes unavailable (facets loaded/pivoted), fall
  // back to rating (always offered) so the list never sorts by a hidden key.
  useEffect(() => {
    if (!facets[orderBy]) {
      setOrderBy("rating");
      setDir(ORDER_META.rating.defaultDir);
    }
  }, [facets, orderBy]);

  // Slider ranges are derived from the unfiltered set so the bounds stay stable
  // as the active filters change. Price uses the cheapest-service price; distance
  // is measured from the reference location. A range is hidden when the data
  // gives it no span (e.g. every provider at the same price, or none priced).
  const bounds = useMemo(() => {
    const all = allProviders.data ?? [];
    const prices = all
      .map((p) => p.priceFromMinorUnits)
      .filter((v): v is number => v != null);
    const dists = all.map((p) => distanceKm(geoOrigin(), p.location));
    const priceLo = prices.length ? Math.min(...prices) : 0;
    const priceHi = prices.length ? Math.max(...prices) : 0;
    return {
      priceLo,
      priceHi,
      priceCurrency: all.find((p) => p.priceFromMinorUnits != null)?.currency || "EUR",
      hasPrice: priceHi > priceLo,
      distHi: dists.length ? Math.max(1, Math.ceil(Math.max(...dists))) : 0,
      hasDistance: dists.length > 0 && Math.max(...dists) > 0,
    };
    // `ready` is a dependency because `geoOrigin()` is module state with no React
    // subscription: without it these bounds keep the pre-boot fallback origin for
    // the life of the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allProviders.data, ready]);

  const followed = new Set(user?.followedProviderIds ?? []);

  // Filter (range sliders) then order the results client-side. Followed pinned to
  // the top (unchanged), then the chosen key/direction; providers with no value
  // for the sort key sink to the bottom. Instant — no refetch on filter/sort.
  const providers = useMemo(() => {
    const { value } = ORDER_META[orderBy];
    const sign = dir === "asc" ? 1 : -1;
    const list = (results.data ?? []).filter((p) => {
      if (minRating > 0 && p.rating < minRating) return false;
      if (maxPrice != null && (p.priceFromMinorUnits == null || p.priceFromMinorUnits > maxPrice))
        return false;
      if (maxDist != null && distanceKm(geoOrigin(), p.location) > maxDist) return false;
      return true;
    });
    return list.sort((a, b) => {
      const fa = followed.has(a.id) ? 0 : 1;
      const fb = followed.has(b.id) ? 0 : 1;
      if (fa !== fb) return fa - fb;
      const va = value(a);
      const vb = value(b);
      if (va == null || vb == null) return (va == null ? 1 : 0) - (vb == null ? 1 : 0);
      return sign * (va - vb);
    });
    // followedKey stands in for the `followed` set (rebuilt each render).
    // `ready` for the same reason as `bounds`: the maxDist filter calls
    // geoOrigin(), which is not reactive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results.data, orderBy, dir, followedKey, minRating, maxPrice, maxDist, ready]);

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

  const rangeActive = maxPrice !== null || minRating > 0 || maxDist !== null;
  const hasFilters = text !== "" || near !== "" || categoryId !== null || rangeActive;
  const clearFilters = () => {
    setText("");
    setNear("");
    setCategoryId(null);
    setMaxPrice(null);
    setMinRating(0);
    setMaxDist(null);
  };

  // Badge on the Filter button counts the panel's active filters (location +
  // the three range sliders) — category is a visible inline chip, not counted.
  const activeFilterCount =
    (near !== "" ? 1 : 0) +
    (maxPrice !== null ? 1 : 0) +
    (minRating > 0 ? 1 : 0) +
    (maxDist !== null ? 1 : 0);

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
            className={cn(SEARCH_INPUT, "pr-[4.75rem]")}
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
      </div>

      {/* Filters line: Filter button (opens the panel — location + sort) followed
          by the category quick-filters. Provider-code entry lives in the
          search-bar icon → dialog. */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setFiltersOpen(true)}
          aria-label="Filters"
          className={cn(
            "inline-flex shrink-0 items-center gap-2 rounded-full border border-border bg-card px-4 py-1.5 text-sm font-semibold text-foreground shadow-sm transition-all hover:bg-muted",
            buttonFx.press,
          )}
        >
          <SlidersHorizontal className="size-4" aria-hidden />
          Filter
          {activeFilterCount > 0 ? (
            <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
              {activeFilterCount}
            </span>
          ) : null}
        </button>
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto no-scrollbar">
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
              className={cn("font-medium text-primary hover:underline", buttonFx.link)}
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
              showPrice={facets.price}
              showDistance={facets.distance}
            />
          ))
        )}
      </div>

      <FilterSheet
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        near={near}
        onNearChange={setNear}
        showLocation={facets.distance}
        maxPrice={maxPrice}
        onMaxPriceChange={setMaxPrice}
        priceLo={bounds.priceLo}
        priceHi={bounds.priceHi}
        priceCurrency={bounds.priceCurrency}
        showPrice={facets.price && bounds.hasPrice}
        minRating={minRating}
        onMinRatingChange={setMinRating}
        maxDist={maxDist}
        onMaxDistChange={setMaxDist}
        distHi={bounds.distHi}
        showDistance={facets.distance && bounds.hasDistance}
        orderKeys={enabledOrderKeys}
        orderBy={orderBy}
        dir={dir}
        onPickOrder={pickOrder}
        onClearAll={clearFilters}
        resultCount={providers.length}
      />
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
        "shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition-all",
        buttonFx.press,
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
