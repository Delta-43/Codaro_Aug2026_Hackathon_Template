import { redirect } from "next/navigation";
import { API_BASE, tenancyFromConfig } from "@/api";

// The app opens on the provider discovery Search tab (Tab 1) in the multi-provider
// marketplace. In the single-business pivot (`tenancy.mode === "single"`) there is
// no discovery, so it opens straight on the sole business's catalog (/provider).
// Resolved server-side from GET /config to avoid a client redirect flash — reusing
// the same base URL + parser as the client seam (see api/index.ts) so the two can't
// drift. On failure we fall back to the marketplace landing; the boot-time client
// resolver corrects it, so we log rather than swallow silently.
async function isSingleBusiness(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/config`, { cache: "no-store" });
    if (!res.ok) {
      console.error(`Root redirect: GET /config returned ${res.status}; defaulting to marketplace.`);
      return false;
    }
    return tenancyFromConfig(await res.json()).mode === "single";
  } catch (e) {
    console.error("Root redirect: could not reach /config; defaulting to marketplace.", e);
    return false;
  }
}

export default async function RootPage() {
  redirect((await isSingleBusiness()) ? "/provider" : "/search");
}
