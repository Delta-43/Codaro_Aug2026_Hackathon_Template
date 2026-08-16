"use client";

/**
 * Business-mode client state, shared across the five owner tabs (dashboard /
 * services / requests / calendar / profile) plus settings.
 *
 * Everything here is REAL, owner-gated data:
 *  - `providers` come from `getMyProviders` (owner-scoped); the active one is
 *    remembered in localStorage and drives the Services CRUD + the profile.
 *  - `vocab` is the live vertical's UI vocabulary (`config/verticals.ts`), keyed
 *    off the currently-seeded vertical (`getActiveVertical`).
 *  - `scene` is the on-brand illustrated profile art for the vertical.
 * The per-tab aggregates (dashboard numbers, requests, calendar) are fetched by
 * the pages themselves from the `/owner/*` endpoints.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Provider, VerticalId } from "@/types/domain";
import { getActiveVertical, getMyProviders } from "@/api";
import { VERTICALS, type VerticalConfig } from "@/config/verticals";

const PID_KEY = "codaro.owner.activeProviderId";

/** On-brand illustrated profile art per vertical (see components/business/business-art). */
const VERTICAL_SCENE: Record<VerticalId, string> = {
  fleet: "car-hero",
  oneToOne: "tutor-hero",
  group: "yoga-hero",
};

interface OwnerContextValue {
  ready: boolean;
  providers: Provider[] | null;
  activeProvider: Provider | null;
  /** The live vertical's UI vocabulary (nouns/copy). */
  vocab: VerticalConfig;
  vertical: VerticalId;
  /** On-brand illustrated profile scene for the vertical. */
  scene: string;
  setActiveProviderId: (id: string) => void;
  refreshProviders: () => Promise<void>;
}

const OwnerContext = createContext<OwnerContextValue | null>(null);

export function OwnerProvider({ children }: { children: ReactNode }) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [vertical, setVertical] = useState<VerticalId>("fleet");
  const [ready, setReady] = useState(false);

  const refreshProviders = useCallback(async () => {
    try {
      setProviders(await getMyProviders());
    } catch {
      setProviders([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [list, v] = await Promise.all([
        getMyProviders().catch(() => [] as Provider[]),
        getActiveVertical().catch(() => "fleet" as VerticalId),
      ]);
      if (cancelled) return;
      setProviders(list);
      setVertical(v);
      const stored = typeof window !== "undefined" ? localStorage.getItem(PID_KEY) : null;
      setPid(list.find((p) => p.id === stored)?.id ?? list[0]?.id ?? null);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setActiveProviderId = useCallback((id: string) => {
    setPid(id);
    if (typeof window !== "undefined") localStorage.setItem(PID_KEY, id);
  }, []);

  const activeProvider = providers?.find((p) => p.id === pid) ?? providers?.[0] ?? null;

  const value: OwnerContextValue = {
    ready,
    providers,
    activeProvider,
    vocab: VERTICALS[vertical] ?? VERTICALS.fleet,
    vertical,
    scene: VERTICAL_SCENE[vertical] ?? "grad-amber",
    setActiveProviderId,
    refreshProviders,
  };

  return <OwnerContext.Provider value={value}>{children}</OwnerContext.Provider>;
}

export function useOwner(): OwnerContextValue {
  const ctx = useContext(OwnerContext);
  if (!ctx) throw new Error("useOwner must be used within <OwnerProvider>");
  return ctx;
}
