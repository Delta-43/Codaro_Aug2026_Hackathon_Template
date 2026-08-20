"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { getTenancy } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
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
  const { session, loading, role, configured, signIn, signUp } = useAuth();
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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && session && tenancyReady) router.replace(destination);
  }, [loading, session, tenancyReady, destination, router]);

  async function enterDemoMode(account: { email: string; password: string }) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await signIn(account.email, account.password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
      } else {
        const { needsConfirmation } = await signUp(email, password, "client", agreed);
        if (needsConfirmation) {
          setNotice("Check your inbox to confirm your email, then sign in.");
          setMode("signin");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
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

        {!configured && (
          <p className="mb-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
          </p>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email" className={cn("justify-center", buttonFx.link)}>Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className={cn("justify-center", buttonFx.link)}>Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {mode === "signup" && (
            <label className="flex items-start gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className={cn(
                  "mt-0.5 size-4 shrink-0 cursor-pointer rounded border-border accent-primary transition-transform",
                  buttonFx.press,
                )}
              />
              <span>
                I agree to the{" "}
                <Link href="/privacy" target="_blank" className="font-medium text-primary hover:underline">
                  data handling &amp; privacy policy
                </Link>
                .
              </span>
            </label>
          )}

          {error && (
            <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
          )}
          {notice && <p className="rounded-xl bg-primary/10 px-3 py-2 text-sm text-primary">{notice}</p>}

          <Button
            type="submit"
            size="lg"
            isDisabled={busy || !configured || (mode === "signup" && !agreed)}
            className="w-full"
          >
            {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </Button>
        </form>

        {/* Full redirect to the dedicated business sign-in. Hidden in
            single-business mode — there is no public business onboarding (the
            operator console is reached directly, not advertised to customers). */}
        {!singleBusiness ? (
          <Link
            href="/login/business"
            className="group mt-4 flex w-full items-center justify-center gap-1 text-base font-bold tracking-tight text-foreground transition-colors hover:text-primary"
          >
            I&apos;m a business!
            <ChevronRight className={cn("size-4", buttonFx.chevron)} aria-hidden />
          </Link>
        ) : null}

        <div className="mt-4 text-center text-sm text-muted-foreground">
          {mode === "signin" ? (
            <>
              New here?{" "}
              <button
                type="button"
                className="font-medium text-primary hover:underline"
                onClick={() => {
                  setMode("signup");
                  setError(null);
                  setNotice(null);
                }}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Have an account?{" "}
              <button
                type="button"
                className="font-medium text-primary hover:underline"
                onClick={() => {
                  setMode("signin");
                  setError(null);
                  setNotice(null);
                }}
              >
                Sign in
              </button>
            </>
          )}
        </div>

        {/* Demo shortcuts — main page only (issue #23). Both shortcuts stay
            available even in single-business mode: the business one logs into the
            seeded owner account to show the operator console (public business
            *signup* is what's hidden, not the demo login). */}
        <div className="mt-6 space-y-2 border-t border-border pt-5 text-center">
          <p className="text-xs text-muted-foreground">For developers, check out our website</p>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onPress={() => enterDemoMode(DEMO_USER)}
            isDisabled={busy || !configured}
            className="w-full hover:border-primary hover:bg-primary/10 hover:text-primary"
          >
            {busy ? "Please wait…" : "Demo Mode for Users"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onPress={() => enterDemoMode(DEMO_BUSINESS)}
            isDisabled={busy || !configured}
            className="w-full hover:border-primary hover:bg-primary/10 hover:text-primary"
          >
            {busy ? "Please wait…" : "Demo Mode for Businesses"}
          </Button>
        </div>
      </GlassPanel>
      </div>
    </div>
  );
}
