"use client";

/**
 * The business-mode shell — same responsive pattern and design language as the
 * customer AppShell (bottom tab bar under md, left drawer at md+), but a
 * completely different set of five tabs for the provider persona:
 *   Dashboard · Services · Requests · Calendar · Profile
 * The gold "Business" chip and verified-style avatar mark this as the business
 * account. Identity follows the active demo use case. The top-right avatar opens
 * Settings (desktop); a quick sign-out sits bottom-left of the drawer.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  CalendarDays,
  CircleCheckBig,
  CircleUser,
  Rocket,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useOwner } from "@/context/owner-context";
import { VerifiedScene } from "@/components/business/verified-badge";
import { Button } from "@/components/ui/button";

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
}

const TABS: Tab[] = [
  { href: "/owner", label: "Dashboard", icon: Rocket },
  { href: "/owner/services", label: "Services", icon: SlidersHorizontal },
  { href: "/owner/requests", label: "Requests", icon: CircleCheckBig },
  { href: "/owner/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/owner/profile", label: "Profile", icon: CircleUser },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/owner") return pathname === "/owner";
  return pathname === href || pathname.startsWith(href + "/");
}

function Wordmark() {
  return (
    <span className="text-lg font-semibold tracking-tight">
      <span className="text-foreground">Service</span>
      <span className="text-primary">.com</span>
      <span className="ml-2 rounded-full bg-amber-400/15 px-2 py-0.5 align-middle text-xs font-medium text-amber-600 dark:text-amber-400">
        Business
      </span>
    </span>
  );
}

export function BusinessShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut } = useAuth();
  const { activeProvider, scene } = useOwner();
  const businessName = activeProvider?.name ?? "Your business";
  const active = TABS.find((t) => isActive(pathname, t.href)) ?? TABS[0];
  const heading = pathname.startsWith("/owner/settings") ? "Settings" : active.label;

  return (
    <div className="min-h-dvh md:pl-60">
      {/* Desktop left drawer */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-card px-3 py-4 md:flex">
        <Link href="/owner" className="mb-4 px-1">
          <Wordmark />
        </Link>
        <nav className="flex flex-col gap-1">
          {TABS.map((tab) => (
            <NavItem key={tab.href} tab={tab} active={isActive(pathname, tab.href)} />
          ))}
        </nav>
        <div className="mt-auto px-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onPress={() => signOut().then(() => router.replace("/login"))}
          >
            Sign out
          </Button>
        </div>
      </aside>

      {/* Desktop top bar */}
      <header className="sticky top-0 z-20 hidden h-14 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur md:flex">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{heading}</h1>
          <p className="truncate text-xs text-muted-foreground">{businessName}</p>
        </div>
        <Link
          href="/owner/settings"
          className="flex items-center gap-2 rounded-full py-1 pl-1 pr-3 hover:bg-muted"
          aria-label="Settings"
        >
          <VerifiedScene scene={scene} size="sm" />
          <span className="max-w-[10rem] truncate text-sm">{businessName}</span>
        </Link>
      </header>

      {/* Mobile compact header */}
      <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-border bg-background/85 px-4 backdrop-blur pt-[env(safe-area-inset-top)] md:hidden">
        <span className="truncate text-sm font-semibold">
          {heading}
          <span className="ml-2 font-normal text-muted-foreground">{businessName}</span>
        </span>
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 pb-24 pt-3 md:px-6 md:pb-10">{children}</main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const activeTab = isActive(pathname, tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={activeTab ? "page" : undefined}
              className={cn(
                "flex min-h-[52px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors",
                activeTab ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-5" aria-hidden />
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function NavItem({ tab, active }: { tab: Tab; active: boolean }) {
  const Icon = tab.icon;
  return (
    <Link
      href={tab.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-h-[44px] items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="size-4" aria-hidden />
      {tab.label}
    </Link>
  );
}
