// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Total unread messages across the current user's threads, the number the
 * permanent Messaging nav button badges. Shell-agnostic (no AppProvider
 * dependency), so both the customer AppShell and the BusinessShell can call it.
 *
 * The count is refreshed on three signals, because no single one covers every
 * way you can read a thread:
 *  - **window focus**, returning to the tab after being away;
 *  - **route change**, SPA navigation fires no focus event, so leaving a thread
 *    (back to the inbox or any other tab) would otherwise leave the badge stale;
 *  - **an explicit `unread-changed` event**, dispatched by the thread the moment
 *    it marks messages read, so the badge clears immediately even while you stay
 *    on the same page (e.g. the mobile bottom-bar badge).
 * Degrades to 0 on any error.
 */
import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { getConversations } from "@/api";

/** Window event the messaging thread fires after it marks a conversation read.
 *  Internal to this module: dispatch it via `notifyUnreadChanged()`. */
const UNREAD_CHANGED_EVENT = "arbor:unread-changed";

/** Tell every mounted unread badge to refetch (call after marking read). */
export function notifyUnreadChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(UNREAD_CHANGED_EVENT));
  }
}

export function useUnreadCount(): number {
  const [count, setCount] = useState(0);
  const pathname = usePathname();

  const load = useCallback(() => {
    getConversations()
      .then((convs) => setCount(convs.reduce((n, c) => n + c.unreadCount, 0)))
      .catch(() => setCount(0));
  }, []);

  // Refetch on mount and whenever the route changes (leaving a thread re-counts).
  useEffect(() => {
    load();
  }, [load, pathname]);

  // Refetch on window focus and on the explicit read event.
  useEffect(() => {
    const onSignal = () => load();
    window.addEventListener("focus", onSignal);
    window.addEventListener(UNREAD_CHANGED_EVENT, onSignal);
    return () => {
      window.removeEventListener("focus", onSignal);
      window.removeEventListener(UNREAD_CHANGED_EVENT, onSignal);
    };
  }, [load]);

  return count;
}
