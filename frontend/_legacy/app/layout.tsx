import type { ReactNode } from "react";
import { DomainProvider } from "@/lib/domain";
import "./globals.css";

export const metadata = { title: "Booking Engine" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <DomainProvider>{children}</DomainProvider>
      </body>
    </html>
  );
}
