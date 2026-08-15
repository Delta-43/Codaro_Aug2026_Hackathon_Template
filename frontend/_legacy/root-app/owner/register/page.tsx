"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Term, useDomain } from "@/lib/domain";
import { useAuth } from "@/lib/auth";

/** Register as a professional -- i.e. the owner role (terms.admin). Signs up
 *  through Supabase Auth carrying the owner role in user_metadata, then lands on
 *  the owner dashboard. Clients register from /login instead; this page only
 *  creates owner accounts. Copy is config-driven via terms.admin. */
export default function ProfessionalRegisterPage() {
  const { terms } = useDomain();
  const { user, isOwner, loading, configured, signUp } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Already an owner? Skip to the dashboard. A signed-in client stays here and
  // can create a separate professional account.
  useEffect(() => {
    if (!loading && user && isOwner) router.replace("/owner");
  }, [loading, user, isOwner, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { needsConfirmation } = await signUp(email, password, "owner");
      if (needsConfirmation) {
        setNotice("Check your inbox to confirm your email, then sign in.");
      } else {
        router.replace("/owner");
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
        Register as {aOrAn(terms.admin)} <Term term="admin" />
      </h1>
      <p className="mt-1 text-sm text-gray-600">
        Create a professional account to publish <Term term="resources" /> and open{" "}
        <Term term="slot" plural />.
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
          autoComplete="new-password"
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
          {busy ? "..." : `Create ${terms.admin} account`}
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
        Already have an account?{" "}
        <Link href="/login" className="underline hover:text-gray-900">
          Sign in
        </Link>
      </p>
      <p className="mt-2 text-sm text-gray-600">
        Just want to book?{" "}
        <Link href="/login" className="underline hover:text-gray-900">
          Register as {aOrAn(terms.client)} <Term term="client" />
        </Link>
      </p>

      <p className="mt-8 text-xs text-gray-400">
        <Link href="/" className="underline hover:text-gray-600">
          &larr; Back to home
        </Link>
      </p>
    </main>
  );
}

/** "a"/"an" for a term, so labels read naturally whatever the domain calls the
 *  role (an "Owner", a "Doctor"). */
function aOrAn(word: string): string {
  return /^[aeiou]/i.test(word) ? "an" : "a";
}
