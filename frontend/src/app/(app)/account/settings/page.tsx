// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * User Settings Panel: the shared Settings template configured for the customer
 * persona. It is what the shell's Settings tab opens, mirroring the owner
 * console's Settings tab. The profile page above it (reputation, membership,
 * reviews) is reached from the top-right avatar on desktop and from the row this
 * page adds to its Profile section on mobile. Display name is editable and
 * persists via PATCH /me.
 */
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { buttonFx } from "@/config/buttons";
import { useApp } from "@/context/app-context";
import { useAuth } from "@/lib/auth";
import { updateUser, uploadAvatar, deleteAvatar, deleteAccount } from "@/api";
import { AvatarUpload } from "@/components/account/avatar-upload";
import { Skeleton } from "@/components/skeleton";
import { SettingsPanel } from "@/components/settings/settings-panel";

export default function UserSettingsPage() {
  const { ready, user, setUser } = useApp();
  const { signOut } = useAuth();

  if (!ready || !user) return <Skeleton className="h-96 w-full" />;

  return (
    <SettingsPanel
      variant="user"
      photo={
        <AvatarUpload
          avatarUrl={user.avatarUrl}
          name={user.displayName}
          className="size-16"
          onUpload={async (file) => setUser(await uploadAvatar(file))}
          onRemove={async () => setUser(await deleteAvatar())}
        />
      }
      displayName={user.displayName}
      displayNameLabel="Display name"
      onSaveDisplayName={async (value) => {
        const updated = await updateUser({ displayName: value });
        setUser(updated);
      }}
      email={user.email}
      extraProfile={
        <Link
          href="/account"
          className={cn(
            "group flex items-center gap-3 rounded-xl border border-border bg-card p-3",
            buttonFx.surface,
          )}
        >
          <span className="min-w-0 flex-1">
            <span className="block font-medium">Your profile</span>
            <span className="block text-sm text-muted-foreground">
              Reputation, membership and reviews.
            </span>
          </span>
          <ChevronRight
            className={cn("size-5 shrink-0 text-muted-foreground", buttonFx.chevron)}
            aria-hidden
          />
        </Link>
      }
      onSignOut={signOut}
      onDeleteAccount={async () => {
        await deleteAccount();
        // signOut() lands on the landing page.
        await signOut();
      }}
    />
  );
}
