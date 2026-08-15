"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type DomainConfig = {
  domain: string;
  terms: Record<string, string>;
  rules: Record<string, number>;
  copy: Record<string, string>;
  theme: Record<string, string>;
  metaFields: Record<string, Array<{ key: string; label: string; type: string }>>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function fetchConfig(): Promise<DomainConfig> {
  const res = await fetch(`${API_BASE}/config`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /config failed: ${res.status}`);
  return res.json();
}

const DomainContext = createContext<DomainConfig | null>(null);

export function DomainProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<DomainConfig | null>(null);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(console.error);
  }, []);

  if (!config) return null; // TODO: loading state
  return <DomainContext.Provider value={config}>{children}</DomainContext.Provider>;
}

export function useDomain(): DomainConfig {
  const ctx = useContext(DomainContext);
  if (!ctx) throw new Error("useDomain() must be used within <DomainProvider>");
  return ctx;
}

/** Renders a single term from config.terms, e.g. <Term term="resource" /> -> "Doctor" */
export function Term({ term, plural = false }: { term: string; plural?: boolean }) {
  const { terms } = useDomain();
  const key = plural ? `${term}s` : term;
  return <>{terms[key] ?? terms[term] ?? term}</>;
}
