"use client";

/**
 * Business-mode client state, shared across the five owner tabs (dashboard /
 * services / requests / calendar / profile) plus settings.
 *
 * Two data sources, kept distinct:
 *  - `useCase` (client-side demo dimension, switchable in Settings → Demo) drives
 *    the showcase identity + all demo-generated content across every niche.
 *  - `providers` (real, owner-gated `getMyProviders`) backs the Services tab's
 *    live create/edit/delete. The active one is remembered in localStorage.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Provider } from "@/types/domain";
import { getMyProviders } from "@/api";
import { useDemoUseCase } from "@/lib/demo-use-case";
import type { UseCase, UseCaseId } from "@/config/useCases";

const PID_KEY = "codaro.owner.activeProviderId";

interface OwnerContextValue {
  ready: boolean;
  providers: Provider[] | null;
  activeProvider: Provider | null;
  /** The active demo niche — vocabulary + showcase identity + mock content. */
  useCase: UseCase;
  setUseCaseId: (id: UseCaseId) => void;
  /** The showcase business shown across business mode for the active niche. */
  demoBusiness: UseCase["business"];
  /** Stable seed for the deterministic demo generators. */
  seed: string;
  setActiveProviderId: (id: string) => void;
  refreshProviders: () => Promise<void>;
}

const OwnerContext = createContext<OwnerContextValue | null>(null);

export function OwnerProvider({ children }: { children: ReactNode }) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [useCase, setUseCaseId] = useDemoUseCase();

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
      const list = await getMyProviders().catch(() => [] as Provider[]);
      if (cancelled) return;
      setProviders(list);
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
    useCase,
    setUseCaseId,
    demoBusiness: useCase.business,
    seed: `${useCase.id}:${activeProvider?.id ?? "demo"}`,
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
