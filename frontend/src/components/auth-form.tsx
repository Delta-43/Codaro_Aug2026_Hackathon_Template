"use client";

/**
 * The email/password sign-in + sign-up form — just the form itself (inputs,
 * mode toggle, consent checkbox, submit, error/notice), no page chrome. Used
 * by both `/login` (wrapped in its own glass panel + demo-mode shortcuts +
 * business-signup link) and the embed's login panel (`components/embed/
 * login-panel.tsx`, behind its "Already have an account?" toggle) — one
 * implementation instead of two that could drift. Talks to `useAuth()`
 * directly; the caller just needs to be somewhere a session change causes a
 * re-render (both callers already are, via `AuthGate`/`/login`'s own
 * `useEffect` on `session`).
 */
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export function AuthForm({
  onModeChange,
}: {
  /** Notified whenever sign-in/sign-up mode toggles — for a caller (like
   *  /login) that wants to reflect it in surrounding chrome (a heading).
   *  Optional: the embed's login panel doesn't need it. */
  onModeChange?: (mode: "signin" | "signup") => void;
}) {
  const { configured, signIn, signUp } = useAuth();

  const [mode, setModeState] = useState<"signin" | "signup">("signin");
  function setMode(next: "signin" | "signup") {
    setModeState(next);
    onModeChange?.(next);
  }
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
    <div>
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
    </div>
  );
}
