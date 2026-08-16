import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Outfit } from "next/font/google";
import { cn } from "@/lib/utils";
import { AuthProvider } from "@/lib/auth";

const outfit = Outfit({subsets:['latin'],variable:'--font-outfit'});

export const metadata: Metadata = {
  title: "Codaro",
  description: "Booking and resource scheduling — demo build.",
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
    <html lang="en" className={cn("font-sans", outfit.variable)}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
