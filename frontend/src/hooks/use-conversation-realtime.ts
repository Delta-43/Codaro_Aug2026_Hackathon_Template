"use client";

/**
 * Live delivery for one conversation, over Supabase Realtime — the repo's first
 * `.channel()` usage. It layers on top of the HTTP seam (which owns the durable
 * send/read/delete): this hook only *receives* changes and surfaces the typing
 * indicator.
 *
 *  - `postgres_changes` INSERT on `messages` (filtered to this thread) → a new
 *    bubble, via `onInsert`.
 *  - `postgres_changes` UPDATE on `messages` → a read receipt or soft-delete
 *    patch, via `onUpdate`.
 *  - `broadcast` "typing" → the three-dot indicator (ephemeral, no DB write);
 *    the composer calls the returned `sendTyping()` (throttled).
 *
 * RLS on the user's own session gates exactly what Realtime delivers, so there
 * are no extra grants. When `getSupabase()` is null (env unset) the hook no-ops
 * gracefully — the thread still works over HTTP, just not live.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import type { ID, Message } from "@/types/domain";
import { getSupabase } from "@/lib/supabase";

/** Map a raw `messages` DB row (snake_case, from a Realtime payload) to the
 *  domain `Message`, deriving `mine` from the viewer — mirrors the backend
 *  serializer, including blanking a soft-deleted body. */
function toMessage(row: Record<string, unknown>, meId: ID): Message {
  const deleted = row.deleted_at != null;
  const str = (v: unknown): string | null => (v == null ? null : String(v));
  return {
    id: String(row.id),
    conversationId: String(row.conversation_id),
    senderId: String(row.sender_id),
    body: deleted ? "" : String(row.body ?? ""),
    replyToId: str(row.reply_to_id),
    createdAtUtc: String(row.created_at),
    deliveredAtUtc: str(row.delivered_at),
    readAtUtc: str(row.read_at),
    deletedAtUtc: str(row.deleted_at),
    mine: String(row.sender_id) === meId,
  };
}

const TYPING_VISIBLE_MS = 3000;
const TYPING_THROTTLE_MS = 2000;

export function useConversationRealtime({
  conversationId,
  meId,
  onInsert,
  onUpdate,
}: {
  conversationId: ID | null;
  meId: ID;
  onInsert: (m: Message) => void;
  onUpdate: (m: Message) => void;
}): { typing: boolean; sendTyping: () => void } {
  const [typing, setTyping] = useState(false);

  // Latest callbacks in refs so the subscription effect depends only on the
  // conversation id / viewer — not on every parent re-render's new closures.
  const onInsertRef = useRef(onInsert);
  const onUpdateRef = useRef(onUpdate);
  onInsertRef.current = onInsert;
  onUpdateRef.current = onUpdate;

  const channelRef = useRef<RealtimeChannel | null>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSentTyping = useRef(0);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase || !conversationId) return;

    const filter = `conversation_id=eq.${conversationId}`;
    const channel = supabase
      .channel(`conv:${conversationId}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "messages", filter },
        (payload) => onInsertRef.current(toMessage(payload.new as Record<string, unknown>, meId)),
      )
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "messages", filter },
        (payload) => onUpdateRef.current(toMessage(payload.new as Record<string, unknown>, meId)),
      )
      .on("broadcast", { event: "typing" }, (payload) => {
        // Ignore our own typing echo; show the indicator, auto-hiding after a beat.
        if ((payload.payload as { senderId?: string })?.senderId === meId) return;
        setTyping(true);
        if (typingTimer.current) clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTyping(false), TYPING_VISIBLE_MS);
      })
      .subscribe();

    channelRef.current = channel;
    return () => {
      if (typingTimer.current) clearTimeout(typingTimer.current);
      setTyping(false);
      supabase.removeChannel(channel);
      channelRef.current = null;
    };
  }, [conversationId, meId]);

  const sendTyping = useCallback(() => {
    const now = Date.now();
    if (now - lastSentTyping.current < TYPING_THROTTLE_MS) return;
    lastSentTyping.current = now;
    channelRef.current?.send({ type: "broadcast", event: "typing", payload: { senderId: meId } });
  }, [meId]);

  return { typing, sendTyping };
}
