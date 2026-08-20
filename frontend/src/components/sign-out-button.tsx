"use client";

/**
 * Sign-out control with a confirmation gate. Used by both shells' side rails and
 * the Settings panel, so signing out is always a deliberate, confirmed step
 * (not a stray tap). Turns pink on hover like the rest of the platform's
 * neutral buttons; the confirm dialog uses the calm "primary" tone, not the red
 * destructive one.
 */
import { useState } from "react";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/business/confirm-dialog";
import { cn } from "@/lib/utils";

export function SignOutButton({
  onSignOut,
  className,
  size = "sm",
}: {
  /** Performs the actual sign-out (and any redirect). */
  onSignOut: () => Promise<unknown> | void;
  className?: string;
  size?: "sm" | "default" | "lg";
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        size={size}
        className={cn("hover:border-primary hover:bg-primary/10 hover:text-primary", className)}
        onPress={() => setOpen(true)}
      >
        <LogOut aria-hidden /> Sign out
      </Button>
      <ConfirmDialog
        open={open}
        tone="primary"
        icon={<LogOut className="size-7" aria-hidden />}
        title="Sign out of Arbor?"
        body="You'll need to sign in again to get back to your bookings, messages and account."
        confirmLabel="Sign out"
        busyLabel="Signing out…"
        onConfirm={async () => {
          await onSignOut();
        }}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
