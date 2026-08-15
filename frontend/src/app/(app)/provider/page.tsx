"use client";

// Tab 2 — Provider profile. Operates only on the locked-in provider; with none
// locked in it renders a purposeful empty state (never blank). Full profile +
// services + resource picker land in Phase 4.
import { Store } from "lucide-react";
import { useApp } from "@/context/app-context";
import { EmptyState } from "@/components/empty-state";

export default function ProviderPage() {
  const { activeProvider, vertical } = useApp();

  if (!activeProvider) {
    return (
      <EmptyState
        icon={<Store className="size-8" aria-hidden />}
        title={vertical.copy.noProviderTitle}
        body={vertical.copy.noProviderBody}
        actionHref="/search"
        actionLabel="Go to Search"
      />
    );
  }

  return (
    <section className="py-6">
      <h1 className="text-xl font-semibold tracking-tight">{activeProvider.name}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{activeProvider.tagline}</p>
      <p className="mt-6 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Full profile, {vertical.serviceNounPlural.toLowerCase()}, and the resource
        picker arrive in Phase 4.
      </p>
    </section>
  );
}
