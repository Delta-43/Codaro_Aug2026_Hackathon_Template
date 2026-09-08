// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * "Have a provider code?" — resolves a publicCode via getProviderByCode.
 * Surfaces the API's error message verbatim (plain, specific — no
 * "Something went wrong").
 */
import { useState } from "react";
import type { Provider } from "@/types/domain";
import { getProviderByCode, isApiError } from "@/api";
import { Button } from "@/components/ui/button";

const INPUT =
  "h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

export function CodeEntry({ onResolved }: { onResolved: (p: Provider) => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const value = code.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      const provider = await getProviderByCode(value);
      onResolved(provider);
      setCode("");
    } catch (err) {
      setError(isApiError(err) ? err.message : "Couldn't reach the service. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder="e.g. VISTULA-4471"
          aria-label="Provider code"
          autoCapitalize="characters"
          className={INPUT}
        />
        <Button isDisabled={busy || !code.trim()} onPress={submit}>
          {busy ? "Finding…" : "Find"}
        </Button>
      </div>
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
