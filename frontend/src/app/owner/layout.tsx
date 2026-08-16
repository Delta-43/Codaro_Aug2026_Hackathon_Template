"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { OwnerProvider } from "@/context/owner-context";
import { BusinessShell } from "@/components/business/business-shell";

/**
 * Business mode — gated on the *owner* role (a separate persona from the
 * customer app, so it lives outside the (app) group and gets its own five-tab
 * shell). Anonymous → /login; a signed-in non-owner → /search.
 *
 * `confirmedOwner` latches once we've seen an owner session, so a transient
 * `isOwner=false` during a token refresh / auth-state settle never bounces an
 * established owner out to the customer app.
 */
export default function OwnerLayout({ children }: { children: ReactNode }) {
  const { session, loading, isOwner } = useAuth();
  const router = useRouter();
  const confirmedOwner = useRef(false);
  if (isOwner) confirmedOwner.current = true;

  useEffect(() => {
    if (loading) return;
    if (!session) router.replace("/login?next=/owner");
    else if (!isOwner && !confirmedOwner.current) router.replace("/search");
  }, [loading, session, isOwner, router]);

  const allowed = isOwner || confirmedOwner.current;
  if (loading || !session || !allowed) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        {loading ? "Loading…" : "Business access required — redirecting…"}
      </div>
    );
  }

  return (
    <OwnerProvider>
      <BusinessShell>{children}</BusinessShell>
    </OwnerProvider>
  );
}
