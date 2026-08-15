import type { ReactNode } from "react";
import { AppProvider } from "@/context/app-context";
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
        <AppShell>{children}</AppShell>
      </AppProvider>
    </AuthGate>
  );
}
