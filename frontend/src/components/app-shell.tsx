"use client";

/**
 * One responsive shell for the whole app — no separate mobile app, no
 * user-agent sniffing. Breakpoint at 768px (Tailwind `md`):
 *  - below md: fixed bottom tab bar (5 items, icon + label), compact sticky
 *    header, content scrolls under it.
 *  - md and up: persistent ~240px left drawer with the same 5 items, plus a
 *    top bar with the page title and an avatar that navigates to Account.
 * Touch targets ≥44px; safe-area insets respected on mobile.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, CircleUser, Search, Store, Ticket, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useApp } from "@/context/app-context";

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
}

const TABS: Tab[] = [
  { href: "/search", label: "Search", icon: Search },
  { href: "/provider", label: "Services", icon: Store },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/bookings", label: "Bookings", icon: Ticket },
  { href: "/account", label: "Account", icon: CircleUser },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, activeProvider } = useApp();

  const active = TABS.find((t) => isActive(pathname, t.href)) ?? TABS[0];
  const showProviderContext = active.href === "/provider" || active.href === "/calendar";

  return (
    <div className="min-h-dvh md:pl-60">
      {/* Desktop left drawer */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-card px-3 py-4 md:flex">
        <Link href="/search" className="mb-4 px-3 text-lg font-semibold tracking-tight">
          <span className="text-foreground">Service</span>
          <span className="text-primary">.com</span>
        </Link>
        <nav className="flex flex-col gap-1">
          {TABS.map((tab) => (
            <NavItem key={tab.href} tab={tab} active={isActive(pathname, tab.href)} />
          ))}
        </nav>
      </aside>

      {/* Desktop top bar */}
      <header className="sticky top-0 z-20 hidden h-14 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur md:flex">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{active.label}</h1>
          {showProviderContext && activeProvider ? (
            <p className="truncate text-xs text-muted-foreground">{activeProvider.name}</p>
          ) : null}
        </div>
        <Link
          href="/account"
          className="flex items-center gap-2 rounded-full py-1 pl-1 pr-3 hover:bg-muted"
          aria-label="Account"
        >
          <Avatar url={user?.avatarUrl} name={user?.displayName} />
          <span className="max-w-[10rem] truncate text-sm">{user?.displayName ?? "Account"}</span>
        </Link>
      </header>

      {/* Mobile compact header */}
      <header className="sticky top-0 z-20 flex h-12 items-center border-b border-border bg-background/85 px-4 backdrop-blur pt-[env(safe-area-inset-top)] md:hidden">
        <span className="truncate text-sm font-semibold">
          {active.label}
          {showProviderContext && activeProvider ? (
            <span className="ml-2 font-normal text-muted-foreground">{activeProvider.name}</span>
          ) : null}
        </span>
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 pb-24 pt-2 md:px-6 md:pb-10">{children}</main>

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

function Avatar({ url, name }: { url?: string; name?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url ?? ""}
      alt={name ?? ""}
      className="size-8 rounded-full bg-muted object-cover"
    />
  );
}
