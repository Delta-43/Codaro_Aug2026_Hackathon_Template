"use client";

/**
 * Business Settings Panel — the shared Settings template configured for the
 * business persona. Reached from the top-right avatar (desktop) or the Profile
 * tab's cog (mobile). Identity follows the active demo use case, so the business
 * name is shown read-only here; the niche itself is switched in the Demo section.
 */
import { useAuth } from "@/lib/auth";
import { useOwner } from "@/context/owner-context";
import {
  uploadProviderAvatar,
  deleteProviderAvatar,
  uploadProviderCover,
  deleteProviderCover,
  deleteAccount,
} from "@/api";
import { AvatarUpload } from "@/components/account/avatar-upload";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { EditableBusinessHero } from "@/components/business/business-hero";
import { VerifiedScene } from "@/components/business/verified-badge";

export default function BusinessSettingsPage() {
  const { user, signOut } = useAuth();
  const { activeProvider, scene, vocab, replaceProvider } = useOwner();

  // The Profile section shows the *same* header the Profile tab does — banner,
  // verified logo, name, tagline and meta row — with the banner and logo
  // swappable in place, so the owner edits what a customer actually sees rather
  // than a shrunken stand-in. Both belong to the active provider, so the header
  // only appears once one is loaded; until then the panel falls back to its
  // plain photo row with the on-brand illustrated scene. The upload/remove
  // calls return the updated provider, so patch it in place rather than
  // refetching the whole list (a transient GET failure there would blank the
  // owner UI).
  const hero = activeProvider ? (
    <EditableBusinessHero
      provider={activeProvider}
      scene={scene}
      vocabLabel={vocab.label}
      onUploadCover={async (file) => replaceProvider(await uploadProviderCover(activeProvider.id, file))}
      onRemoveCover={async () => replaceProvider(await deleteProviderCover(activeProvider.id))}
      onUploadAvatar={async (file) => replaceProvider(await uploadProviderAvatar(activeProvider.id, file))}
      onRemoveAvatar={async () => replaceProvider(await deleteProviderAvatar(activeProvider.id))}
    />
  ) : undefined;

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
      hero={hero}
      displayName={activeProvider?.name ?? "Your business"}
      displayNameLabel="Business name"
      email={user?.email ?? "—"}
      onSignOut={signOut}
      onDeleteAccount={async () => {
        await deleteAccount();
        // signOut() lands on the landing page.
        await signOut();
      }}
    />
  );
}
