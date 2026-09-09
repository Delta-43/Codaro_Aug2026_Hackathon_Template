// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { redirect } from "next/navigation";

/**
 * Retired route. The owner calendar merged into the Bookings tab (tab 4, calendar
 * on top + list below). Kept as a redirect so old links/bookmarks still resolve.
 */
export default function OwnerCalendarRedirect() {
  redirect("/owner/bookings");
}
