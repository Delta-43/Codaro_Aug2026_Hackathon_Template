// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

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
import { InlineMessage } from "@/components/ui/inline-message";
import { DemoLogins } from "@/components/demo-logins";

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
  const { session, loading, role, roleReady, configured, signIn, signUp } = useAuth();
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

  // `next` is attacker-controllable via the query string, and it feeds
  // router.replace below — so only honour a same-origin absolute PATH. A crafted
  // `?next=https://evil.com` (or the protocol-relative `//evil.com`) would
  // otherwise turn the post-login redirect into an open redirect / phishing hop.
  const rawNext = params.get("next");
  const safeNext =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : null;
  const next = safeNext || (singleBusiness ? "/provider" : "/search");
  // Either door takes either account: one account holds both personas, so a
  // business signing in here is sent to its own home rather than turned away.
  const destination = role === "owner" ? "/owner" : next;

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // `roleReady` as well as `tenancyReady`: `destination` branches on the role,
  // and the trusted role lands a beat after the session. Redirecting early would
  // send a business owner into the customer app and then bounce them.
  useEffect(() => {
    if (!loading && session && tenancyReady && roleReady) router.replace(destination);
  }, [loading, session, tenancyReady, roleReady, role, destination, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // The redirect effect above routes on the resolved role once it lands.
      if (mode === "signin") await signIn(email, password);
      else await signUp(email, password, "client", agreed);
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
              className="inline-flex items-center gap-1.5 origin-center text-primary transition-transform duration-200 ease-out hover:scale-110"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/arbor-mark-7d.png" alt="" aria-hidden className="size-7 -translate-y-[9%]" />
              Arbor
            </Link>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin" ? "Sign in to continue" : "Create your account"}
          </p>
        </div>

        {!configured && (
          <InlineMessage live="polite" className="mb-4 rounded-2xl">
            Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
          </InlineMessage>
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
            <InlineMessage className="rounded-2xl">{error}</InlineMessage>
          )}

          <Button
            type="submit"
            size="lg"
            isDisabled={busy || !configured || (mode === "signup" && !agreed)}
            className="w-full"
          >
            {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <DemoLogins disabled={busy} onError={setError} />

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
