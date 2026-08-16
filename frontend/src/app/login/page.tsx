"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

// Temporary Demo Mode (issue #23) — the seeded customer demo account. Lets us
// jump straight into a working space to review changes without creating an
// account or typing credentials. Remove before production; these are the same
// credentials the backend seeds (backend/seed.py) and the hint block advertises.
const DEMO_EMAIL = "demo@codaro.app";
const DEMO_PASSWORD = "Codaro-Demo-2026";

/**
 * Login / sign-up — the front door. Backed by Supabase Auth via useAuth(); on
 * success the whole app becomes available (the (app) group is gated on a
 * session). A signed-in visitor is bounced straight to the app.
 */
export default function LoginPage() {
  // useSearchParams needs a Suspense boundary for the production build.
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
  // Owners land in the owner area; everyone else at their requested destination.
  const destination = role === "owner" ? "/owner" : next;

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [asOwner, setAsOwner] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Already signed in (or just signed in) → leave the login screen. This is the
  // single redirect authority; it re-runs when the session/role resolves, so the
  // owner-vs-customer destination is always correct.
  useEffect(() => {
    if (!loading && session) router.replace(destination);
  }, [loading, session, destination, router]);

  // One-click entry with the seeded customer demo account. Goes through the
  // real Supabase sign-in (real JWT + RLS), so it's a shortcut, not a bypass —
  // the redirect useEffect above takes over once the session lands.
  async function enterDemoMode() {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await signIn(DEMO_EMAIL, DEMO_PASSWORD);
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
      // On success the session updates and the redirect useEffect (role-aware)
      // takes the user to /owner or their destination — no redirect here.
      if (mode === "signin") {
        await signIn(email, password);
      } else {
        const { needsConfirmation } = await signUp(
          email,
          password,
          asOwner ? "owner" : "client",
        );
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
          <h1 className="text-2xl font-semibold tracking-tight">Codaro</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin" ? "Sign in to continue" : "Create your account"}
          </p>
        </div>

        {!configured && (
          <p className="mb-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and
            NEXT_PUBLIC_SUPABASE_ANON_KEY.
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
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={asOwner}
                onChange={(e) => setAsOwner(e.target.checked)}
                className="size-4 rounded border-border accent-primary"
              />
              I&apos;m a business (owner account)
            </label>
          )}

          {error && (
            <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          {notice && (
            <p className="rounded-xl bg-primary/10 px-3 py-2 text-sm text-primary">{notice}</p>
          )}

          <Button type="submit" size="lg" isDisabled={busy || !configured} className="w-full">
            {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </Button>
        </form>

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

        {/* Temporary Demo Mode (issue #23) — developer entry at the foot of the
            card. "Demo Mode" does a one-click sign-in with the seeded customer
            demo account so changes can be reviewed without logging in. Remove
            before production. */}
        <div className="mt-6 border-t border-border pt-5 text-center">
          <p className="text-xs text-muted-foreground">
            For developers, check out our website
          </p>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onPress={enterDemoMode}
            isDisabled={busy || !configured}
            className="mt-3 w-full"
          >
            {busy ? "Please wait…" : "Demo Mode"}
          </Button>
        </div>
      </div>
    </div>
  );
}
