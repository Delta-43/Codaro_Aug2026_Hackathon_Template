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
import {
  getActiveVertical,
  getMyProviders,
  getPivotConfig,
  FALLBACK_PIVOT_CONFIG,
  type Capabilities,
  type ConfigCopy,
  type MetaFields,
  type TenancyTerms,
  type ConfigTerms,
} from "@/api";
import { applyPivotVocabulary, VERTICALS, type VerticalConfig } from "@/config/verticals";

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
  /** The live vertical's UI vocabulary (nouns/copy), with the pivot file's
   *  `terms`/`copy` overlaid — the owner console must name things exactly as the
   *  customer side does, so both read the same overlay. */
  vocab: VerticalConfig;
  vertical: VerticalId;
  /** On-brand illustrated profile scene for the vertical. */
  scene: string;
  /** Global `capabilities.<name>` (default ON). Only a FALLBACK: the routers
   *  gate per service, so prefer `Service.capabilities` and use this when the
   *  per-service value is unavailable — e.g. the services fetch failed. */
  capability: (name: string) => boolean;
  /** `tenancy` — what this business is signed up to: whether it can onboard
   *  itself, what it must be verified with, and what the platform takes. All
   *  three were config-only and shown on no owner screen. */
  tenancyTerms: TenancyTerms;
  /** `metaFields.{entity}` — the domain fields this deployment declares, so the
   *  owner's own create/edit forms can offer what the backend already validates. */
  metaFields: MetaFields;
  setActiveProviderId: (id: string) => void;
  refreshProviders: () => Promise<void>;
  /** Replace one already-loaded provider in place (e.g. after an avatar edit),
   *  without a refetch that could transiently blank the list. */
  replaceProvider: (provider: Provider) => void;
}

const OwnerContext = createContext<OwnerContextValue | null>(null);

export function OwnerProvider({ children }: { children: ReactNode }) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [vertical, setVertical] = useState<VerticalId>("fleet");
  const [ready, setReady] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities>({});
  const [terms, setTerms] = useState<ConfigTerms>({});
  const [copy, setCopy] = useState<ConfigCopy>({});
  const [tenancyTerms, setTenancyTerms] = useState<TenancyTerms>(
    FALLBACK_PIVOT_CONFIG.tenancyTerms,
  );
  const [metaFields, setMetaFields] = useState<MetaFields>({});

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
      const [list, v, pivot] = await Promise.all([
        getMyProviders().catch(() => [] as Provider[]),
        getActiveVertical().catch(() => "fleet" as VerticalId),
        // /config unreachable: leave everything ON and keep the static
        // vocabulary — the backend still refuses whatever is actually disabled.
        getPivotConfig().catch(() => FALLBACK_PIVOT_CONFIG),
      ]);
      if (cancelled) return;
      setProviders(list);
      setVertical(v);
      setCapabilities(pivot.capabilities);
      setTerms(pivot.terms);
      setCopy(pivot.copy);
      setTenancyTerms(pivot.tenancyTerms);
      setMetaFields(pivot.metaFields);
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

  const replaceProvider = useCallback((provider: Provider) => {
    setProviders((list) => list?.map((p) => (p.id === provider.id ? provider : p)) ?? list);
  }, []);

  // Unknown name -> true: the config lists only what it turns off. Mirrors
  // rules.capability() on the backend.
  const capability = useCallback(
    (name: string) => capabilities[name] !== false,
    [capabilities],
  );

  const activeProvider = providers?.find((p) => p.id === pid) ?? providers?.[0] ?? null;

  const value: OwnerContextValue = {
    ready,
    capability,
    tenancyTerms,
    metaFields,
    providers,
    activeProvider,
    vocab: applyPivotVocabulary(VERTICALS[vertical] ?? VERTICALS.fleet, terms, copy),
    vertical,
    scene: VERTICAL_SCENE[vertical] ?? "grad-amber",
    setActiveProviderId,
    refreshProviders,
    replaceProvider,
  };

  return <OwnerContext.Provider value={value}>{children}</OwnerContext.Provider>;
}

export function useOwner(): OwnerContextValue {
  const ctx = useContext(OwnerContext);
  if (!ctx) throw new Error("useOwner must be used within <OwnerProvider>");
  return ctx;
}
