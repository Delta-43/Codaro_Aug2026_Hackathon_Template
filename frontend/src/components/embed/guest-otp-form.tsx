"use client";

/**
 * The embed's primary auth path: email in, one-time code back, no password.
 * A verified Supabase session either way — `sendOtp`/`verifyOtp` create an
 * account on first use just like sign-up would, so nothing downstream
 * (create_booking's email check, profiles role-seeding, RLS) needs to know
 * this visitor never set a password.
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export function GuestOtpForm() {
  const { configured, sendOtp, verifyOtp } = useAuth();

  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSendCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await sendOtp(email);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send a code.");
    } finally {
      setBusy(false);
    }
  }

  async function onVerifyCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyOtp(email, code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (step === "code") {
    return (
      <form onSubmit={onVerifyCode} className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          We sent a code to <span className="font-medium text-foreground">{email}</span>.
        </p>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="otp-code">Code</Label>
          <Input
            id="otp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="123456"
          />
        </div>
        {error && (
          <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}
        <Button type="submit" size="lg" isDisabled={busy || !code} className="w-full">
          {busy ? "Checking…" : "Confirm"}
        </Button>
        <button
          type="button"
          className="text-center text-sm text-muted-foreground hover:text-foreground"
          onClick={() => {
            setStep("email");
            setCode("");
            setError(null);
          }}
        >
          Use a different email
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={onSendCode} className="flex flex-col gap-4">
      {!configured && (
        <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
        </p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="guest-email">Email</Label>
        <Input
          id="guest-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
      </div>
      {error && (
        <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      )}
      <Button type="submit" size="lg" isDisabled={busy || !configured} className="w-full">
        {busy ? "Sending…" : "Send code"}
      </Button>
    </form>
  );
}
