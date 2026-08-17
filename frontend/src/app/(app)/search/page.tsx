"use client";

/**
 * Tab 1 — Search. Three ways to lock in a provider: text/category/location
 * search, a provider code, and a demo QR scan. Followed providers pin to the
 * top. Tapping a result opens a preview (Follow / Open); Open moves to Tab 2.
 */
import { useMemo, useState } from "react";
import { MapPin, QrCode, Search as SearchIcon } from "lucide-react";
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
import { QrScannerModal } from "@/components/search/qr-scanner-modal";
import { CodeEntry } from "@/components/search/code-entry";
import { cn } from "@/lib/utils";

const INPUT =
  "h-11 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

export default function SearchPage() {
  const vertical = useVertical();
  const { user } = useApp();

  const [text, setText] = useState("");
  const [near, setNear] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
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
  const providers = results.data ?? [];

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
            className={cn(INPUT, "pr-12")}
          />
          <Button
            variant="ghost"
            size="icon"
            aria-label="Scan a provider code"
            className="absolute right-1 top-1/2 -translate-y-1/2"
            onPress={() => setQrOpen(true)}
          >
            <QrCode className="size-5" aria-hidden />
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

      {/* Category chips */}
      <div className="flex flex-wrap gap-2">
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

      {/* Code entry affordance */}
      <div>
        {showCode ? (
          <CodeEntry
            onResolved={(p) => {
              setShowCode(false);
              setPreview(p);
            }}
          />
        ) : (
          <button
            type="button"
            onClick={() => setShowCode(true)}
            className="text-sm font-medium text-primary hover:underline"
          >
            Have a provider code?
          </button>
        )}
      </div>

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

      <QrScannerModal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        targets={qrTargets}
        onResolved={(p) => {
          setQrOpen(false);
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
        "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
