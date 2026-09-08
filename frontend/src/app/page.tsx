// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Public marketing landing page, served at the app root (`/`). It's outside the
 * gated `(app)` group and uses no AppProvider/useAuth/useVertical: it always
 * renders the logged-out-shaped CTAs and links (via next/link) to
 * /login, /docs, and /privacy. Pitches the engine/product itself, deliberately
 * vertical-agnostic (see hero.tsx) — the live-demo vertical only comes back
 * into play in the later "featured providers" section.
 *
 * Built section by section. Full page:
 * Hero → How it works → Testimonials → Business CTA → Footer.
 */
import { SceneBackground } from "@/components/landing/scene-background";
import { NavBar } from "@/components/landing/nav-bar";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { CalendarShowcase } from "@/components/landing/calendar-showcase";
import { Testimonials } from "@/components/landing/testimonials";
import { DocsCta } from "@/components/landing/docs-cta";
import { BusinessCta } from "@/components/landing/business-cta";
import { Footer } from "@/components/landing/footer";

export default function RootPage() {
  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth [scrollbar-gutter:stable_both-edges]">
      <SceneBackground />
      <NavBar />
      <Hero />
      <HowItWorks />
      <CalendarShowcase />
      <Testimonials />
      <DocsCta />
      <BusinessCta />
      <Footer />
    </main>
  );
}
