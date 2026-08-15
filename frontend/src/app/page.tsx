import { redirect } from "next/navigation";

// The app opens on Search (Tab 1). All real routes live under the (app) group.
export default function RootPage() {
  redirect("/search");
}
