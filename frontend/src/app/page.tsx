"use client";

/**
 * Public marketing landing page, served at the app root (`/`). It's outside the
 * gated `(app)` group and uses no AppProvider/useAuth/useVertical: it always
 * renders the logged-out-shaped CTAs and links (via next/link) to /login and
 * /privacy.
 *
 * The deployment this markets is the funeral-home pivot (issue 109): Arbor keeps
 * its name and leaf mark, but every plate now speaks the funeral business —
 * arrangements, chapels, and the farewell products families actually buy. Full
 * page: Hero → Calendar showcase → Popular products → Reviews → Footer.
 */
import { SceneBackground } from "@/components/landing/scene-background";
import { NavBar } from "@/components/landing/nav-bar";
import { Hero } from "@/components/landing/hero";
import { CalendarShowcase } from "@/components/landing/calendar-showcase";
import { Products } from "@/components/landing/products";
import { Testimonials } from "@/components/landing/testimonials";
import { Footer } from "@/components/landing/footer";

export default function RootPage() {
  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth [scrollbar-gutter:stable_both-edges]">
      <SceneBackground />
      <NavBar />
      <Hero />
      <CalendarShowcase />
      <Products />
      <Testimonials />
      <Footer />
    </main>
  );
}
