"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { SceneBackground } from "@/components/landing/scene-background";
import { GlassPanel } from "@/components/landing/scroll-reveal";
import { useAuth } from "@/lib/auth";

/**
 * Business sign-in — a dedicated page reached from "I'm a business!" on the main
 * sign-in. Shares the exact glass-plate layout of the customer login page; the
 * only distinction is a gold "Business" tagline next to the Arbor mark and the
 * owner-role auth behaviour.
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
    <div className="relative flex min-h-dvh items-center justify-center px-4 py-10">
      {/* Same liquid-glass scene as the customer sign-in, so the two plates frost
          the backdrop identically. */}
      <SceneBackground />
      <div className="w-full max-w-sm">
      <GlassPanel className="p-6">
        <div className="mb-6 text-center">
          <h1 className="flex items-center justify-center gap-2 text-2xl font-semibold tracking-tight">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 origin-center text-primary transition-transform duration-200 ease-out hover:scale-110"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-7 -translate-y-[9%]" />
              Arbor
            </Link>
            <span className="-translate-y-px rounded-full bg-amber-400/15 px-2 py-1 text-[0.625rem] font-semibold uppercase leading-none tracking-[0.08em] text-amber-600 dark:text-amber-400">
              Business
            </span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin" ? "Sign in to continue" : "Create your business account"}
          </p>
        </div>

        {!configured && (
          <p className="mb-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
          </p>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="biz-email" className={cn("justify-center", buttonFx.link)}>Email</Label>
            <Input
              id="biz-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="biz-password" className={cn("justify-center", buttonFx.link)}>Password</Label>
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
            {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create business account"}
          </Button>
        </form>

        {/* Inverse of the customer page's "I'm a business!" — back to the
            customer sign-in. */}
        <Link
          href="/login"
          className="mt-4 flex w-full items-center justify-center gap-1 text-base font-bold tracking-tight text-foreground transition-colors hover:text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden />
          I&apos;m a customer!
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
                Create a business account
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
      </GlassPanel>
      </div>
    </div>
  );
}
