"use client";

/**
 * Profile editor — display name, email, and timezone, saved through the
 * updateUser seam. Timezone is the demo's centrepiece: every slot is a true UTC
 * instant, so changing the zone re-renders the same instants in a new wall clock
 * without touching stored state. Save is enabled only when something changed.
 */
import { useState } from "react";
import type { User } from "@/types/domain";
import { isApiError, updateUser } from "@/api";
import { useApp } from "@/context/app-context";
import { AvatarUpload } from "@/components/account/avatar-upload";
import { Button } from "@/components/ui/button";

const INPUT =
  "h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

/** A small, readable set of IANA zones; the user's own zone is always included. */
const BASE_ZONES = [
  "Europe/Warsaw",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Madrid",
  "Europe/Athens",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Asia/Dubai",
  "Asia/Tokyo",
  "Australia/Sydney",
  "UTC",
];

function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function ProfileForm({ user }: { user: User }) {
  const { setUser } = useApp();
  const [displayName, setDisplayName] = useState(user.displayName);
  const [email, setEmail] = useState(user.email);
  const [timezone, setTimezone] = useState(user.timezone);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const zones = BASE_ZONES.includes(user.timezone)
    ? BASE_ZONES
    : [user.timezone, ...BASE_ZONES];

  const dirty =
    displayName !== user.displayName || email !== user.email || timezone !== user.timezone;
  const valid = displayName.trim().length > 0 && isEmail(email);

  async function save() {
    if (busy || !dirty || !valid) return;
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await updateUser({
        displayName: displayName.trim(),
        email: email.trim(),
        timezone,
      });
      setUser(updated);
      setSaved(true);
    } catch (e) {
      setError(isApiError(e) ? e.message : "Couldn't save your changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">Profile</h2>

      <div className="mt-3 flex items-center gap-3">
        <AvatarUpload avatarUrl={user.avatarUrl} name={user.displayName} className="size-14" />
        <p className="text-xs text-muted-foreground">
          Your details are used across bookings. There&apos;s no password — you&apos;re identified
          by email.
        </p>
      </div>

      <div className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">Display name</span>
          <input
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setSaved(false);
            }}
            aria-label="Display name"
            className={INPUT}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setSaved(false);
            }}
            aria-label="Email"
            aria-invalid={email.length > 0 && !isEmail(email)}
            className={INPUT}
          />
          {email.length > 0 && !isEmail(email) ? (
            <span className="mt-1 block text-xs text-destructive">Enter a valid email.</span>
          ) : null}
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">Timezone</span>
          <select
            value={timezone}
            onChange={(e) => {
              setTimezone(e.target.value);
              setSaved(false);
            }}
            aria-label="Timezone"
            className={INPUT}
          >
            {zones.map((z) => (
              <option key={z} value={z}>
                {z.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <span className="mt-1 block text-xs text-muted-foreground">
            Times across the app are shown in this zone.
          </span>
        </label>
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      ) : null}

      <div className="mt-4 flex items-center gap-3">
        <Button isDisabled={busy || !dirty || !valid} onPress={save}>
          {busy ? "Saving…" : "Save changes"}
        </Button>
        {saved && !dirty ? <span className="text-sm text-primary">Saved</span> : null}
      </div>
    </div>
  );
}
