import { redirect } from "next/navigation";

/**
 * The marketing landing page now lives in the standalone `landing/` app (see
 * root CLAUDE.md) — it links here via a plain cross-origin <a> to `/login`.
 * A bare visit to the app's own root has nothing to render, so send it
 * straight to `/login`, which already redirects an authenticated visitor
 * onward itself.
 */
export default function RootPage() {
  redirect("/login");
}
