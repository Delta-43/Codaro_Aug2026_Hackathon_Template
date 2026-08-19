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
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Provider, Resource, Service, User, VerticalId } from "@/types/domain";
import {
  getActiveVertical,
  getCurrentUser,
  getProviderByCode,
  getPivotConfig,
  type MetaFields,
  type SearchFacets,
  type TenancyTerms,
  resetDemoData as apiResetDemoData,
  searchProviders,
  setVertical as apiSetVertical,
  FALLBACK_PIVOT_CONFIG,
  type Capabilities,
  type ConfigCopy,
  type ConfigTerms,
} from "@/api";
import {
  applyPivotVocabulary,
  DEFAULT_VERTICAL,
  getVertical,
  type VerticalConfig,
} from "@/config/verticals";
import { setGeoSettings } from "@/lib/geo";

interface AppContextValue {
  /** False until the first user/vertical fetch resolves. */
  ready: boolean;

  verticalId: VerticalId;
  /** The active vertical's vocabulary with the pivot file's `terms`/`copy`
   *  overlaid — so a config that renames `service` to "Plan" renames it on every
   *  screen. Falls back to the static vertical for anything the config omits. */
  vertical: VerticalConfig;
  /** The pivot file's `copy` block verbatim, for the named moments that have no
   *  vertical equivalent (`confirmTitle`, `requestPending`, the empty states). */
  copy: ConfigCopy;
  /** `metaFields.{entity}` — the domain fields this deployment declares. The
   *  backend validates them on write; the booking form renders them. */
  metaFields: MetaFields;
  /** `discovery.facets` — which search dimensions this deployment offers. */
  facets: SearchFacets;
  /** `tenancy` — self-onboarding, tenant verification and the platform's cut.
   *  Owner-facing: the business needs to see the terms it trades under. */
  tenancyTerms: TenancyTerms;
  user: User | null;

  /** Single-business pivot (`tenancy.mode === "single"`): the site itself is the
   *  only business, so the sole provider is auto-locked and provider discovery is
   *  hidden. False = the multi-provider marketplace. */
  singleBusiness: boolean;

  /** Re-run the whole boot — profile, vertical AND the pivot config. Each leg
   *  degrades independently, so recovering only one leaves the others on their
   *  fallbacks with nothing on screen to say so. */
  reload: () => Promise<void>;

  /** `capabilities.<name>` from the pivot file, defaulting to ON for a name the
   *  config does not mention. Gate a surface on this wherever the backend gates
   *  the matching write, or the user gets a control that 404s. */
  capability: (name: string) => boolean;

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

  // The tenancy mode + sole-business code from `GET /config`. In single mode the
  // provider is never chosen by the user — it's resolved from this code (or, if
  // the code isn't in the active vertical, the catalog's first provider).
  const [singleBusiness, setSingleBusiness] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities>({});
  const [terms, setTerms] = useState<ConfigTerms>({});
  const [copy, setCopy] = useState<ConfigCopy>({});
  const [metaFields, setMetaFields] = useState<MetaFields>({});
  const [facets, setFacets] = useState<SearchFacets>(FALLBACK_PIVOT_CONFIG.facets);
  const [tenancyTerms, setTenancyTerms] = useState<TenancyTerms>(
    FALLBACK_PIVOT_CONFIG.tenancyTerms,
  );
  const [soleProviderCode, setSoleProviderCode] = useState<string | null>(null);

  const [activeProvider, setActiveProvider] = useState<Provider | null>(null);
  const [activeService, setActiveService] = useState<Service | null>(null);
  const [activeResource, setActiveResource] = useState<Resource | null>(null);

  // Guards the post-await setState in resolveSoleProvider against an unmount
  // (navigation / sign-out / fast refresh) mid-resolution.
  const mounted = useRef(true);
  useEffect(() => {
    // Re-arm on every mount, not just the first. Strict Mode (on by default in
    // Next's App Router) runs effects mount -> cleanup -> mount again on the
    // same instance, and refs survive that cycle — so without this the cleanup
    // latched `mounted.current` to false before the second mount and the guard
    // in `resolveSoleProvider` bailed for the rest of the dev session, leaving
    // single-business deployments stuck on the "no business" empty state.
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refreshUser = useCallback(async () => {
    setUserState(await getCurrentUser());
  }, []);

  // Resolve the one implicit business. The configured code is *authoritative*: it
  // must point at the platform's own business so the customer catalog and the
  // owner console never diverge — a code that fails to resolve yields the empty
  // state (a visible misconfiguration) rather than silently substituting an
  // unrelated, highest-rated provider. Only when no code is configured do we
  // best-effort the catalog's first provider.
  const resolveSoleProvider = useCallback(async (code: string | null) => {
    let provider: Provider | null = null;
    try {
      provider = code
        ? await getProviderByCode(code)
        : ((await searchProviders({}))[0] ?? null);
    } catch {
      provider = null;
    }
    if (!mounted.current) return;
    setActiveProvider(provider);
    setActiveService(null);
    setActiveResource(null);
  }, []);

  // Extracted from the mount effect so a retry can re-run EVERY leg. Only the
  // profile leg is visible when it fails, so a retry that re-fetched just that
  // one cleared the error screen while tenancy, vertical and capabilities stayed
  // on their fallbacks for the life of the mount — search exposed on a
  // single-business site, default vocabulary, and every capability reading ON
  // because an empty block means "nothing disabled".
  const boot = useCallback(
    async (isCancelled: () => boolean = () => false) => {
      // The pivot config must not gate boot: if /config is unreachable, degrade to
      // the multi-provider marketplace (and default geo) rather than hanging on the
      // not-ready state.
      const [vid, u, pivot] = await Promise.all([
        // Every leg degrades on its own. Previously only /config had a catch, so
        // a rejecting /me (expired token, 500, network blip) rejected the whole
        // Promise.all, `setReady(true)` never ran, and every surface gated on
        // `ready` sat on a skeleton for the lifetime of the mount with no error
        // and no retry.
        getActiveVertical().catch(() => DEFAULT_VERTICAL),
        getCurrentUser().catch(() => null),
        getPivotConfig().catch(() => FALLBACK_PIVOT_CONFIG),
      ]);
      if (isCancelled()) return;
      setVerticalId(vid);
      setUserState(u);
      // Distances render from the pivot file's origin/unit, not a hardcoded city.
      setGeoSettings(pivot.location);
      setCapabilities(pivot.capabilities);
      // Vocabulary comes from the config too. Applied here (not in a render
      // effect) so a `reload()` after `make reload` repaints without a refresh.
      setTerms(pivot.terms);
      setCopy(pivot.copy);
      setMetaFields(pivot.metaFields);
      setFacets(pivot.facets);
      setTenancyTerms(pivot.tenancyTerms);
      const { tenancy } = pivot;
      const single = tenancy.mode === "single";
      setSingleBusiness(single);
      setSoleProviderCode(tenancy.providerCode);
      if (single) {
        // Best-effort: a failure here must not strand the app as not-ready.
        try {
          await resolveSoleProvider(tenancy.providerCode);
        } catch {
          /* leaves the provider unresolved; the UI degrades to "no business" */
        }
      }
      if (isCancelled()) return;
      setReady(true);
    },
    [resolveSoleProvider],
  );

  useEffect(() => {
    let cancelled = false;
    void boot(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [boot]);

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

  // After a vertical switch / reseed the locked-in provider is stale. Multi mode
  // clears it (back to the picker's empty state); single mode re-resolves the new
  // vertical's sole provider so the catalog is never empty.
  const resettleProvider = useCallback(async () => {
    if (singleBusiness) await resolveSoleProvider(soleProviderCode);
    else clearActiveProvider();
  }, [singleBusiness, soleProviderCode, resolveSoleProvider, clearActiveProvider]);

  // Unknown name -> true: the config lists only what it turns off, and the
  // backend refuses the write regardless. This mirrors rules.capability().
  const capability = useCallback(
    (name: string) => capabilities[name] !== false,
    [capabilities],
  );

  const switchVertical = useCallback(
    async (id: VerticalId) => {
      await apiSetVertical(id);
      setVerticalId(id);
      await resettleProvider();
      await refreshUser();
    },
    [resettleProvider, refreshUser],
  );

  const reseed = useCallback(async () => {
    await apiResetDemoData();
    await resettleProvider();
    await refreshUser();
  }, [resettleProvider, refreshUser]);

  const value: AppContextValue = {
    ready,
    verticalId,
    vertical: applyPivotVocabulary(getVertical(verticalId), terms, copy),
    copy,
    metaFields,
    facets,
    tenancyTerms,
    user,
    singleBusiness,
    capability,
    activeProvider,
    activeService,
    activeResource,
    lockInProvider,
    clearActiveProvider,
    selectService,
    selectResource: setActiveResource,
    setUser: setUserState,
    refreshUser,
    reload: boot,
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
