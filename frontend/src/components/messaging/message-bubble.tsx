"use client";

/**
 * One chat bubble, iMessage-style: pink (primary) for the viewer's own messages,
 * grey (muted) for received. Renders — top to bottom — an optional reply quote,
 * the body (with a client-only link chip), and a timestamp; under the *last sent*
 * message only, a Delivered → "Read at HH:MM" receipt. A soft-deleted message
 * shows an italic placeholder. Long-press (touch) or right-click (desktop) opens
 * the action menu.
 */
import { useRef, useState } from "react";
import { cva } from "class-variance-authority";
import type { Message } from "@/types/domain";
import { formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { LinkPreview } from "@/components/messaging/link-preview";
import { MessageActions } from "@/components/messaging/message-actions";

const bubbleVariants = cva(
  "w-fit max-w-full whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm",
  {
    variants: {
      variant: {
        sent: "rounded-br-md bg-primary text-primary-foreground",
        received: "rounded-bl-md bg-muted text-foreground",
      },
    },
  },
);

const LONG_PRESS_MS = 450;

export function MessageBubble({
  message,
  tz,
  isLastSent,
  replyTo,
  onReply,
  onDelete,
}: {
  message: Message;
  tz: string;
  /** Show the receipt line only under the newest message the viewer sent. */
  isLastSent: boolean;
  /** The message this one replies to, resolved by the thread (for the quote). */
  replyTo?: Message | null;
  onReply?: (m: Message) => void;
  onDelete?: (m: Message) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mine = message.mine;
  const deleted = !!message.deletedAtUtc;

  const clearTimer = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };
  const startLongPress = () => {
    clearTimer();
    timer.current = setTimeout(() => setMenuOpen(true), LONG_PRESS_MS);
  };

  const receipt = message.readAtUtc
    ? `Read at ${formatTime(message.readAtUtc, tz)}`
    : message.deliveredAtUtc
      ? "Delivered"
      : "Sent";

  return (
    <div className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
      <div className="relative max-w-[78%]">
        <div
          className={bubbleVariants({ variant: mine ? "sent" : "received" })}
          onContextMenu={(e) => {
            e.preventDefault();
            setMenuOpen(true);
          }}
          onPointerDown={startLongPress}
          onPointerUp={clearTimer}
          onPointerLeave={clearTimer}
          onPointerCancel={clearTimer}
          onPointerMove={clearTimer}
        >
          {replyTo ? (
            <div className="mb-1 border-l-2 border-current/40 pl-2 text-xs opacity-80">
              <span className="line-clamp-2">
                {replyTo.deletedAtUtc ? "Message deleted" : replyTo.body}
              </span>
            </div>
          ) : null}

          {deleted ? (
            <span className="italic opacity-70">Message deleted</span>
          ) : (
            <>
              <span>{message.body}</span>
              <LinkPreview body={message.body} />
            </>
          )}
        </div>

        <MessageActions
          message={message}
          tz={tz}
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          onReply={onReply}
          onDelete={onDelete}
          align={mine ? "end" : "start"}
        />
      </div>

      <div
        className={cn(
          "mt-0.5 flex items-center gap-1 px-1 text-[10px] text-muted-foreground",
          mine ? "justify-end" : "justify-start",
        )}
      >
        <span>{formatTime(message.createdAtUtc, tz)}</span>
        {mine && isLastSent && !deleted ? (
          <>
            <span aria-hidden>·</span>
            <span>{receipt}</span>
          </>
        ) : null}
      </div>
    </div>
  );
}
