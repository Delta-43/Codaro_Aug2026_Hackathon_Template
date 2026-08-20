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
import {
  CalendarClock,
  CalendarDays,
  CircleUser,
  Search,
  Send,
  ShoppingBag,
  Store,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";
import { useApp } from "@/context/app-context";
import { useCart } from "@/context/cart-context";
import { CartSheet } from "@/components/booking/cart-sheet";
import { browserTz } from "@/lib/format";
import { AvatarImg } from "@/components/avatar-img";
import { useAuth } from "@/lib/auth";
import { useUnreadCount } from "@/hooks/use-unread-count";
import { Button } from "@/components/ui/button";
import { SignOutButton } from "@/components/auth/sign-out-button";

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Section this tab lights up for, when it lands deeper than the section root.
   *  Settings opens `/account/settings` directly (same as the owner console's
   *  Settings tab) but stays lit on the profile page above it. */
  match?: string;
}

// Messaging is the permanent centre button (paper plane); the tabs stay balanced
// around it in both modes.
const SEARCH_TAB: Tab = { href: "/search", label: "Search", icon: Search };
const SERVICES_TAB: Tab = { href: "/provider", label: "Services", icon: Store };
const CALENDAR_TAB: Tab = { href: "/calendar", label: "Calendar", icon: CalendarClock };
const MESSAGING_TAB: Tab = { href: "/messages", label: "Messaging", icon: Send };
const BOOKINGS_TAB: Tab = { href: "/bookings", label: "Bookings", icon: CalendarDays };
const PROFILE_TAB: Tab = {
  href: "/account/settings",
  label: "Settings",
  icon: CircleUser,
  match: "/account",
};

// Marketplace: discovery leads, and Calendar is folded into Bookings.
const TABS: Tab[] = [SEARCH_TAB, SERVICES_TAB, MESSAGING_TAB, BOOKINGS_TAB, PROFILE_TAB];
// Single-business: no discovery (no Search). Rather than drop to four tabs, the
// availability Calendar un-merges back out of Bookings so five logical tabs
// remain with Messaging still centred.
const SINGLE_TABS: Tab[] = [
  SERVICES_TAB,
  CALENDAR_TAB,
  MESSAGING_TAB,
  BOOKINGS_TAB,
  PROFILE_TAB,
];

function isActive(pathname: string, tab: Tab): boolean {
  const href = tab.match ?? tab.href;
  return pathname === href || pathname.startsWith(href + "/");
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, ready, reload, activeProvider, singleBusiness, vertical } = useApp();
  const [retrying, setRetrying] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);

  // AuthGate has already established a session, so a finished boot with no
  // profile means `/me` failed. Boot degrades each leg independently rather than
  // hanging, which is right — but every downstream surface then substitutes a
  // default, and `user?.timezone ?? "UTC"` on the bookings, calendar and booking
  // detail pages would render real appointment times in the wrong zone with
  // nothing on screen to say so. Stop here instead, and offer a way out.
  const profileFailed = ready && !user;

  async function retryProfile() {
    setRetrying(true);
    try {
      // The WHOLE boot, not just the profile: if connectivity was down, tenancy,
      // vertical and capabilities fell back too, and recovering only the profile
      // would clear this screen while leaving those wrong until a hard reload.
      await reload();
    } catch {
      /* still failing — stay on this screen so the retry remains available */
    } finally {
      setRetrying(false);
    }
  }
  const { signOut } = useAuth();
  const unread = useUnreadCount();
  // The page name in the top bar glides the content back to the top when tapped.
  const scrollTop = () => window.scrollTo({ top: 0, behavior: "smooth" });

  // Both tab sets are module constants, so a plain switch on the mode is enough.
  // The bookings tab is the one nav label the pivot file names (`terms.bookings`);
  // the rest are app furniture, not domain vocabulary. Relabelled here rather
  // than in the module-level constants, which are built before any config load.
  const tabs = (singleBusiness ? SINGLE_TABS : TABS).map((tab) =>
    tab === BOOKINGS_TAB ? { ...tab, label: vertical.bookingNounPlural } : tab,
  );

  const active = tabs.find((t) => isActive(pathname, t)) ?? tabs[0];
  // The account section holds two pages under one tab: the profile page and the
  // Settings panel the tab itself opens.
  const heading = pathname === "/account" ? "Profile" : active.label;
  const showProviderContext = active.href === "/provider" || active.href === "/calendar";
  const badgeFor = (href: string) => (href === "/messages" ? unread : 0);

  return (
    <div className="min-h-dvh md:pl-60">
      {/* Desktop left drawer */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-card px-3 py-4 md:flex">
        <Link
          href="/"
          className={cn(
            buttonFx.heading,
            "mb-4 flex items-center gap-1.5 px-3 text-lg font-semibold tracking-tight",
          )}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-6 -translate-y-[9%]" />
          <span className="text-primary">Arbor</span>
        </Link>
        <nav className="flex flex-col gap-1">
          {tabs.map((tab) => (
            <NavItem
              key={tab.href}
              tab={tab}
              active={isActive(pathname, tab)}
              badge={badgeFor(tab.href)}
            />
          ))}
        </nav>
        <div className="mt-auto px-1">
          <SignOutButton className="w-full" onSignOut={signOut} />
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
          {showProviderContext && activeProvider ? (
            <p className="truncate text-xs text-muted-foreground">{activeProvider.name}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
        <CartButton onOpen={() => setCartOpen(true)} />
        <Link
          href="/account"
          className="group flex items-center gap-2 rounded-full py-1 pl-3 pr-1 transition-all hover:bg-primary/10 hover:text-primary"
          aria-label="Profile"
        >
          {/* Name first, avatar hard against the right edge — same order as the
              business shell's chip. */}
          <span className="max-w-[10rem] truncate text-base font-medium">{user?.displayName ?? "Account"}</span>
          <AvatarImg
            src={user?.avatarUrl}
            name={user?.displayName}
            alt=""
            className={cn("size-8 shrink-0", buttonFx.groupIcon)}
          />
        </Link>
        </div>
      </header>

      {/* Mobile compact header — the brand only (tapping it goes to the landing
          page), plus the cart, which is a control rather than a title and has
          nowhere else to live on mobile. No page name up here: the bottom tab
          bar already says which tab you are on. Each page keeps its own sr-only
          <h1>, so screen readers still get a title. */}
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
        <CartButton onOpen={() => setCartOpen(true)} />
      </header>

      {/* `capabilities.cart` — one basket for the whole app, so it survives
          moving between tabs while the customer picks the next thing. */}
      <CartSheet open={cartOpen} onClose={() => setCartOpen(false)} tz={browserTz()} />

      <main className="mx-auto w-full max-w-3xl px-4 pb-24 pt-2 md:px-6 md:pb-10">
        {profileFailed ? (
          <div className="mt-10 rounded-xl border border-border bg-card p-6 text-center">
            <h1 className="text-base font-semibold">We couldn&apos;t load your profile</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              You&apos;re signed in, but your account details didn&apos;t load. Times and
              bookings are hidden rather than shown in the wrong timezone.
            </p>
            <Button className="mt-4" onPress={retryProfile} isDisabled={retrying}>
              {retrying ? "Retrying…" : "Try again"}
            </Button>
          </div>
        ) : (
          children
        )}
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const activeTab = isActive(pathname, tab);
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

/** Basket entry point. Renders nothing where `capabilities.cart` is off, which
 *  is every deployment that does not sell more than one thing at a time. */
function CartButton({ onOpen }: { onOpen: () => void }) {
  const { capability } = useApp();
  const { items } = useCart();
  if (!capability("cart")) return null;
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Basket (${items.length})`}
      className={cn("relative grid size-9 place-items-center rounded-full transition-all hover:bg-primary/10 hover:text-primary", buttonFx.press)}
    >
      <ShoppingBag className="size-5" aria-hidden />
      {items.length ? (
        <span className="absolute -right-0.5 -top-0.5 grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
          {items.length}
        </span>
      ) : null}
    </button>
  );
}

/** Unread bubble pinned to the top-right of a nav icon. Renders nothing at 0. */
export function TabBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span
      aria-label={`${count} unread`}
      className="absolute -right-2 -top-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-none text-primary-foreground"
    >
      {count > 9 ? "9+" : count}
    </span>
  );
}
