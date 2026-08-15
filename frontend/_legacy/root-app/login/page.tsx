"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Term, useDomain } from "@/lib/domain";
import { useAuth } from "@/lib/auth";

/** Email/password login + sign-up for clients, backed by Supabase Auth. Retires
 *  the old "type your email, no password" identify form on the landing page.
 *  Copy stays config-driven -- the client role is labelled via terms.client. */
export default function LoginPage() {
  const { copy, terms } = useDomain();
  const { user, isOwner, loading, configured, signIn, signUp } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Already signed in? Skip to the right dashboard for the role.
  useEffect(() => {
    if (!loading && user) router.replace(isOwner ? "/owner" : "/dashboard");
  }, [loading, user, isOwner, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "login") {
        const { role } = await signIn(email, password);
        router.replace(role === "owner" ? "/owner" : "/dashboard");
      } else {
        const { needsConfirmation } = await signUp(email, password);
        if (needsConfirmation) {
          setNotice("Check your inbox to confirm your email, then sign in.");
          setMode("login");
        } else {
          router.replace("/dashboard");
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-2xl font-semibold">
        {mode === "login" ? "Sign in" : "Create account"}
      </h1>
      <p className="mt-1 text-sm text-gray-600">
        {mode === "login" ? (
          <>
            Sign in to manage your <Term term="booking" plural />.
          </>
        ) : (
          <>
            Sign up as a <Term term="client" /> to start booking.
          </>
        )}
      </p>

      {!configured && (
        <p role="alert" className="mt-4 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Auth is not configured. Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
          <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in <code>frontend/.env.local</code>.
        </p>
      )}

      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="Email"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          type="password"
          required
          minLength={6}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          aria-label="Password"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={busy || !configured}
          className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "..." : mode === "login" ? "Sign in" : "Sign up"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p className="mt-4 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
          {notice}
        </p>
      )}

      <p className="mt-6 text-sm text-gray-600">
        {mode === "login" ? (
          <>
            No account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError(null);
                setNotice(null);
              }}
              className="underline hover:text-gray-900"
            >
              Sign up
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
                setNotice(null);
              }}
              className="underline hover:text-gray-900"
            >
              Sign in
            </button>
          </>
        )}
      </p>

      <p className="mt-8 border-t border-gray-100 pt-4 text-sm text-gray-600">
        Are you {/^[aeiou]/i.test(terms.admin) ? "an" : "a"} <Term term="admin" />?{" "}
        <Link href="/owner/register" className="underline hover:text-gray-900">
          Register as a professional
        </Link>
      </p>

      <p className="mt-6 text-xs text-gray-400">
        <Link href="/" className="underline hover:text-gray-600">
          &larr; Back to {copy.landingTitle ?? "home"}
        </Link>
      </p>
    </main>
  );
}
