"use client";

/**
 * The app's core client state, in one provider:
 *  - the active demo vertical + its config (labels/nouns/copy),
 *  - the signed-in mock user,
 *  - the locked-in provider / service / resource (tabs 2 & 3 operate only on
 *    this; nothing locked in → those tabs show a purposeful empty state).
 *
 * All persistence is in-memory: a hard refresh resets to seed, by design.
 * Everything reads through the API seam (@/api) — never the store directly.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Provider, Resource, Service, User, VerticalId } from "@/types/domain";
import {
  getActiveVertical,
  getCurrentUser,
  resetDemoData as apiResetDemoData,
  setVertical as apiSetVertical,
} from "@/api";
import { DEFAULT_VERTICAL, getVertical, type VerticalConfig } from "@/config/verticals";

interface AppContextValue {
  /** False until the first user/vertical fetch resolves. */
  ready: boolean;

  verticalId: VerticalId;
  vertical: VerticalConfig;
  user: User | null;

  activeProvider: Provider | null;
  activeService: Service | null;
  /** null means "any available unit" for unit_selection services. */
  activeResource: Resource | null;

  lockInProvider: (provider: Provider) => void;
  clearActiveProvider: () => void;
  selectService: (service: Service | null) => void;
  selectResource: (resource: Resource | null) => void;

  /** Apply a User returned by the API (e.g. after follow/unfollow/update). */
  setUser: (user: User) => void;
  refreshUser: () => Promise<void>;

  switchVertical: (id: VerticalId) => Promise<void>;
  reseed: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [verticalId, setVerticalId] = useState<VerticalId>(DEFAULT_VERTICAL);
  const [user, setUserState] = useState<User | null>(null);

  const [activeProvider, setActiveProvider] = useState<Provider | null>(null);
  const [activeService, setActiveService] = useState<Service | null>(null);
  const [activeResource, setActiveResource] = useState<Resource | null>(null);

  const refreshUser = useCallback(async () => {
    setUserState(await getCurrentUser());
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [vid, u] = await Promise.all([getActiveVertical(), getCurrentUser()]);
      if (cancelled) return;
      setVerticalId(vid);
      setUserState(u);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const clearActiveProvider = useCallback(() => {
    setActiveProvider(null);
    setActiveService(null);
    setActiveResource(null);
  }, []);

  const lockInProvider = useCallback((provider: Provider) => {
    setActiveProvider(provider);
    setActiveService(null);
    setActiveResource(null);
  }, []);

  const selectService = useCallback((service: Service | null) => {
    setActiveService(service);
    setActiveResource(null);
  }, []);

  const switchVertical = useCallback(
    async (id: VerticalId) => {
      await apiSetVertical(id);
      clearActiveProvider();
      setVerticalId(id);
      await refreshUser();
    },
    [clearActiveProvider, refreshUser],
  );

  const reseed = useCallback(async () => {
    await apiResetDemoData();
    clearActiveProvider();
    await refreshUser();
  }, [clearActiveProvider, refreshUser]);

  const value: AppContextValue = {
    ready,
    verticalId,
    vertical: getVertical(verticalId),
    user,
    activeProvider,
    activeService,
    activeResource,
    lockInProvider,
    clearActiveProvider,
    selectService,
    selectResource: setActiveResource,
    setUser: setUserState,
    refreshUser,
    switchVertical,
    reseed,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within <AppProvider>");
  return ctx;
}

/** The active vertical's config (labels, nouns, copy). */
export function useVertical(): VerticalConfig {
  return useApp().vertical;
}
