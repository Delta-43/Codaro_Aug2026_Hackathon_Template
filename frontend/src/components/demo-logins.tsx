// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { useState } from "react";
import { Store, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

/**
 * One-tap sign-in for the two seeded demo accounts, shown on both sign-in
 * doors. Either door takes either account (see the note in `login/page.tsx`),
 * so both buttons render on both pages, the parent's redirect effect routes on
 * the resolved role once the session lands.
 *
 * These credentials are seeded by `backend/seed.py` and ship in the client
 * bundle by design: they are demo logins against demo data, not secrets.
 */
const DEMO_ACCOUNTS = [
  {
    key: "client",
    label: "Demo customer",
    email: "demo@codaro.app",
    password: "Codaro-Demo-2026",
    Icon: User,
  },
  {
    key: "owner",
    label: "Demo business",
    email: "owner@codaro.app",
    password: "Codaro-Owner-2026",
    Icon: Store,
  },
] as const;

export function DemoLogins({
  disabled,
  onError,
}: {
  disabled?: boolean;
  onError: (message: string | null) => void;
}) {
  const { signIn, configured } = useAuth();
  // Which account is mid-flight, so only the tapped button shows the pending
  // label while both stay disabled.
  const [pending, setPending] = useState<string | null>(null);

  async function signInAsDemo(account: (typeof DEMO_ACCOUNTS)[number]) {
    onError(null);
    setPending(account.key);
    try {
      await signIn(account.email, account.password);
      // No redirect here: the page's own effect owns that, and it waits for the
      // trusted role so an owner isn't flashed the customer app first.
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not sign in.");
      setPending(null);
    }
  }

  return (
    <div className="mt-6">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">or try a demo account</span>
        <span className="h-px flex-1 bg-border" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {DEMO_ACCOUNTS.map((account) => (
          <Button
            key={account.key}
            type="button"
            variant="outline"
            size="lg"
            isDisabled={disabled || !configured || pending !== null}
            onPress={() => signInAsDemo(account)}
          >
            <account.Icon aria-hidden />
            {pending === account.key ? "Signing in…" : account.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
