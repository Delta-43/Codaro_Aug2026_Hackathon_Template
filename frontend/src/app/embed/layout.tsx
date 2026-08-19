"use client";

/**
 * Chromeless mount for a third-party site's iframe: <AuthGate> (in-frame
 * login, never a redirect) → <AppProvider> (resolves the single business from
 * tenancy.providerCode, same as the main app) → children — no <AppShell>
 * nav/tab-bar/footer. Applies the pivot's theme.primaryColor/fontFamily to
 * this subtree only; the main (app) tree is unaffected (see backend/CLAUDE.md
 * "Declared but NOT enforced" — theme has no other reader today).
 *
 * Deliberately no `frame-ancestors` allow-list: this route is meant to be
 * embedded by any third-party business's site with zero config (that's the
 * "plug and play" pitch) — a fixed allowlist would defeat that unless a
 * business also registers its domain somewhere first, which nothing here
 * requires. The real security boundary is bearer-token auth + RLS, not who's
 * allowed to iframe the page. See plugin_sdk/CLAUDE.md's Conventions section.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AppProvider } from "@/context/app-context";
import { AuthGate } from "@/components/auth-gate";
import { EmbedLoginPanel } from "@/components/embed/login-panel";
import { getPivotConfig, type ThemeConfig } from "@/api";

export default function EmbedLayout({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPivotConfig()
      .then((cfg) => {
        if (!cancelled) setTheme(cfg.theme);
      })
      .catch(() => {
        /* fall back to the app's default tokens */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Tells plugin_sdk/embed.js's launcher modal how tall to size the iframe as
  // content changes — both the login panel (AuthGate's `fallback`) and the
  // booking flow (`children`) need this, so the ref wraps <AuthGate> itself,
  // not something nested inside its `children` (which doesn't exist in the
  // DOM at all while the fallback is showing). A no-op when not actually
  // framed — same route works fine visited directly. Deliberately NOT on the
  // outer min-h-dvh div below: a min-h-dvh element's scrollHeight is pinned to
  // the iframe's OWN viewport (which this very message controls) — circular,
  // it'd just echo back whatever height the modal already set.
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (window.parent === window || !contentRef.current) return;
    const el = contentRef.current;
    const post = () =>
      window.parent.postMessage({ type: "codaro:resize", height: el.scrollHeight }, "*");
    const observer = new ResizeObserver(post);
    observer.observe(el);
    post();
    return () => observer.disconnect();
  }, []);

  return (
    <div
      className="min-h-dvh bg-background text-foreground"
      style={{
        ...(theme?.primaryColor ? { ["--primary" as string]: theme.primaryColor } : {}),
        ...(theme?.radius ? { ["--radius" as string]: theme.radius } : {}),
        ...(theme?.fontFamily ? { fontFamily: theme.fontFamily } : {}),
      }}
    >
      <div ref={contentRef}>
        <AuthGate fallback={<EmbedLoginPanel />}>
          <AppProvider>
            <main className="mx-auto w-full max-w-lg px-4 py-4">
              {theme?.logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- arbitrary host-supplied URL, not a local asset
                <img src={theme.logoUrl} alt="" className="mx-auto mb-4 h-10 w-auto" />
              ) : null}
              {children}
            </main>
          </AppProvider>
        </AuthGate>
      </div>
    </div>
  );
}
