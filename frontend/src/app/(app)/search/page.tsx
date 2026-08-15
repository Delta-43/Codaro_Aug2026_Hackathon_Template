"use client";

// Tab 1 — Search. Full discovery UI (query, categories, code entry, mock QR,
// follow) lands in Phase 3. Phase 2 stub: navigable, vertical-aware.
import { useVertical } from "@/context/app-context";

export default function SearchPage() {
  const vertical = useVertical();
  return (
    <section className="py-6">
      <h1 className="text-xl font-semibold tracking-tight md:sr-only">Search</h1>
      <p className="mt-1 text-sm text-muted-foreground">{vertical.searchPlaceholder}</p>
      <p className="mt-6 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Discovery UI — query, categories, code entry, and the demo QR scanner —
        arrives in Phase 3.
      </p>
    </section>
  );
}
