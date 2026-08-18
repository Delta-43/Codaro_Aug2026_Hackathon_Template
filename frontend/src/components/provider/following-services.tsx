"use client";

/**
 * The customer's Services tab in the marketplace: the businesses they follow,
 * front and centre. A strip of the top 3 followed businesses sits at the top
 * (the currently-viewed one wears a pink aura halo); below it, a quick view of
 * that business — its profile with the bio clamped. From here a small back-stack
 * opens deeper views without leaving the tab:
 *   home  ──Show full bio──▶  full bio (back → home)
 *   home  ──View more──▶  all following  ──tap──▶  full bio (back → all → home)
 * Selecting a different slice swaps the quick view; the strip stays put.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Star } from "lucide-react";
import type { Provider } from "@/types/domain";
import { searchProviders } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { AvatarImg } from "@/components/avatar-img";
import { Skeleton } from "@/components/skeleton";
import { ProviderCard } from "@/components/search/provider-card";
import { ProviderProfile } from "@/components/provider/provider-profile";
import { cn } from "@/lib/utils";

type View = { kind: "home" } | { kind: "fullbio"; id: string } | { kind: "all" };

export function FollowingServices({ followedIds }: { followedIds: string[] }) {
  const { activeProvider, lockInProvider } = useApp();

  // The full Provider objects for the followed ids, in follow order. `searchProviders`
  // returns the catalog followed-first; we index by id and read back in the order
  // the user actually followed so the strip is stable.
  const all = useAsync<Provider[]>(() => searchProviders({}), []);
  const byId = useMemo(() => {
    const m = new Map<string, Provider>();
    (all.data ?? []).forEach((p) => m.set(p.id, p));
    return m;
  }, [all.data]);
  const followed = useMemo(
    () => followedIds.map((id) => byId.get(id)).filter((p): p is Provider => !!p),
    [followedIds, byId],
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stack, setStack] = useState<View[]>([{ kind: "home" }]);
  const view = stack[stack.length - 1];

  // Seed the viewer once the follow list resolves: prefer an already locked-in
  // followed business, else the first one. Guarded so it runs a single time.
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current || followed.length === 0) return;
    didInit.current = true;
    const seed = followed.find((f) => f.id === activeProvider?.id) ?? followed[0];
    setSelectedId(seed.id);
    lockInProvider(seed);
  }, [followed, activeProvider?.id, lockInProvider]);

  const push = (v: View) => setStack((s) => [...s, v]);
  const back = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));

  function selectSlice(p: Provider) {
    setSelectedId(p.id);
    lockInProvider(p);
  }

  if (all.loading && !all.data) {
    return (
      <div className="space-y-3 py-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const selected = (selectedId && byId.get(selectedId)) || followed[0] || null;
  const top3 = followed.slice(0, 3);

  // --- deeper views (share the back header) ---
  if (view.kind === "fullbio") {
    const p = byId.get(view.id);
    return (
      <div className="py-2">
        <BackHeader onBack={back} label="Back" />
        {p ? <ProviderProfile provider={p} clampBio={false} /> : null}
      </div>
    );
  }

  if (view.kind === "all") {
    return (
      <div className="space-y-3 py-2">
        <BackHeader onBack={back} label="Top followed" />
        <h1 className="text-lg font-semibold tracking-tight">All following</h1>
        <div className="space-y-2">
          {followed.map((p) => (
            <ProviderCard
              key={p.id}
              provider={p}
              isFollowed
              onOpen={(prov) => push({ kind: "fullbio", id: prov.id })}
            />
          ))}
        </div>
      </div>
    );
  }

  // --- home: top-3 strip + quick view ---
  return (
    <div className="space-y-4 py-4">
      <div className="space-y-2">
        <h2 className="text-sm font-semibold tracking-tight">Following</h2>
        {top3.map((p, i) => (
          <Slice
            key={p.id}
            provider={p}
            highlighted={selected?.id === p.id}
            leader={i === 0}
            onSelect={() => selectSlice(p)}
          />
        ))}
        {followed.length > 3 ? (
          <button
            type="button"
            onClick={() => push({ kind: "all" })}
            className="w-full rounded-xl border border-dashed border-border py-2 text-sm font-medium text-primary hover:bg-muted/50"
          >
            Show all businesses I&apos;m following ({followed.length})
          </button>
        ) : null}
      </div>

      {selected ? (
        <div className="border-t border-border pt-2">
          <ProviderProfile
            provider={selected}
            clampBio
            onShowFullBio={() => push({ kind: "fullbio", id: selected.id })}
          />
        </div>
      ) : null}
    </div>
  );
}

function BackHeader({ onBack, label }: { onBack: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden /> {label}
    </button>
  );
}

/** A full-width followed-business slice. The viewed one wears a pink aura halo. */
function Slice({
  provider: p,
  highlighted,
  leader,
  onSelect,
}: {
  provider: Provider;
  highlighted: boolean;
  leader: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={highlighted}
      className={cn(
        "flex w-full items-center gap-3 rounded-2xl border bg-card p-3 text-left transition-all",
        highlighted
          ? "border-pink-400/70 shadow-lg shadow-pink-500/20 ring-2 ring-pink-400/60"
          : "border-border hover:bg-muted/50",
      )}
    >
      <AvatarImg src={p.avatarUrl} name={p.name} alt="" className="size-14 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold">{p.name}</span>
          {leader ? (
            <span className="shrink-0 rounded-full bg-pink-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-pink-600 dark:text-pink-400">
              Top
            </span>
          ) : null}
        </div>
        <p className="truncate text-sm text-muted-foreground">{p.tagline}</p>
        <span className="mt-0.5 inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
          {p.rating.toFixed(1)} ({p.reviewCount})
        </span>
      </div>
    </button>
  );
}
