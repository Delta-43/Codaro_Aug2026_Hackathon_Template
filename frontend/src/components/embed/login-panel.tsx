"use client";

/**
 * The embed's auth gate fallback. Two ways in, both real Supabase sessions by
 * the time they reach the backend: <GuestOtpForm> (email + one-time code, no
 * password — the low-friction default for a first-time visitor) and, behind a
 * toggle, the same <AuthForm> the main app's /login page uses (for a
 * returning visitor who already has a password). No demo shortcuts, no
 * business-signup link, no landing branding. Rendered in place inside
 * the iframe; never navigates the top-level location.
 */
import { useState } from "react";
import { AuthForm } from "@/components/auth-form";
import { GuestOtpForm } from "@/components/embed/guest-otp-form";

export function EmbedLoginPanel() {
  const [showPasswordForm, setShowPasswordForm] = useState(false);

  return (
    <div className="flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <p className="mb-6 text-center text-sm text-muted-foreground">Sign in to book</p>
        {showPasswordForm ? (
          <>
            <AuthForm />
            <button
              type="button"
              className="mt-4 w-full text-center text-sm text-muted-foreground hover:text-foreground"
              onClick={() => setShowPasswordForm(false)}
            >
              Use an email code instead
            </button>
          </>
        ) : (
          <>
            <GuestOtpForm />
            <button
              type="button"
              className="mt-4 w-full text-center text-sm text-muted-foreground hover:text-foreground"
              onClick={() => setShowPasswordForm(true)}
            >
              Already have an account? Sign in
            </button>
          </>
        )}
        <p className="mt-6 text-center text-xs text-muted-foreground">Powered by Arbor</p>
      </div>
    </div>
  );
}
