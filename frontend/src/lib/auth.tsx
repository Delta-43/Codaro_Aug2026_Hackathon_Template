"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase, isAuthConfigured } from "@/lib/supabase";
import { getMyRole } from "@/api";

/** App-wide auth state, backed by Supabase Auth. The signed-in user is verified,
 *  and their email is the booking owner the backend records. The access token is
 *  attached as `Authorization: Bearer <jwt>` on every backend call (see the API
 *  seam in @/api). */

/** Engine-neutral roles, labelled in the UI via the domain config's terms — never
 *  a hardcoded "Owner"/"Customer". Anything other than "owner" is a client. */
export type EngineRole = "owner" | "client";

/** The caller's **trusted** role, resolved by the backend from `profiles` — the
 *  same value `require_owner` gates on.
 *
 *  This used to be read straight off the JWT (`user_metadata.role`). That claim
 *  is writable by the user themselves via `supabase.auth.updateUser`, so the two
 *  sides could disagree in both directions: a customer who set it saw the entire
 *  business UI while every request inside it 403'd, and an admin promoting
 *  someone the documented way (UPDATE `profiles.role`) got backend access the UI
 *  kept hiding. The token now only *seeds* the role at sign-up; `profiles` is
 *  what anything reads. */
async function fetchTrustedRole(token: string): Promise<EngineRole> {
  const { role } = await getMyRole(token);
  return role === "owner" ? "owner" : "client";
}

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  role: EngineRole;
  isOwner: boolean;
  /** False while the trusted role is still being resolved for a signed-in user.
   *  Anything that routes on the role must wait for this — treating "not yet
   *  known" as "not an owner" would bounce a business straight out of business
   *  mode on every page load. */
  roleReady: boolean;
  loading: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (
    email: string,
    password: string,
    role?: EngineRole,
    consent?: boolean,
  ) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  // null = not resolved yet. Kept across token refreshes so a refresh doesn't
  // momentarily demote an owner; only a sign-out clears it.
  const [role, setRole] = useState<EngineRole | null>(null);

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

  const sessionUserId = session?.user?.id ?? null;
  const accessToken = session?.access_token ?? null;
  // Which user the held `role` actually belongs to. Keeping the role across a
  // token refresh is deliberate (no momentary demotion), but that must not
  // extend to a *different* user arriving without an intervening sign-out.
  const roleOwnerId = useRef<string | null>(null);

  // The single place a role is resolved. Sign-in deliberately does not resolve
  // its own: `onAuthStateChange` lands the session here anyway, so a second
  // resolver on that path would duplicate the request and race this one for the
  // final write.
  useEffect(() => {
    if (!sessionUserId) {
      roleOwnerId.current = null;
      setRole(null);
      return;
    }
    if (roleOwnerId.current !== sessionUserId) {
      // A different account: drop the previous role so `roleReady` reports
      // "unknown" until this user's own role lands, rather than briefly
      // answering for them with their predecessor's.
      roleOwnerId.current = sessionUserId;
      setRole(null);
    }
    if (!accessToken) {
      // A session carrying no usable token can never resolve a role. Settle
      // closed instead of leaving `roleReady` false forever, which would pin
      // the app on a loading screen with nothing scheduled to break out.
      setRole((prev) => prev ?? "client");
      return;
    }
    let cancelled = false;
    fetchTrustedRole(accessToken)
      .then((resolved) => {
        if (!cancelled) setRole(resolved);
      })
      .catch(() => {
        // Unreachable, or the lookup timed out. Keep whatever was already
        // resolved, so an established owner rides out a blip instead of being
        // ejected from business mode mid-session. With nothing resolved yet,
        // fail closed to the customer app rather than to the token's
        // self-asserted claim — every owner-only call would 403 anyway, so
        // opening business mode on a guess only renders a screen that cannot
        // work.
        if (!cancelled) setRole((prev) => prev ?? "client");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionUserId, accessToken]);

  const value = useMemo<AuthContextValue>(() => {
    const user = session?.user ?? null;
    // Default to the customer app until the backend says otherwise; `roleReady`
    // is how callers tell "confirmed customer" from "not resolved yet".
    const resolved: EngineRole = role ?? "client";
    return {
      session,
      user,
      role: resolved,
      isOwner: resolved === "owner",
      roleReady: !session || role !== null,
      loading,
      configured: isAuthConfigured,
      async signIn(email, password) {
        const supabase = requireSupabase();
        const { error } = await supabase.auth.signInWithPassword({
          email: email.trim().toLowerCase(),
          password,
        });
        if (error) throw new Error(error.message);
        // The role follows from `profiles` once the session lands — never from
        // what this client thinks the user is.
      },
      async signUp(email, password, role: EngineRole = "client", consent = false) {
        const supabase = requireSupabase();
        const address = email.trim().toLowerCase();
        // GDPR: record the explicit consent the sign-up form gated on, alongside
        // the role, in the user's metadata. Owners also carry their role.
        const data = {
          ...(role === "owner" ? { role } : {}),
          gdpr_consent: consent,
          gdpr_consent_at: consent ? new Date().toISOString() : null,
        };
        const { data: result, error } = await supabase.auth.signUp({
          email: address,
          password,
          options: { data },
        });
        if (error) throw new Error(error.message);
        // No inbox step: the Supabase project has "Confirm email" turned off, so
        // sign-up returns a live session and the account works immediately.
        //
        // If a deployment ever turns confirmation back on, signUp yields a user
        // but NO session. Signing in explicitly here means that case surfaces as
        // a real error ("Email not confirmed") on the form, rather than as a
        // silent half-signed-up state that looks like success and then bounces
        // the user off the gated routes with no explanation.
        if (!result.session) {
          const { error: signInError } = await supabase.auth.signInWithPassword({
            email: address,
            password,
          });
          if (signInError) throw new Error(signInError.message);
        }
      },
      async signOut() {
        const supabase = getSupabase();
        if (supabase) await supabase.auth.signOut();
        setSession(null);
      },
    };
  }, [session, loading, role]);

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
