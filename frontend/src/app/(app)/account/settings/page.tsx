"use client";

/**
 * User Settings Panel — the shared Settings template configured for the customer
 * persona. Reached from the top-right avatar (desktop) or the Profile tab's cog
 * (mobile). Display name is editable and persists via PATCH /me.
 */
import { useRouter } from "next/navigation";
import { useApp } from "@/context/app-context";
import { useAuth } from "@/lib/auth";
import { updateUser } from "@/api";
import { AvatarImg } from "@/components/avatar-img";
import { Skeleton } from "@/components/skeleton";
import { SettingsPanel } from "@/components/settings/settings-panel";

export default function UserSettingsPage() {
  const router = useRouter();
  const { ready, user, setUser } = useApp();
  const { signOut } = useAuth();

  if (!ready || !user) return <Skeleton className="h-96 w-full" />;

  return (
    <SettingsPanel
      variant="user"
      photo={<AvatarImg src={user.avatarUrl} alt="" className="size-16" />}
      displayName={user.displayName}
      displayNameLabel="Display name"
      onSaveDisplayName={async (value) => {
        const updated = await updateUser({ displayName: value });
        setUser(updated);
      }}
      email={user.email}
      onSignOut={() => signOut().then(() => router.replace("/login"))}
    />
  );
}
