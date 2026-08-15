"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase, isAuthConfigured } from "@/lib/supabase";

/** App-wide auth state, backed by Supabase Auth. This replaces the old
 *  localStorage "claimed email" identity (lib/session.ts): the signed-in user
 *  is now verified, and their email is the booking owner the backend records.
 *  See frontend/CLAUDE.md "Auth". */

/** Engine-neutral roles. The owner/client split is config-neutral here and only
 *  gets *labelled* through terms.admin / terms.client in the UI -- never a
 *  hardcoded "Owner"/"Customer". "owner" matches the backend's existing
 *  `actor: "owner"` concept. Anything else (including a user with no role set)
 *  is treated as a plain client. */
export type EngineRole = "owner" | "client";

/** Read the role a user registered with. We prefer `app_metadata.role` (set
 *  server-side / by an admin, so it's trustworthy) and fall back to
 *  `user_metadata.role` (what the sign-up form asks for). Defaults to "client".
 *
 *  NOTE: `user_metadata` is self-asserted at sign-up, so until the backend
 *  verifies the JWT and/or promotes the role into `app_metadata`, owner access
 *  is client-side gating only. See frontend/CLAUDE.md "Auth". */
export function roleOf(user: User | null | undefined): EngineRole {
  const raw =
    (user?.app_metadata as Record<string, unknown> | undefined)?.role ??
    (user?.user_metadata as Record<string, unknown> | undefined)?.role;
  return raw === "owner" ? "owner" : "client";
}

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  role: EngineRole;
  isOwner: boolean;
  loading: boolean;
  /** Present only when Supabase env is configured. */
  configured: boolean;
  signIn: (email: string, password: string) => Promise<{ role: EngineRole }>;
  signUp: (
    email: string,
    password: string,
    role?: EngineRole
  ) => Promise<{ needsConfirmation: boolean; role: EngineRole }>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setLoading(false);
      return;
    }
    // Seed from the persisted session, then track every change (login, logout,
    // token refresh) so the whole tree re-renders on auth transitions.
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const user = session?.user ?? null;
    const role = roleOf(user);
    return {
      session,
      user,
      role,
      isOwner: role === "owner",
      loading,
      configured: isAuthConfigured,
      async signIn(email, password) {
        const supabase = requireSupabase();
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim().toLowerCase(),
          password,
        });
        if (error) throw new Error(error.message);
        return { role: roleOf(data.user) };
      },
      async signUp(email, password, role: EngineRole = "client") {
        const supabase = requireSupabase();
        // The chosen role rides along in user_metadata (`options.data`). Only an
        // owner sign-up carries a non-default role; clients stay implicit.
        const { data, error } = await supabase.auth.signUp({
          email: email.trim().toLowerCase(),
          password,
          options: role === "owner" ? { data: { role } } : undefined,
        });
        if (error) throw new Error(error.message);
        // When email confirmation is on, signUp returns a user but no session;
        // the caller shows a "check your inbox" message instead of redirecting.
        return { needsConfirmation: !data.session, role };
      },
      async signOut() {
        const supabase = getSupabase();
        if (supabase) await supabase.auth.signOut();
        setSession(null);
      },
    };
  }, [session, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() must be used within <AuthProvider>");
  return ctx;
}

function requireSupabase() {
  const supabase = getSupabase();
  if (!supabase) {
    throw new Error(
      "Auth is not configured -- set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
    );
  }
  return supabase;
}
