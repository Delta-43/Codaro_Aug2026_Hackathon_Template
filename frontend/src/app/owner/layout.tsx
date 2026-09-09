// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { OwnerProvider } from "@/context/owner-context";
import { BusinessShell } from "@/components/business/business-shell";

/**
 * Business mode: gated on the *owner* role (a separate persona from the
 * customer app, so it lives outside the (app) group and gets its own five-tab
 * shell). Anonymous → /login; a signed-in non-owner → /search.
 *
 * The role is the **trusted** one the backend resolves from `profiles`, not a
 * JWT claim: so what this gate shows and what the API allows can no longer
 * disagree. It arrives a beat after the session, hence `roleReady`: treating
 * "not resolved yet" as "not an owner" would bounce a business out of business
 * mode on every page load.
 *
 * This used to keep a `confirmedOwner` ref, latched once an owner session had
 * been seen, so that a transient `isOwner=false` mid-token-refresh didn't eject
 * an established owner. That latch is no longer needed: the resolved role is
 * held in `AuthProvider` state that survives a token refresh (and a failed
 * re-check keeps the previous value), so `isOwner` has no flicker left to
 * absorb, and unlike the ref, that protection now survives navigation instead
 * of resetting with the component.
 */
export default function OwnerLayout({ children }: { children: ReactNode }) {
  const { session, loading, isOwner, roleReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!session) router.replace("/login?next=/owner");
    else if (roleReady && !isOwner) router.replace("/search");
  }, [loading, session, isOwner, roleReady, router]);

  const settling = loading || (!!session && !roleReady);
  if (settling || !session || !isOwner) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        {settling
          ? "Loading…"
          : !session
            ? "Sign in to continue, redirecting…"
            : "Business access required, redirecting…"}
      </div>
    );
  }

  return (
    <OwnerProvider>
      <BusinessShell>{children}</BusinessShell>
    </OwnerProvider>
  );
}
