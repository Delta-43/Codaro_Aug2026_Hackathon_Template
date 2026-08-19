"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

/**
 * Gates the authenticated app: a visitor without a session is redirected to
 * /login (carrying the path they wanted as `?next=`), and children are held
 * back until a session exists. While Supabase restores the persisted session we
 * show a light placeholder rather than flashing the app or the login screen.
 *
 * Pass `fallback` to render in-place instead of redirecting — an iframed embed
 * must never navigate its own top-level location out.
 */
export function AuthGate({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { session, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !session && !fallback) {
      const next = encodeURIComponent(pathname || "/search");
      router.replace(`/login?next=${next}`);
    }
  }, [loading, session, fallback, pathname, router]);

  if (!loading && !session && fallback) {
    return <>{fallback}</>;
  }

  if (loading || !session) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  return <>{children}</>;
}
