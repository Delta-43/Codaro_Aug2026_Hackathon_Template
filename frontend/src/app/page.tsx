"use client";

/**
 * Public landing page for anonymous visitors — outside the gated (app) group,
 * so no useVertical() here. Pitches the engine/product itself, deliberately
 * vertical-agnostic (see hero.tsx) — the live-demo vertical only comes back
 * into play in the later "featured providers" section.
 *
 * Built section by section (see docs/issues/26-loading-page.md). Full page:
 * Hero → How it works → Testimonials → Business CTA → Footer.
 *
 * Also loads `plugin_sdk`'s own widget script (`/embed.js`) when this
 * deployment is single-tenant — the exact same snippet a third-party business
 * would paste into their own site, running here on ours, in buttonless mode
 * (this page's own Login/Get Started/Sign in buttons open the widget modal
 * via `window.Arbor.open()` instead of the script's floating launcher).
 * Dogfooding beats a second bespoke login modal: it proves the plugin works
 * on a real page instead of only a throwaway test host, and it completes the
 * project's story end to end (engine → pivot → plugin) without hiding the
 * pitch behind a business-specific storefront. `/embed` only resolves a
 * business in single-tenant mode (see plugin_sdk/CLAUDE.md), so the script is
 * gated on that the same way `/login`'s business-signup link already is.
 */
import { useEffect, useState } from "react";
import Script from "next/script";
import { getTenancy } from "@/api";
import { useAuth } from "@/lib/auth";
import { SceneBackground } from "@/components/landing/scene-background";
import { NavBar } from "@/components/landing/nav-bar";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { CalendarDemo } from "@/components/landing/calendar-demo";
import { Testimonials } from "@/components/landing/testimonials";
import { DocsCta } from "@/components/landing/docs-cta";
import { BusinessCta } from "@/components/landing/business-cta";
import { Footer } from "@/components/landing/footer";

export default function RootPage() {
  const { session, loading } = useAuth();
  const authed = !loading && !!session;

  const [singleTenant, setSingleTenant] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getTenancy()
      .then((t) => {
        if (!cancelled) setSingleTenant(t.mode === "single");
      })
      .catch(() => {
        /* stay false — no widget rather than a broken one */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth">
      {singleTenant ? (
        <Script src="/embed.js" data-mode="buttonless" strategy="afterInteractive" />
      ) : null}
      <SceneBackground />
      <NavBar authed={authed} />
      <Hero authed={authed} />
      <HowItWorks />
      <CalendarDemo />
      <Testimonials />
      <DocsCta />
      <BusinessCta authed={authed} />
      <Footer authed={authed} />
    </main>
  );
}
