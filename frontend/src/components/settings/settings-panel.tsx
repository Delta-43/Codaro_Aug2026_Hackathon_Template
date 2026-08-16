"use client";

/**
 * The shared Settings template, recycled by both the User and Business settings
 * panels. It renders the ~80% of settings every app has — profile photo, name,
 * email, change password, notifications, appearance — plus the demo use-case
 * switcher, and a sign-out. Callers pass a small config and (optionally) extra
 * profile fields specific to their persona.
 *
 * Real where it's cheap and safe (name save, notifications, appearance, demo
 * switch, sign out); honest stubs where it needs backend plumbing that isn't
 * here yet (email change, password change, photo upload, account deletion).
 */
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Bell, Camera, LogOut, Palette, ShieldAlert, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeToggle } from "@/components/account/theme-toggle";
import { useDemoUseCase } from "@/lib/demo-use-case";
import { USE_CASE_IDS, USE_CASES } from "@/config/useCases";
import { cn } from "@/lib/utils";

export interface SettingsConfig {
  variant: "user" | "business";
  photo: ReactNode;
  displayName: string;
  displayNameLabel: string;
  /** When set, the name is editable and this persists it. */
  onSaveDisplayName?: (value: string) => Promise<void>;
  email: string;
  /** Extra persona-specific profile fields (e.g. business bio, user bio). */
  extraProfile?: ReactNode;
  onSignOut: () => void;
}

export function SettingsPanel(cfg: SettingsConfig) {
  return (
    <section className="space-y-6 py-2">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your {cfg.variant === "business" ? "business" : "account"}, preferences and demo.
        </p>
      </div>

      <Section title="Profile" description="How you appear across the app.">
        <div className="flex items-center gap-4">
          <div className="relative">
            {cfg.photo}
            <button
              type="button"
              onClick={() => alert("Photo upload lands with media storage.")}
              aria-label="Change photo"
              className="absolute -bottom-1 -right-1 grid size-7 place-items-center rounded-full border border-border bg-card text-muted-foreground shadow-sm hover:text-foreground"
            >
              <Camera className="size-3.5" aria-hidden />
            </button>
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{cfg.displayName}</p>
            <p className="truncate text-sm text-muted-foreground">{cfg.email}</p>
          </div>
        </div>

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

      <Section title="Appearance" description="Light, dark, or follow your device.">
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Palette className="size-4" aria-hidden /> Theme
          </span>
          <ThemeToggle />
        </div>
      </Section>

      <Section title="Demo" description="Switch the demo use case across the whole app.">
        <DemoUseCaseSwitcher />
      </Section>

      <Section title="Account">
        <Button variant="outline" size="sm" onPress={cfg.onSignOut}>
          <LogOut aria-hidden /> Sign out
        </Button>
        <button
          type="button"
          onClick={() => alert("Account deletion lands with backend support.")}
          className="mt-3 inline-flex items-center gap-1.5 text-sm text-destructive hover:underline"
        >
          <ShieldAlert className="size-4" aria-hidden /> Delete account
        </button>
      </Section>
    </section>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
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
        <Label>{label}</Label>
        <Input value={value} readOnly className="opacity-70" />
        <p className="text-[11px] text-muted-foreground">Managed by the active demo use case.</p>
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
      <Label>{label}</Label>
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
      <Label>Email</Label>
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
        setNotice("In this demo, password changes go through the email reset flow.");
      }}
      className="grid gap-3 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-1">
        <Label>Current password</Label>
        <Input type="password" placeholder="••••••••" autoComplete="current-password" />
      </div>
      <div className="flex flex-col gap-1">
        <Label>New password</Label>
        <Input type="password" placeholder="••••••••" autoComplete="new-password" />
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" size="sm" variant="outline">
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
        <li key={n.id} className="flex items-center justify-between gap-3">
          <span className="inline-flex items-start gap-2">
            <Bell className="mt-0.5 size-4 text-muted-foreground" aria-hidden />
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
        "flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors",
        on ? "bg-primary" : "bg-muted",
      )}
    >
      <span className={cn("size-5 rounded-full bg-card shadow-sm transition-transform", on ? "translate-x-5" : "translate-x-0")} />
    </button>
  );
}

function DemoUseCaseSwitcher() {
  const [useCase, setUseCaseId] = useDemoUseCase();
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {USE_CASE_IDS.map((id) => {
          const uc = USE_CASES[id];
          const active = useCase.id === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setUseCaseId(id)}
              aria-pressed={active}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                active
                  ? "border-primary/40 bg-primary/5 text-foreground"
                  : "border-border bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              {active ? <Sparkles className="size-4 shrink-0 text-primary" aria-hidden /> : <span className="size-4 shrink-0" />}
              <span className="truncate font-medium">{uc.label}</span>
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Currently showing <span className="font-medium text-foreground">{useCase.label}</span>. Switching updates the
        demo content across business mode and profiles.
      </p>
    </div>
  );
}
