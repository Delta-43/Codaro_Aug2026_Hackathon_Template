// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Standardizes the four data-driven states (loading, error, loaded, and the
 * caller's own empty check) for read calls through the API seam. Re-runs when
 * `deps` change and ignores stale resolutions after unmount / dep change, so a
 * fast tab switch never flashes old data.
 */
import { useCallback, useEffect, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  /** Manually re-run (e.g. a retry button). */
  reload: () => void;
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: React.DependencyList,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, reload };
}
