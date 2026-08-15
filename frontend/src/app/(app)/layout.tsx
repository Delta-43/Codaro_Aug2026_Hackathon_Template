import type { ReactNode } from "react";
import { AppProvider } from "@/context/app-context";
import { AppShell } from "@/components/app-shell";

/**
 * Wraps every real route in the app-wide context and the responsive shell.
 * This layout stays mounted across tab navigation, so the locked-in provider
 * and selected service survive moving between tabs.
 */
export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <AppProvider>
      <AppShell>{children}</AppShell>
    </AppProvider>
  );
}
