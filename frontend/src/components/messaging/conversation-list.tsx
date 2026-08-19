"use client";

/**
 * The inbox: one row per conversation, mirroring the provider/booking card style
 * (avatar + name + preview + chevron). An unread thread gets a highlighted row,
 * a bolded name/preview, and a pink count badge. Rows deep-link into the
 * persona's thread route (`${basePath}/${id}`).
 */
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Conversation } from "@/types/domain";
import { AvatarImg } from "@/components/avatar-img";
import { avatarDataUri } from "@/lib/business-view";
import { timeAgo } from "@/lib/format";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";

export function ConversationList({
  conversations,
  basePath,
  tz,
}: {
  conversations: Conversation[];
  /** Thread route prefix, e.g. "/messages" — rows link to `${basePath}/${id}`. */
  basePath: string;
  tz: string;
}) {
  return (
    <ul className="space-y-2">
      {conversations.map((c) => {
        const name = c.otherParty.name || "Conversation";
        const avatar = c.otherParty.avatarUrl || avatarDataUri(name);
        const unread = c.unreadCount > 0;
        return (
          <li key={c.id}>
            <Link
              href={`${basePath}/${c.id}`}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-3 transition-colors",
                unread
                  ? "border-primary/30 bg-accent/40 hover:border-primary/60 hover:bg-accent/70"
                  : cn("border-border bg-card", buttonFx.surface),
              )}
            >
              <AvatarImg src={avatar} name={name} alt="" className="size-11 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={cn("truncate", unread ? "font-semibold" : "font-medium")}>{name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {c.lastMessageAtUtc ? timeAgo(c.lastMessageAtUtc, tz) : ""}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center justify-between gap-2">
                  <p
                    className={cn(
                      "truncate text-sm",
                      unread ? "font-medium text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {c.lastMessagePreview || "No messages yet"}
                  </p>
                  {unread ? (
                    <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">
                      {c.unreadCount}
                    </span>
                  ) : null}
                </div>
              </div>
              <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
