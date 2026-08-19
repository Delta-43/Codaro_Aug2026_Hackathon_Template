"use client";

/**
 * Tab 3 — Messaging. The permanent hub for the customer's threads with the
 * businesses they book. Self-contained inbox: fetches the user's conversations,
 * refetches on focus (return from a thread refreshes previews + unread), and
 * shows a purposeful empty state instead of self-hiding like the embeddable
 * MessagingSection, since this is a whole tab.
 */
import { useCallback, useEffect, useState } from "react";
import { Send } from "lucide-react";
import type { Conversation } from "@/types/domain";
import { getConversations } from "@/api";
import { useApp } from "@/context/app-context";
import { Skeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ConversationList } from "@/components/messaging/conversation-list";

export default function MessagesPage() {
  const { user } = useApp();
  const tz = user?.timezone ?? "UTC";
  const [conversations, setConversations] = useState<Conversation[] | null>(null);

  const load = useCallback(() => {
    getConversations()
      .then(setConversations)
      .catch(() => setConversations([]));
  }, []);

  useEffect(() => {
    load();
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  return (
    <section className="space-y-4 py-4">
      <h1 className="text-xl font-semibold tracking-tight sr-only">Messaging</h1>

      {conversations === null ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : conversations.length === 0 ? (
        <EmptyState
          icon={<Send className="size-8" aria-hidden />}
          title="No messages yet"
          body="Open a business's profile and tap Message to start a conversation. Approved requests will start a thread here too."
          actionHref="/search"
          actionLabel="Find a business"
        />
      ) : (
        <ConversationList conversations={conversations} basePath="/messages" tz={tz} />
      )}
    </section>
  );
}
