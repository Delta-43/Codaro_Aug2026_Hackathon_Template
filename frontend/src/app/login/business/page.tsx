"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

/**
 * Business sign-in — a dedicated page (not a drawer), reached from "I'm a
 * business!" on the main sign-in. Near-identical layout with a distinct look:
 * a darker grey card, gold "Business" flair, pink as the core action colour.
 * No demo shortcuts here — those live on the main customer page.
 */
export default function BusinessLoginPage() {
  return (
    <Suspense fallback={null}>
      <BusinessLoginForm />
    </Suspense>
  );
}

function BusinessLoginForm() {
  const { session, loading, role, configured, signIn, signUp } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/owner";
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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
      } else {
        const { needsConfirmation } = await signUp(email, password, "owner", agreed);
        if (needsConfirmation) {
          setNotice("Check your inbox to confirm your email, then sign in as a business.");
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
      <div
        className="w-full max-w-sm overflow-hidden rounded-3xl border border-amber-400/30 shadow-sm ring-1 ring-amber-400/20"
        // The business card is a grey surface ~20% darker than the customer card.
        style={{ backgroundColor: "color-mix(in oklch, var(--card) 80%, var(--muted-foreground))" }}
      >
        <div className="h-1.5 bg-gradient-to-r from-amber-300 to-amber-500" />
        <div className="p-6">
          <div className="mb-6 text-center">
            <span className="mx-auto mb-3 grid size-11 place-items-center rounded-2xl bg-amber-400/15 text-amber-600 dark:text-amber-400">
              <Building2 className="size-6" aria-hidden />
            </span>
            <h1 className="text-2xl font-semibold tracking-tight">
              <span className="text-foreground">Service</span>
              <span className="text-primary">.com</span>
              <span className="text-amber-600 dark:text-amber-400"> Business</span>
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === "signin" ? "Sign in to your business" : "Create your business account"}
            </p>
          </div>

          {!configured && (
            <p className="mb-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
            </p>
          )}

          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="biz-email">Business user email</Label>
              <Input
                id="biz-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@business.com"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="biz-password">Password</Label>
              <Input
                id="biz-password"
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
              {busy ? "Please wait…" : mode === "signin" ? "Sign in as a business user" : "Create business account"}
            </Button>
          </form>

          <div className="mt-4 text-center text-sm text-muted-foreground">
            {mode === "signin" ? (
              <>
                New to Business?{" "}
                <button
                  type="button"
                  className="font-medium text-primary hover:underline"
                  onClick={() => {
                    setMode("signup");
                    setError(null);
                    setNotice(null);
                  }}
                >
                  Create business account
                </button>
              </>
            ) : (
              <>
                Have a business account?{" "}
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

          <div className="mt-6 border-t border-border/60 pt-5 text-center">
            <Link
              href="/login"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-4" aria-hidden /> Sign in as a customer
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
