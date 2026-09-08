// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Sign-out trigger with a confirmation gate. Signing out is easy to hit by
 * accident (it lives in the drawer and the Settings panel), so it always routes
 * through the shared ConfirmDialog before the session is torn down. The visual
 * button props are passed through so each caller keeps its own look.
 */
import { useState, type ReactNode } from "react";
import { LogOut } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/business/confirm-dialog";
import type { VariantProps } from "class-variance-authority";

export function SignOutButton({
  onSignOut,
  className,
  variant = "outline",
  size = "sm",
  withIcon = false,
  children = "Sign out",
}: {
  /** The actual sign-out; may redirect once resolved. */
  onSignOut: () => void | Promise<void>;
  className?: string;
  withIcon?: boolean;
  children?: ReactNode;
} & VariantProps<typeof buttonVariants>) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant={variant} size={size} className={className} onPress={() => setOpen(true)}>
        {withIcon ? <LogOut aria-hidden /> : null}
        {children}
      </Button>
      <ConfirmDialog
        open={open}
        tone="default"
        title="Sign out?"
        body="You'll need to sign back in to reach your bookings and settings."
        confirmLabel="Sign out"
        busyLabel="Signing out…"
        onConfirm={onSignOut}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
