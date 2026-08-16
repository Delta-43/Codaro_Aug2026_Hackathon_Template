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
import { SettingsPanel } from "@/components/settings/settings-panel";
import { VerifiedScene } from "@/components/business/verified-badge";

export default function BusinessSettingsPage() {
  const router = useRouter();
  const { user, signOut } = useAuth();
  const { useCase, demoBusiness } = useOwner();

  return (
    <SettingsPanel
      variant="business"
      photo={<VerifiedScene scene={useCase.profileScene} size="lg" />}
      displayName={demoBusiness.name}
      displayNameLabel="Business name"
      email={user?.email ?? "—"}
      onSignOut={() => signOut().then(() => router.replace("/login"))}
    />
  );
}
