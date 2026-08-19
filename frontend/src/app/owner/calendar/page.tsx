import { redirect } from "next/navigation";

/**
 * Retired route. The owner calendar merged into the Bookings tab (tab 4, calendar
 * on top + list below). Kept as a redirect so old links/bookmarks still resolve.
 */
export default function OwnerCalendarRedirect() {
  redirect("/owner/bookings");
}
