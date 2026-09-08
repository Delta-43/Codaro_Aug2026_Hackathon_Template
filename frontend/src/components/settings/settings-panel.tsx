// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The shared Settings template, recycled by both the User and Business settings
 * panels. It renders the ~80% of settings every app has — profile photo, name,
 * email, change password, notifications, appearance, and a sign-out. Callers
 * pass a small config and (optionally) extra profile fields specific to their
 * persona.
 *
 * Real where it's cheap and safe (name save, photo upload, notifications,
 * appearance, sign out); honest stubs where it needs backend
 * plumbing that isn't here yet (email change, password change, account
 * deletion). The `photo` and `hero` slots carry their own upload affordances:
 * the user avatar, the business's active-provider avatar and the business's
 * banner are all uploadable (the caller wires that in), so this template just
 * renders whatever it's handed.
 */
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Bell, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AppearancePicker } from "@/components/account/appearance-picker";
import { ConfirmDialog } from "@/components/business/confirm-dialog";
import { SignOutButton } from "@/components/auth/sign-out-button";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

/** Interactive feel for the plate headings — a gentle hover-grow, anchored left
 *  so the title doesn't drift. Same feel the rest of the platform uses. */
const HEADING_FX =
  "inline-block origin-left transition-transform duration-200 ease-out hover:scale-105";

/** Interactive form labels — grow and turn pink on hover like the login field
 *  labels, anchored left and only as wide as the text so the row doesn't shift. */
const LABEL_FX =
  "inline-block w-fit origin-left transition-all duration-200 ease-out hover:scale-110 hover:text-primary";

export interface SettingsConfig {
  variant: "user" | "business";
  photo: ReactNode;
  /** Optional full profile header, rendered *instead of* the photo row: the
   *  business persona passes the very header its Profile tab shows, so the
   *  owner edits the real thing rather than a stand-in. */
  hero?: ReactNode;
  displayName: string;
  displayNameLabel: string;
  /** When set, the name is editable and this persists it. */
  onSaveDisplayName?: (value: string) => Promise<void>;
  email: string;
  /** Extra persona-specific profile fields (e.g. business bio, user bio). */
  extraProfile?: ReactNode;
  onSignOut: () => void;
  /** When set, "Delete my data" performs a real erasure (GDPR). The caller is
   *  responsible for signing out / redirecting once it resolves. */
  onDeleteAccount?: () => Promise<void>;
}

export function SettingsPanel(cfg: SettingsConfig) {
  return (
    <section className="space-y-6 py-2">
      <div>
        {/* The shell's desktop top bar shows the "Settings" title, and on mobile
            the bottom tab bar marks the tab — so this stays screen-reader only,
            no on-screen copy. */}
        <h1 className="sr-only">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your {cfg.variant === "business" ? "business" : "account"} and preferences.
        </p>
      </div>

      <Section title="Profile" description="How you appear across the app.">
        {cfg.hero ?? (
          <div className="flex items-center gap-4">
            {cfg.photo}
            <div className="min-w-0 flex-1">
              <p className={cn(buttonFx.heading, "max-w-full truncate font-medium")}>{cfg.displayName}</p>
              <p className="truncate text-sm text-muted-foreground">{cfg.email}</p>
            </div>
          </div>
        )}

        <NameField
          label={cfg.displayNameLabel}
          value={cfg.displayName}
          onSave={cfg.onSaveDisplayName}
        />
        <EmailField email={cfg.email} />
        {cfg.extraProfile}
      </Section>

      <Section title="Password" description="Keep your account secure.">
        <PasswordForm />
      </Section>

      <Section title="Notifications" description="Choose what we contact you about.">
        <Notifications />
      </Section>

      {/* Appearance: the control sits on the right of the label + description,
          vertically centred, so the plate reads balanced (no lonely full-width
          row of buttons). */}
      <div className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">
            <span className={HEADING_FX}>Appearance</span>
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Light, dark, or follow your device.
          </p>
        </div>
        <AppearancePicker />
      </div>

      <Section title="Account">
        {/* Two equal-width buttons, side by side, so the plate reads symmetrical. */}
        <div className="grid grid-cols-2 gap-2">
          <SignOutButton withIcon className="w-full" onSignOut={cfg.onSignOut} />
          <DeleteAccount onDeleteAccount={cfg.onDeleteAccount} />
        </div>
      </Section>
    </section>
  );
}

/** GDPR right-to-erasure control. Opens a destructive confirm dialog before
 *  calling the supplied erasure fn (DELETE /me); the caller signs out +
 *  redirects on success. Falls back to the honest stub when no handler is wired
 *  (e.g. a persona without backend deletion yet). */
function DeleteAccount({ onDeleteAccount }: { onDeleteAccount?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);

  if (!onDeleteAccount) {
    return (
      <Button
        variant="destructive"
        size="sm"
        className="w-full"
        onPress={() => alert("Account deletion lands with backend support.")}
      >
        <ShieldAlert aria-hidden /> Delete account
      </Button>
    );
  }

  return (
    <>
      <Button variant="destructive" size="sm" className="w-full" onPress={() => setOpen(true)}>
        <ShieldAlert aria-hidden /> Delete account
      </Button>
      <ConfirmDialog
        open={open}
        title="Delete your account and all your data?"
        body="This permanently removes your account, bookings, follows and reviews. This cannot be undone."
        confirmLabel="Yes, delete everything"
        busyLabel="Deleting…"
        onConfirm={onDeleteAccount}
        onClose={() => setOpen(false)}
      />
    </>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">
        <span className={HEADING_FX}>{title}</span>
      </h2>
      {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  );
}

function NameField({ label, value, onSave }: { label: string; value: string; onSave?: (v: string) => Promise<void> }) {
  const [name, setName] = useState(value);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => setName(value), [value]);

  if (!onSave) {
    return (
      <div className="flex flex-col gap-1">
        <Label className={LABEL_FX}>{label}</Label>
        <Input value={value} readOnly className="opacity-70" />
        <p className="text-[11px] text-muted-foreground">This field is read-only.</p>
      </div>
    );
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await onSave!(name);
      setMsg("Saved.");
    } catch {
      setMsg("Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-1">
      <Label className={LABEL_FX}>{label}</Label>
      <div className="flex items-center gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" size="sm" isDisabled={busy || name === value}>
          {busy ? "…" : "Save"}
        </Button>
      </div>
      {msg ? <p className="text-[11px] text-muted-foreground">{msg}</p> : null}
    </form>
  );
}

function EmailField({ email }: { email: string }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className={LABEL_FX}>Email</Label>
      <Input value={email} readOnly className="opacity-70" />
      <p className="text-[11px] text-muted-foreground">Changing your email is handled via a verification link.</p>
    </div>
  );
}

function PasswordForm() {
  const [notice, setNotice] = useState<string | null>(null);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setNotice("Password changes go through the email reset flow.");
      }}
      className="grid gap-3 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-1">
        <Label className={LABEL_FX}>Current password</Label>
        <Input type="password" placeholder="••••••••" autoComplete="current-password" />
      </div>
      <div className="flex flex-col gap-1">
        <Label className={LABEL_FX}>New password</Label>
        <Input type="password" placeholder="••••••••" autoComplete="new-password" />
      </div>
      <div className="sm:col-span-2">
        <Button
          type="submit"
          size="sm"
          variant="outline"
          className="hover:border-primary hover:bg-primary/10 hover:text-primary"
        >
          Change password
        </Button>
        {notice ? <p className="mt-2 text-[11px] text-muted-foreground">{notice}</p> : null}
      </div>
    </form>
  );
}

const NOTIF_KEY = "codaro.settings.notifications";
const NOTIF_ITEMS = [
  { id: "bookings", label: "Booking updates", desc: "Confirmations, changes and reminders." },
  { id: "messages", label: "Messages", desc: "When someone messages you." },
  { id: "marketing", label: "Product news", desc: "Occasional updates and tips." },
] as const;

function Notifications() {
  const [state, setState] = useState<Record<string, boolean>>({ bookings: true, messages: true, marketing: false });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(NOTIF_KEY);
      if (raw) setState((s) => ({ ...s, ...JSON.parse(raw) }));
    } catch {
      /* ignore */
    }
  }, []);

  function toggle(id: string) {
    setState((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      try {
        localStorage.setItem(NOTIF_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  return (
    <ul className="space-y-2">
      {NOTIF_ITEMS.map((n) => (
        <li key={n.id} className="group flex items-center justify-between gap-3">
          <span className="inline-flex items-start gap-2">
            <Bell className="mt-0.5 size-4 text-muted-foreground transition-all group-hover:scale-110 group-hover:text-primary" aria-hidden />
            <span>
              <span className="block text-sm font-medium">{n.label}</span>
              <span className="block text-xs text-muted-foreground">{n.desc}</span>
            </span>
          </span>
          <Switch on={!!state[n.id]} onChange={() => toggle(n.id)} label={n.label} />
        </li>
      ))}
    </ul>
  );
}

function Switch({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onChange}
      className={cn(
        "flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-all",
        buttonFx.press,
        on ? "bg-primary" : "bg-muted",
      )}
    >
      <span className={cn("size-5 rounded-full bg-card shadow-sm transition-transform", on ? "translate-x-5" : "translate-x-0")} />
    </button>
  );
}

