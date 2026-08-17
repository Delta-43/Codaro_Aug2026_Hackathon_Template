"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  const next = params.get("next") || "/search";
  const destination = role === "owner" ? "/owner" : next;

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && session) router.replace(destination);
  }, [loading, session, destination, router]);

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
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-sm rounded-3xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            <span className="text-foreground">Service</span>
            <span className="text-primary">.com</span>
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
            <Label htmlFor="email">Email</Label>
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
            <Label htmlFor="password">Password</Label>
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
                className="mt-0.5 size-4 shrink-0 rounded border-border accent-primary"
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

        {/* Full redirect to the dedicated business sign-in. */}
        <Link
          href="/login/business"
          className="mt-4 flex w-full items-center justify-center gap-1 text-base font-bold tracking-tight text-foreground transition-colors hover:text-primary"
        >
          I&apos;m a business!
          <ChevronRight className="size-4" aria-hidden />
        </Link>

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

        {/* Demo shortcuts — main page only (issue #23). */}
        <div className="mt-6 space-y-2 border-t border-border pt-5 text-center">
          <p className="text-xs text-muted-foreground">For developers, check out our website</p>
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
      </div>
    </div>
  );
}
