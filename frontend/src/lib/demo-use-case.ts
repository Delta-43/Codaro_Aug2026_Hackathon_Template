"use client";

/**
 * The active demo use case, held client-side and shared across both apps
 * (customer + business). It's a *demo* dimension — a hard refresh keeps your
 * last choice (localStorage), and switching it re-renders every surface that
 * reads mock content. A tiny pub/sub keeps the two contexts in sync without a
 * global provider.
 */
import { useEffect, useState } from "react";
import { DEFAULT_USE_CASE, getUseCase, isUseCaseId, type UseCase, type UseCaseId } from "@/config/useCases";

const KEY = "codaro.demo.useCase";
const subs = new Set<() => void>();

function read(): UseCaseId {
  if (typeof window === "undefined") return DEFAULT_USE_CASE;
  const v = localStorage.getItem(KEY);
  return isUseCaseId(v) ? v : DEFAULT_USE_CASE;
}

let current: UseCaseId = read();

function setUseCaseId(id: UseCaseId): void {
  current = id;
  if (typeof window !== "undefined") localStorage.setItem(KEY, id);
  subs.forEach((fn) => fn());
}

/** Subscribe to the active use case. Returns `[useCase, setId]`. */
export function useDemoUseCase(): readonly [UseCase, (id: UseCaseId) => void] {
  const [id, setId] = useState<UseCaseId>(current);
  useEffect(() => {
    // Reconcile with localStorage on mount (SSR rendered the default).
    setId(current);
    const fn = () => setId(current);
    subs.add(fn);
    return () => {
      subs.delete(fn);
    };
  }, []);
  return [getUseCase(id), setUseCaseId] as const;
}
