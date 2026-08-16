"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

/**
 * Owner area — gated on the *owner* role (a separate persona from the customer
 * app, so it lives outside the (app) group and gets its own minimal shell).
 * Anonymous → /login; a signed-in non-owner → /search.
 */
export default function OwnerLayout({ children }: { children: ReactNode }) {
  const { session, loading, isOwner, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!session) router.replace("/login?next=/owner");
    else if (!isOwner) router.replace("/search");
  }, [loading, session, isOwner, router]);

  if (loading || !session || !isOwner) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        {loading ? "Loading…" : "Owner access required — redirecting…"}
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur md:px-6">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold tracking-tight">Codaro</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            Business
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/search" className="text-sm text-muted-foreground hover:text-foreground">
            View as customer
          </Link>
          <Button variant="outline" size="sm" onPress={() => signOut().then(() => router.replace("/login"))}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-4 md:px-6">{children}</main>
    </div>
  );
}
