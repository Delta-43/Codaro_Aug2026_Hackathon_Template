"use client";

/**
 * Landing page — a standalone deployable, air-gapped from the app (see
 * landing/CLAUDE.md). No AppProvider/useAuth/useVertical here by design: this
 * page cannot see a visitor's session on the app's origin, so it always
 * renders the logged-out-shaped CTAs and links out (plain cross-origin <a>,
 * not next/link) to `${NEXT_PUBLIC_APP_URL}` for login/search/docs/privacy.
 * Pitches the engine/product itself, deliberately vertical-agnostic (see
 * hero.tsx) — the live-demo vertical only comes back into play in the later
 * "featured providers" section.
 *
 * Built section by section (see docs/issues/26-loading-page.md). Full page:
 * Hero → How it works → Testimonials → Business CTA → Footer.
 */
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
  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth">
      <SceneBackground />
      <NavBar />
      <Hero />
      <HowItWorks />
      <CalendarDemo />
      <Testimonials />
      <DocsCta />
      <BusinessCta />
      <Footer />
    </main>
  );
}
