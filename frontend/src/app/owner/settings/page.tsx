"use client";

/**
 * Business Settings Panel — the shared Settings template configured for the
 * business persona. Reached from the top-right avatar (desktop) or the Profile
 * tab's cog (mobile). Identity follows the active demo use case, so the business
 * name is shown read-only here; the niche itself is switched in the Demo section.
 */
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useOwner } from "@/context/owner-context";
import { uploadProviderAvatar, deleteProviderAvatar } from "@/api";
import { AvatarUpload } from "@/components/account/avatar-upload";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { VerifiedScene } from "@/components/business/verified-badge";

export default function BusinessSettingsPage() {
  const router = useRouter();
  const { user, signOut } = useAuth();
  const { activeProvider, scene, replaceProvider } = useOwner();

  // The business avatar is the active provider's picture (what shows on its
  // cards/profile), so it's only uploadable once a provider is loaded; until
  // then, fall back to the on-brand illustrated scene. The upload/remove calls
  // return the updated provider, so patch it in place rather than refetching
  // the whole list (a transient GET failure there would blank the owner UI).
  const photo = activeProvider ? (
    <AvatarUpload
      avatarUrl={activeProvider.avatarUrl}
      name={activeProvider.name}
      className="size-16"
      onUpload={async (file) => replaceProvider(await uploadProviderAvatar(activeProvider.id, file))}
      onRemove={async () => replaceProvider(await deleteProviderAvatar(activeProvider.id))}
    />
  ) : (
    <VerifiedScene scene={scene} size="lg" />
  );

  return (
    <SettingsPanel
      variant="business"
      photo={photo}
      displayName={activeProvider?.name ?? "Your business"}
      displayNameLabel="Business name"
      email={user?.email ?? "—"}
      onSignOut={() => signOut().then(() => router.replace("/login"))}
    />
  );
}
