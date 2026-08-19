"use client";

/**
 * Public landing page for anonymous visitors — outside the gated (app) group,
 * so no AppProvider/useVertical() here. Pitches the engine/product itself,
 * deliberately vertical-agnostic (see hero.tsx) — the live-demo vertical only
 * comes back into play in the later "featured providers" section.
 *
 * Built section by section (see docs/issues/26-loading-page.md). Full page:
 * Hero → How it works → Testimonials → Business CTA → Footer.
 */
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

  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth">
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
