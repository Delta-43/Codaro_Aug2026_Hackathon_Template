import type { ReactNode } from "react";
import { DomainProvider } from "@/lib/domain";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata = { title: "Booking Engine" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <DomainProvider>{children}</DomainProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
