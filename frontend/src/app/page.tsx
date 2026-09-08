// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Public marketing landing page, served at the app root (`/`). It's outside the
 * gated `(app)` group and uses no AppProvider/useAuth/useVertical: it always
 * renders the logged-out-shaped CTAs and links (via next/link) to /login and
 * /privacy.
 *
 * This markets the engine itself rather than any one pivot of it: the plates
 * describe the config blocks, the booking pipeline and the evidence behind the
 * claim, so the page reads the same whatever `domain.config.json` currently
 * says. Full page: Hero → Calendar showcase → Pivot blocks → Evidence → Footer.
 */
import { SceneBackground } from "@/components/landing/scene-background";
import { NavBar } from "@/components/landing/nav-bar";
import { Hero } from "@/components/landing/hero";
import { CalendarShowcase } from "@/components/landing/calendar-showcase";
import { Products } from "@/components/landing/products";
import { Proof } from "@/components/landing/proof";
import { Footer } from "@/components/landing/footer";

export default function RootPage() {
  return (
    <main className="relative h-dvh snap-y snap-mandatory overflow-y-auto scroll-smooth [scrollbar-gutter:stable_both-edges]">
      <SceneBackground />
      <NavBar />
      <Hero />
      <CalendarShowcase />
      <Products />
      <Proof />
      <Footer />
    </main>
  );
}
