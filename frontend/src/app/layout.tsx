// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Outfit } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { cn } from "@/lib/utils";
import { AuthProvider } from "@/lib/auth";

const outfit = Outfit({subsets:['latin'],variable:'--font-outfit'});

/** Absolute base for OG/Twitter URLs. Social scrapers reject relative image
 *  paths, so `metadataBase` has to resolve even when nothing is configured:
 *  an explicit site URL wins, Vercel's own hostname is the fallback on a
 *  preview or production deploy, and localhost keeps `next dev` quiet. */
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

const TITLE = "Arbor: one engine, any booking business";
const DESCRIPTION =
  "A config-driven booking engine. Provider, service, resource, slot, booking, user: one neutral spine, and a JSON file that turns it into a different business.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Arbor",
  description: DESCRIPTION,
  icons: { icon: "/favicon.ico?v=2" },
  // Without these a shared link renders as a bare card: the title, and an empty
  // grey image box. Most people who meet this project through a link will only
  // ever see the card, so it is the page for them. The image itself is generated
  // by `app/opengraph-image.tsx`, which Next wires in automatically.
  openGraph: {
    type: "website",
    siteName: "Arbor",
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};

// Enables env(safe-area-inset-*) and prevents zoom-on-input jank on mobile.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // Paired, so the mobile browser chrome follows the page instead of staying
  // white above a black page in dark mode.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class on <html> via a
    // pre-paint inline script, so the server markup and first client render differ.
    <html lang="en" className={cn("font-sans", outfit.variable)} suppressHydrationWarning>
      <body>
        {/* Smart dark mode: first load follows the OS light/dark setting live
            (next-themes "system"); flipping the footer/account toggle pins an
            explicit light/dark choice, which then persists. */}
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
