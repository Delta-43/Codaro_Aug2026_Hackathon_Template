"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase, isAuthConfigured } from "@/lib/supabase";

/** App-wide auth state, backed by Supabase Auth. The signed-in user is verified,
 *  and their email is the booking owner the backend records. The access token is
 *  attached as `Authorization: Bearer <jwt>` on every backend call (see the API
 *  seam in @/api). */

/** Engine-neutral roles, labelled in the UI via the domain config's terms — never
 *  a hardcoded "Owner"/"Customer". Anything other than "owner" is a client. */
export type EngineRole = "owner" | "client";

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
  configured: boolean;
  signIn: (email: string, password: string) => Promise<{ role: EngineRole }>;
  signUp: (
    email: string,
    password: string,
    role?: EngineRole,
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
        const { data, error } = await supabase.auth.signUp({
          email: email.trim().toLowerCase(),
          password,
          options: role === "owner" ? { data: { role } } : undefined,
        });
        if (error) throw new Error(error.message);
        // With email confirmation on, signUp returns a user but no session.
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

/** The current session's access token, or null when logged out / unconfigured.
 *  The API seam calls this to attach the Bearer header. */
export async function getAccessToken(): Promise<string | null> {
  const supabase = getSupabase();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function requireSupabase() {
  const supabase = getSupabase();
  if (!supabase) {
    throw new Error(
      "Auth is not configured — set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.",
    );
  }
  return supabase;
}
