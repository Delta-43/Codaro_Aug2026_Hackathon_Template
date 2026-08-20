"use client";

/**
 * The business-mode shell — same responsive pattern and design language as the
 * customer AppShell (bottom tab bar under md, left drawer at md+), but a
 * completely different set of five tabs for the provider persona:
 *   Dashboard · Services · Requests · Calendar · Settings
 * The gold "Business" chip and verified-style avatar mark this as the business
 * account. Identity follows the active demo use case. The top-right avatar opens
 * the Profile view (desktop); a quick sign-out sits bottom-left of the drawer.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  CalendarDays,
  Rocket,
  Send,
  Settings,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";
import { useAuth } from "@/lib/auth";
import { useOwner } from "@/context/owner-context";
import { useUnreadCount } from "@/hooks/use-unread-count";
import { BusinessBadge } from "@/components/business/verified-badge";
import { TabBadge } from "@/components/app-shell";
import { SignOutButton } from "@/components/auth/sign-out-button";

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
}

// Messages is the permanent centre button (paper plane); Requests + Calendar
// collapse into Messages and Bookings so the persona keeps five balanced tabs.
const TABS: Tab[] = [
  { href: "/owner", label: "Dashboard", icon: Rocket },
  { href: "/owner/services", label: "Services", icon: SlidersHorizontal },
  { href: "/owner/messages", label: "Requests", icon: Send },
  { href: "/owner/bookings", label: "Bookings", icon: CalendarDays },
  { href: "/owner/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/owner") return pathname === "/owner";
  return pathname === href || pathname.startsWith(href + "/");
}

function Wordmark() {
  return (
    <span className="inline-flex items-center gap-1.5 text-lg font-semibold tracking-tight">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-6 -translate-y-[9%]" />
      <span className="text-primary">Arbor</span>
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
  const { activeProvider, scene, vocab } = useOwner();
  const unread = useUnreadCount();
  const businessName = activeProvider?.name ?? "Your business";
  // Same relabel as the customer shell: `terms.bookings` owns this one word, so
  // the owner console and the customer app never call it different things.
  const tabs = TABS.map((t) =>
    t.href === "/owner/bookings" ? { ...t, label: vocab.bookingNounPlural } : t,
  );
  const active = tabs.find((t) => isActive(pathname, t.href)) ?? tabs[0];
  const heading = pathname.startsWith("/owner/profile") ? "Profile" : active.label;
  const badgeFor = (href: string) => (href === "/owner/messages" ? unread : 0);
  // The page name in the top bar glides the content back to the top when tapped.
  const scrollTop = () => window.scrollTo({ top: 0, behavior: "smooth" });

  return (
    <div className="min-h-dvh md:pl-60">
      {/* Desktop left drawer */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-card px-3 py-4 md:flex">
        <Link href="/" className={cn(buttonFx.heading, "mb-4 flex items-center px-3")}>
          <Wordmark />
        </Link>
        <nav className="flex flex-col gap-1">
          {tabs.map((tab) => (
            <NavItem
              key={tab.href}
              tab={tab}
              active={isActive(pathname, tab.href)}
              badge={badgeFor(tab.href)}
            />
          ))}
        </nav>
        <div className="mt-auto px-1">
          <SignOutButton
            className="w-full"
            onSignOut={() => signOut().then(() => router.replace("/login"))}
          />
        </div>
      </aside>

      {/* Desktop top bar */}
      <header className="sticky top-0 z-20 hidden h-14 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur md:flex">
        <div className="min-w-0">
          <h1 className="min-w-0">
            <button
              type="button"
              onClick={scrollTop}
              className={cn(buttonFx.heading, "block max-w-full truncate text-lg font-semibold text-primary")}
            >
              {heading}
            </button>
          </h1>
          <p className="truncate text-xs text-muted-foreground">{businessName}</p>
        </div>
        <Link
          href="/owner/profile"
          className={cn(
            "group flex items-center gap-2 rounded-full py-1 pl-1 pr-3 transition-all hover:bg-primary/10 hover:text-primary",
            buttonFx.press,
          )}
          aria-label="Profile"
        >
          {/* activeProvider comes from useOwner, so an avatar edit re-renders here. */}
          <BusinessBadge avatarUrl={activeProvider?.avatarUrl} scene={scene} size="sm" />
          <span className="max-w-[10rem] truncate text-base font-medium">{businessName}</span>
        </Link>
      </header>

      {/* Mobile compact header — brand (to the landing page) on the left, the
          current page name on the right. The page's own <h1> is sr-only on
          mobile, so this is the single visible page title (no duplicate). */}
      <header className="sticky top-0 z-20 flex h-12 items-center justify-between gap-2 border-b border-border bg-background/85 px-4 backdrop-blur pt-[env(safe-area-inset-top)] md:hidden">
        <Link
          href="/"
          className={cn(
            buttonFx.heading,
            "flex shrink-0 items-center gap-1.5 text-base font-bold tracking-tight text-primary",
          )}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-6 -translate-y-[9%]" />
          Arbor
        </Link>
        <span className="flex min-w-0 items-baseline justify-end gap-2 text-lg font-semibold">
          <button
            type="button"
            onClick={scrollTop}
            className={cn(buttonFx.heading, "shrink-0 origin-right text-primary")}
          >
            {heading}
          </button>
          <span className="min-w-0 shrink truncate font-normal text-muted-foreground">{businessName}</span>
        </span>
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 pb-24 pt-3 md:px-6 md:pb-10">{children}</main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const activeTab = isActive(pathname, tab.href);
          const badge = badgeFor(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={activeTab ? "page" : undefined}
              className={cn(
                "group flex min-h-[52px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors",
                activeTab ? "text-primary" : "text-muted-foreground hover:text-primary",
              )}
            >
              <span className="relative origin-center transition-transform duration-200 ease-out group-hover:scale-110">
                <Icon className="size-5" aria-hidden />
                <TabBadge count={badge} />
              </span>
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function NavItem({ tab, active, badge = 0 }: { tab: Tab; active: boolean; badge?: number }) {
  const Icon = tab.icon;
  return (
    <Link
      href={tab.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex min-h-[44px] items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-primary/10 hover:text-primary",
      )}
    >
      <span className="relative origin-center transition-transform duration-200 ease-out group-hover:scale-110">
        <Icon className="size-4" aria-hidden />
        <TabBadge count={badge} />
      </span>
      {tab.label}
    </Link>
  );
}
