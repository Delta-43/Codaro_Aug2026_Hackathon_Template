// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Metadata } from "next";
import { ShowcaseBackdrop } from "@/components/showcase/showcase-backdrop";
import { ShowcaseHeader } from "@/components/showcase/showcase-header";
import { ServiceList } from "@/components/showcase/service-list";
import { ShowcaseFooter } from "@/components/showcase/showcase-footer";
import { cinzel, showcaseDisplayClass } from "@/components/showcase/showcase-fonts";
import { HERO_TITLE, HERO_SUBTITLE, PAGE_META_TITLE, PAGE_META_DESCRIPTION } from "@/components/showcase/showcase-copy";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: PAGE_META_TITLE,
  description: PAGE_META_DESCRIPTION,
};

/**
 * Public services gallery, forced dark via the `.dark` wrapper below
 * regardless of the site-wide theme toggle (next-themes' `resolvedTheme` is
 * global, so a local class is the only way to pin one page's theme).
 */
export default function ShowcasePage() {
  return (
    <div className="dark min-h-dvh text-foreground">
      <ShowcaseBackdrop />
      <ShowcaseHeader />
      <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
        <div className="mb-16 text-center sm:mb-24">
          <h1
            className={cn(
              "text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl",
              cinzel.variable,
              showcaseDisplayClass,
            )}
          >
            {HERO_TITLE}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-muted-foreground sm:text-lg">{HERO_SUBTITLE}</p>
        </div>
        <ServiceList />
      </main>
      <ShowcaseFooter />
    </div>
  );
}
