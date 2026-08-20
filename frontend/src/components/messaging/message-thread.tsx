"use client";

/**
 * A full conversation view: header (back + other party), the scrollable message
 * list, and the composer. Reusable and shell-agnostic — it reads identity from
 * `useAuth()` (present app-wide), so it drops into both the client `(app)` shell
 * and the `owner` shell unchanged. Live delivery + typing come from
 * `use-conversation-realtime`; the durable send/read/delete go through the seam,
 * with an optimistic bubble on send (reconciled with the server/Realtime echo).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Send, X } from "lucide-react";
import type { Conversation, Message } from "@/types/domain";
import {
  ApiError,
  deleteMessage,
  getConversation,
  getMessages,
  markConversationRead,
  sendMessage,
} from "@/api";
import { useAuth } from "@/lib/auth";
import { notifyUnreadChanged } from "@/hooks/use-unread-count";
import { AvatarImg } from "@/components/avatar-img";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { MessageBubble } from "@/components/messaging/message-bubble";
import { TypingIndicator } from "@/components/messaging/typing-indicator";
import { useConversationRealtime } from "@/hooks/use-conversation-realtime";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

/** Insert-or-replace a message arriving from Realtime, reconciling a viewer's
 *  own echo with the optimistic temp bubble so it never double-renders. */
function mergeIncoming(prev: Message[], msg: Message): Message[] {
  const idx = prev.findIndex((m) => m.id === msg.id);
  if (idx >= 0) {
    const next = prev.slice();
    next[idx] = msg;
    return next;
  }
  if (msg.mine) {
    const tempIdx = prev.findIndex((m) => m.id.startsWith("temp-"));
    if (tempIdx >= 0) {
      const next = prev.slice();
      next[tempIdx] = msg;
      return next;
    }
  }
  return [...prev, msg];
}

export function MessageThread({ backHref }: { backHref: string }) {
  const params = useParams<{ conversationId: string }>();
  const conversationId = params?.conversationId ?? null;
  const { user } = useAuth();
  const meId = user?.id ?? "";
  const tz =
    (user?.user_metadata?.timezone as string | undefined) ||
    (typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC");

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [replyTo, setReplyTo] = useState<Message | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Load the thread + its messages, then mark the other party's messages read.
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([getConversation(conversationId), getMessages(conversationId)])
      .then(([conv, msgs]) => {
        if (cancelled) return;
        setConversation(conv);
        setMessages(msgs);
        setLoading(false);
        void markConversationRead(conversationId).then(notifyUnreadChanged).catch(() => {});
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Couldn't load this conversation.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  const onInsert = useCallback(
    (m: Message) => {
      setMessages((prev) => mergeIncoming(prev, m));
      // An incoming message while the thread is open → mark it read so the sender
      // sees the receipt flip live.
      if (!m.mine && conversationId) void markConversationRead(conversationId).then(notifyUnreadChanged).catch(() => {});
    },
    [conversationId],
  );
  const onUpdate = useCallback((m: Message) => setMessages((prev) => mergeIncoming(prev, m)), []);

  const { typing, sendTyping } = useConversationRealtime({
    conversationId,
    meId,
    onInsert,
    onUpdate,
  });

  // Keep the newest message in view as things arrive / the composer grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, typing]);

  async function handleSend() {
    const body = input.trim();
    if (!body || !conversationId) return;
    const tempId = `temp-${Date.now()}`;
    const replyId = replyTo?.id;
    const optimistic: Message = {
      id: tempId,
      conversationId,
      senderId: meId,
      body,
      replyToId: replyId ?? null,
      createdAtUtc: new Date().toISOString(),
      deliveredAtUtc: null,
      readAtUtc: null,
      deletedAtUtc: null,
      mine: true,
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");
    setReplyTo(null);
    setError(null);
    try {
      const real = await sendMessage(conversationId, body, replyId);
      setMessages((prev) => {
        const tempIdx = prev.findIndex((m) => m.id === tempId);
        if (tempIdx >= 0) {
          const next = prev.slice();
          next[tempIdx] = real;
          return next;
        }
        return mergeIncoming(prev, real); // Realtime already reconciled the temp.
      });
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setInput(body); // restore the unsent text
      setError(e instanceof ApiError ? e.message : "That message didn't send. Try again.");
    }
  }

  async function handleDelete(m: Message) {
    if (!conversationId) return;
    // An unsent optimistic bubble isn't persisted — just drop it locally.
    if (m.id.startsWith("temp-")) {
      setMessages((prev) => prev.filter((x) => x.id !== m.id));
      return;
    }
    const prevSnapshot = m;
    setMessages((prev) =>
      prev.map((x) => (x.id === m.id ? { ...x, body: "", deletedAtUtc: new Date().toISOString() } : x)),
    );
    try {
      await deleteMessage(conversationId, m.id);
    } catch {
      setMessages((prev) => prev.map((x) => (x.id === m.id ? prevSnapshot : x))); // revert
    }
  }

  const otherName = conversation?.otherParty.name || "Conversation";
  const otherAvatar = conversation?.otherParty.avatarUrl;
  const lastSentId = [...messages].reverse().find((m) => m.mine && !m.deletedAtUtc)?.id;

  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col md:h-[calc(100dvh-9rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border pb-3">
        <Link
          href={backHref}
          aria-label="Back"
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-all hover:bg-muted hover:text-foreground",
            buttonFx.press,
          )}
        >
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
        {loading ? (
          <Skeleton className="h-9 w-40" />
        ) : (
          <>
            <AvatarImg src={otherAvatar} name={otherName} alt="" className="size-9 shrink-0" />
            <span className="truncate font-semibold">{otherName}</span>
          </>
        )}
      </div>

      {/* Message list */}
      <div className="no-scrollbar flex-1 space-y-2 overflow-y-auto py-4">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className={cn("h-10", i % 2 ? "ml-auto w-1/2" : "w-2/3")} />
            ))}
          </div>
        ) : error && messages.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">{error}</p>
        ) : messages.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No messages yet — say hello 👋
          </p>
        ) : (
          messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              tz={tz}
              isLastSent={m.id === lastSentId}
              replyTo={m.replyToId ? messages.find((x) => x.id === m.replyToId) ?? null : null}
              onReply={setReplyTo}
              onDelete={handleDelete}
            />
          ))
        )}
        {typing ? <TypingIndicator /> : null}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-border pt-3">
        {error && messages.length > 0 ? (
          <p className="mb-2 text-xs text-destructive">{error}</p>
        ) : null}
        {replyTo ? (
          <div className="mb-2 flex items-center gap-2 rounded-xl border border-border bg-muted/50 px-3 py-1.5 text-xs">
            <span className="min-w-0 flex-1 truncate text-muted-foreground">
              Replying to{" "}
              <span className="text-foreground">
                {replyTo.deletedAtUtc ? "a deleted message" : replyTo.body}
              </span>
            </span>
            <button
              type="button"
              aria-label="Cancel reply"
              onClick={() => setReplyTo(null)}
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-all hover:bg-muted hover:text-foreground",
                buttonFx.press,
              )}
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </div>
        ) : null}
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void handleSend();
          }}
        >
          <Input
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              sendTyping();
            }}
            placeholder="Message…"
            aria-label="Message"
            className="h-10 flex-1 rounded-full"
            disabled={loading}
          />
          <Button
            type="submit"
            size="icon-lg"
            className="rounded-full"
            aria-label="Send"
            isDisabled={loading || !input.trim()}
          >
            <Send aria-hidden />
          </Button>
        </form>
      </div>
    </div>
  );
}
