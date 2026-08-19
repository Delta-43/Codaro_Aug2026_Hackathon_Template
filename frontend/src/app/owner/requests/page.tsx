import { redirect } from "next/navigation";

/**
 * Retired route. Requests now live at the top of the permanent Messages tab
 * (tab 3). Kept as a redirect so old links/bookmarks land in the right place.
 */
export default function RequestsRedirect() {
  redirect("/owner/messages");
}
