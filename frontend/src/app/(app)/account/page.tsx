"use client";

/**
 * Tab 5 — Account. Profile editing (name / email / timezone via updateUser),
 * an identity-only note (no password auth in this app), a stubbed payment row,
 * the demo panel (vertical switch + reseed), and a help/version footer.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CreditCard } from "lucide-react";
import { useApp } from "@/context/app-context";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { ProfileForm } from "@/components/account/profile-form";
import { VERTICAL_IDS, VERTICALS } from "@/config/verticals";
import type { VerticalId } from "@/types/domain";

const APP_VERSION = "demo build";

export default function AccountPage() {
  const { ready, user, verticalId, switchVertical, reseed } = useApp();
  const { signOut } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState<null | "switch" | "reset">(null);

  async function onSignOut() {
    await signOut();
    router.replace("/login");
  }

  async function onSwitch(id: VerticalId) {
    if (id === verticalId || pending) return;
    setPending("switch");
    try {
      await switchVertical(id);
      router.push("/search"); // reset navigation on vertical change
    } finally {
      setPending(null);
    }
  }

  async function onReset() {
    if (pending) return;
    setPending("reset");
    try {
      await reseed();
      router.push("/search");
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="space-y-8 py-6">
      <header className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={user?.avatarUrl ?? ""}
          alt=""
          className="size-14 rounded-full bg-muted object-cover"
        />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {user?.displayName ?? "…"}
            {user?.verified ? (
              <span className="ml-2 align-middle text-xs font-medium text-primary">Verified</span>
            ) : null}
          </h1>
          <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
        </div>
        <Button variant="outline" size="sm" onPress={onSignOut}>
          Sign out
        </Button>
      </header>

      {/* Profile */}
      {ready && user ? (
        <ProfileForm user={user} />
      ) : (
        <Skeleton className="h-72 w-full" />
      )}

      {/* Payment method (stub) */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">Payment method</h2>
        <div className="mt-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-lg bg-muted text-muted-foreground">
              <CreditCard className="size-4" aria-hidden />
            </div>
            <p className="text-sm text-muted-foreground">No payment method on file</p>
          </div>
          <Button variant="outline" size="sm" isDisabled>
            Add
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Payments are out of scope for this demo — bookings are confirmed without charge.
        </p>
      </div>

      {/* Demo panel */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">Demo</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Switching vertical reseeds the store and resets navigation.
        </p>

        <div className="mt-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Vertical</p>
          <div className="flex flex-wrap gap-2">
            {VERTICAL_IDS.map((id) => (
              <Button
                key={id}
                variant={id === verticalId ? "default" : "outline"}
                size="sm"
                isDisabled={pending !== null}
                onPress={() => onSwitch(id)}
              >
                {VERTICALS[id].label}
              </Button>
            ))}
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button variant="secondary" size="sm" isDisabled={pending !== null} onPress={onReset}>
            {pending === "reset" ? "Resetting…" : "Reset demo data"}
          </Button>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          Provider-side availability management is planned for a later iteration.
        </p>
      </div>

      {/* Help / version */}
      <footer className="flex items-center justify-between gap-3 px-1 text-xs text-muted-foreground">
        <span>Codaro · {APP_VERSION}</span>
        <span>State is in-memory — a refresh resets to seed.</span>
      </footer>
    </section>
  );
}
