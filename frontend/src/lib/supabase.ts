"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/** Browser-side Supabase client. Supabase owns email/password auth and stores
 *  the session (localStorage, auto-refreshed), so the app never hand-rolls a
 *  password flow. The backend verifies the JWT this client issues; here we only
 *  need the anon key.
 *
 *  Env: NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY (.env.local).
 *  If unset the client can't be built, so we return null and callers fall back
 *  gracefully rather than crashing at import time. */

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (typeof window === "undefined") return null;
  if (!url || !anonKey) {
    console.warn(
      "Supabase auth is not configured — set NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local",
    );
    return null;
  }
  if (!client) client = createClient(url, anonKey);
  return client;
}

/** True when the Supabase env is present, so the UI can tell "configured but
 *  logged out" from "not configured at all". */
export const isAuthConfigured = Boolean(url && anonKey);
