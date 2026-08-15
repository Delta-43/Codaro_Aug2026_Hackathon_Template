"use client";

// Tab 5 — Account. Full profile editing (display name, timezone), stubbed
// payment row, and help/version land in Phase 8. The demo panel is wired now
// because it only needs Button + context and makes the whole app demoable
// across verticals immediately.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/context/app-context";
import { Button } from "@/components/ui/button";
import { VERTICAL_IDS, VERTICALS } from "@/config/verticals";
import type { VerticalId } from "@/types/domain";

export default function AccountPage() {
  const { user, verticalId, switchVertical, reseed } = useApp();
  const router = useRouter();
  const [pending, setPending] = useState<null | "switch" | "reset">(null);

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
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {user?.displayName ?? "…"}
            {user?.verified ? (
              <span className="ml-2 align-middle text-xs font-medium text-primary">Verified</span>
            ) : null}
          </h1>
          <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
        </div>
      </header>

      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Profile editing, timezone, and payment method arrive in Phase 8.
      </p>

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
    </section>
  );
}
