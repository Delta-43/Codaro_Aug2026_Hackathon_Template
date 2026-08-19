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

function roleOf(user: User | null | undefined): EngineRole {
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
    consent?: boolean,
  ) => Promise<{ needsConfirmation: boolean; role: EngineRole }>;
  signOut: () => Promise<void>;
  /** Passwordless entry point: emails a one-time code. No account exists yet?
   *  one is created on verification — same identity model as signUp/signIn,
   *  just a different way in. Used by the embed's guest-checkout path. */
  sendOtp: (email: string) => Promise<void>;
  /** Exchanges the code from sendOtp for a session. */
  verifyOtp: (email: string, token: string) => Promise<void>;
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
      async signUp(email, password, role: EngineRole = "client", consent = false) {
        const supabase = requireSupabase();
        // GDPR: record the explicit consent the sign-up form gated on, alongside
        // the role, in the user's metadata. Owners also carry their role.
        const data = {
          ...(role === "owner" ? { role } : {}),
          gdpr_consent: consent,
          gdpr_consent_at: consent ? new Date().toISOString() : null,
        };
        const { data: result, error } = await supabase.auth.signUp({
          email: email.trim().toLowerCase(),
          password,
          options: { data },
        });
        if (error) throw new Error(error.message);
        // With email confirmation on, signUp returns a user but no session.
        return { needsConfirmation: !result.session, role };
      },
      async signOut() {
        const supabase = getSupabase();
        if (supabase) await supabase.auth.signOut();
        setSession(null);
      },
      async sendOtp(email) {
        const supabase = requireSupabase();
        const { error } = await supabase.auth.signInWithOtp({
          email: email.trim().toLowerCase(),
          options: { shouldCreateUser: true },
        });
        if (error) throw new Error(error.message);
      },
      async verifyOtp(email, token) {
        const supabase = requireSupabase();
        const { error } = await supabase.auth.verifyOtp({
          email: email.trim().toLowerCase(),
          token,
          type: "email",
        });
        if (error) throw new Error(error.message);
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
