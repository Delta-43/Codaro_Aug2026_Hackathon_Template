import type { ReactNode } from "react";
import { AppProvider } from "@/context/app-context";
import { CartProvider } from "@/context/cart-context";
import { AppShell } from "@/components/app-shell";
import { AuthGate } from "@/components/auth-gate";

/**
 * Wraps every real route in a session gate, the app-wide context, and the
 * responsive shell. The gate redirects anonymous visitors to /login; the
 * context/shell stay mounted across tab navigation, so the locked-in provider
 * and selected service survive moving between tabs.
 */
export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AppProvider>
        {/* The basket is app-wide (`capabilities.cart`): it has to survive
            moving between the calendar, search and the bookings tab. */}
        <CartProvider>
          <AppShell>{children}</AppShell>
        </CartProvider>
      </AppProvider>
    </AuthGate>
  );
}
