"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { getTenancy } from "@/api";
import { Button } from "@/components/ui/button";
import { AuthForm } from "@/components/auth-form";
import { SceneBackground } from "@/components/landing/scene-background";
import { GlassPanel } from "@/components/landing/scroll-reveal";
import { useAuth } from "@/lib/auth";

// Temporary Demo Mode (issue #23) — the seeded demo accounts. One-click entry
// into a working space, no credentials to type. These live on the main
// (customer) sign-in only; the business sign-in page has no demo shortcuts.
const DEMO_USER = { email: "demo@codaro.app", password: "Codaro-Demo-2026" };
const DEMO_BUSINESS = { email: "owner@codaro.app", password: "Codaro-Owner-2026" };

/**
 * Customer sign-in — the default front door. Business owners tap "I'm a
 * business!" to go to the dedicated business sign-in page (`/login/business`).
 */
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { session, loading, role, configured, signIn } = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  // Single-business pivot: no public "become a business" signup, and customers
  // land on the catalog rather than the (nonexistent) discovery search. Tenancy
  // resolves async, so `tenancyReady` gates the redirect below — otherwise an
  // already-authenticated customer would redirect to the stale "/search" default
  // before tenancy loads and then bounce to "/provider" (a visible flash).
  const [singleBusiness, setSingleBusiness] = useState(false);
  const [tenancyReady, setTenancyReady] = useState(false);
  useEffect(() => {
    getTenancy()
      .then((t) => setSingleBusiness(t.mode === "single"))
      .catch(() => setSingleBusiness(false))
      .finally(() => setTenancyReady(true));
  }, []);

  const next = params.get("next") || (singleBusiness ? "/provider" : "/search");
  const destination = role === "owner" ? "/owner" : next;

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && session && tenancyReady) router.replace(destination);
  }, [loading, session, tenancyReady, destination, router]);

  async function enterDemoMode(account: { email: string; password: string }) {
    setError(null);
    setBusy(true);
    try {
      await signIn(account.email, account.password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center px-4 py-10">
      {/* Same liquid-glass scene as the landing page, so the sign-in plate frosts
          the backdrop identically. */}
      <SceneBackground />
      <div className="w-full max-w-sm">
      <GlassPanel className="p-6">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            <Link
              href="/"
              className="inline-block origin-center text-primary transition-transform duration-200 ease-out hover:scale-110"
            >
              Arbor
            </Link>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin" ? "Sign in to continue" : "Create your account"}
          </p>
        </div>

        <AuthForm onModeChange={setMode} />

        {/* Full redirect to the dedicated business sign-in. Hidden in
            single-business mode — there is no public business onboarding (the
            operator console is reached directly, not advertised to customers). */}
        {!singleBusiness ? (
          <Link
            href="/login/business"
            className="mt-4 flex w-full items-center justify-center gap-1 text-base font-bold tracking-tight text-foreground transition-colors hover:text-primary"
          >
            I&apos;m a business!
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : null}

        {/* Demo shortcuts — main page only (issue #23). Both shortcuts stay
            available even in single-business mode: the business one logs into the
            seeded owner account to show the operator console (public business
            *signup* is what's hidden, not the demo login). */}
        <div className="mt-6 space-y-2 border-t border-border pt-5 text-center">
          <p className="text-xs text-muted-foreground">For developers, check out our website</p>
          {error && (
            <p className="rounded-xl bg-destructive/10 px-3 py-2 text-left text-sm text-destructive">
              {error}
            </p>
          )}
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onPress={() => enterDemoMode(DEMO_USER)}
            isDisabled={busy || !configured}
            className="w-full"
          >
            {busy ? "Please wait…" : "Demo Mode for Users"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onPress={() => enterDemoMode(DEMO_BUSINESS)}
            isDisabled={busy || !configured}
            className="w-full"
          >
            {busy ? "Please wait…" : "Demo Mode for Businesses"}
          </Button>
        </div>
      </GlassPanel>
      </div>
    </div>
  );
}
