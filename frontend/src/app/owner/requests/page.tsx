// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { redirect } from "next/navigation";

/**
 * Retired route. Requests now live at the top of the permanent Messages tab
 * (tab 3). Kept as a redirect so old links/bookmarks land in the right place.
 */
export default function RequestsRedirect() {
  redirect("/owner/messages");
}
