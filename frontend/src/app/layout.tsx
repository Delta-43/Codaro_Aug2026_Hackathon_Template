import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Outfit } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { cn } from "@/lib/utils";
import { AuthProvider } from "@/lib/auth";

const outfit = Outfit({subsets:['latin'],variable:'--font-outfit'});

export const metadata: Metadata = {
  title: "Arbor",
  description: "Booking and resource scheduling — demo build.",
  icons: { icon: "/favicon.ico?v=2" },
};

// Enables env(safe-area-inset-*) and prevents zoom-on-input jank on mobile.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#ffffff",
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
