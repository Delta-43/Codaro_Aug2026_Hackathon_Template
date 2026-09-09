// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The reusable "front and centre" inbox block, a heading + the conversation
 * list, that both existing panels embed (client Bookings, business Requests)
 * and the future single-business shell can reuse unchanged. Self-contained: it
 * fetches the current user's threads, derives the viewer timezone from
 * `useAuth()` (so it works in either shell), refetches on window focus for
 * freshness, and hides itself when there are no conversations.
 */
import { useCallback, useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import type { Conversation } from "@/types/domain";
import { getConversations } from "@/api";
import { useAuth } from "@/lib/auth";
import { Skeleton } from "@/components/skeleton";
import { ConversationList } from "@/components/messaging/conversation-list";

export function MessagingSection({
  basePath,
  title = "Messages",
}: {
  /** Thread route prefix rows link to, e.g. "/messages" or "/owner/messages". */
  basePath: string;
  title?: string;
}) {
  const { user } = useAuth();
  const tz =
    (user?.user_metadata?.timezone as string | undefined) ||
    (typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC");
  const [conversations, setConversations] = useState<Conversation[] | null>(null);

  const load = useCallback(() => {
    getConversations()
      .then(setConversations)
      .catch(() => setConversations([]));
  }, []);

  useEffect(() => {
    load();
    // Coming back to the tab (e.g. after reading a thread) refreshes previews +
    // unread counts without a full Realtime inbox subscription.
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  // Nothing to show yet (a brand-new account) → stay out of the way.
  if (conversations !== null && conversations.length === 0) return null;

  const totalUnread = (conversations ?? []).reduce((n, c) => n + c.unreadCount, 0);

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <MessagesSquare className="size-4 text-muted-foreground" aria-hidden />
          {title}
        </h2>
        {totalUnread > 0 ? (
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">
            {totalUnread}
          </span>
        ) : null}
      </div>
      {conversations === null ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <ConversationList conversations={conversations} basePath={basePath} tz={tz} />
      )}
    </section>
  );
}
