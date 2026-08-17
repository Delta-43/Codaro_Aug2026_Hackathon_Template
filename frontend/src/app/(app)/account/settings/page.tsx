"use client";

/**
 * User Settings Panel — the shared Settings template configured for the customer
 * persona. Reached from the top-right avatar (desktop) or the Profile tab's cog
 * (mobile). Display name is editable and persists via PATCH /me.
 */
import { useRouter } from "next/navigation";
import { useApp } from "@/context/app-context";
import { useAuth } from "@/lib/auth";
import { updateUser, uploadAvatar, deleteAvatar } from "@/api";
import { AvatarUpload } from "@/components/account/avatar-upload";
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
      onSignOut={() => signOut().then(() => router.replace("/login"))}
    />
  );
}
