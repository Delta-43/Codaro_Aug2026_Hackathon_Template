"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

/**
 * Gates the authenticated app: a visitor without a session is redirected to
 * /login (carrying the path they wanted as `?next=`), and children are held
 * back until a session exists. While Supabase restores the persisted session we
 * show a light placeholder rather than flashing the app or the login screen.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !session) {
      const next = encodeURIComponent(pathname || "/search");
      router.replace(`/login?next=${next}`);
    }
  }, [loading, session, pathname, router]);

  if (loading || !session) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  return <>{children}</>;
}
