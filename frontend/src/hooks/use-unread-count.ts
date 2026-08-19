"use client";

/**
 * Total unread messages across the current user's threads — the number the
 * permanent Messaging nav button badges. Shell-agnostic (no AppProvider
 * dependency), so both the customer AppShell and the BusinessShell can call it.
 * Refetches on window focus so returning from a thread clears the badge without
 * a full Realtime inbox subscription. Degrades to 0 on any error.
 */
import { useCallback, useEffect, useState } from "react";
import { getConversations } from "@/api";

export function useUnreadCount(): number {
  const [count, setCount] = useState(0);

  const load = useCallback(() => {
    getConversations()
      .then((convs) => setCount(convs.reduce((n, c) => n + c.unreadCount, 0)))
      .catch(() => setCount(0));
  }, []);

  useEffect(() => {
    load();
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  return count;
}
