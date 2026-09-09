// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * The message action menu: Reply / Delete / More info. Opened by a long-press
 * (touch) or right-click (desktop) on a bubble, the gesture detection lives in
 * message-bubble; this component is the floating menu + the "More info" modal.
 *
 * The menu is an absolutely-positioned popover (modeled on the StatTile tooltip)
 * with a full-screen backdrop that catches an outside tap/click, one code path
 * that works as a right-click menu on desktop and a long-press menu on touch.
 * No dropdown primitive exists in the app, so it's built here.
 */
import { useState } from "react";
import { Info, Reply, Trash2 } from "lucide-react";
import type { Message } from "@/types/domain";
import { Modal } from "@/components/modal";
import { formatDate, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function MessageActions({
  message,
  tz,
  open,
  onClose,
  onReply,
  onDelete,
  align,
}: {
  message: Message;
  tz: string;
  open: boolean;
  onClose: () => void;
  onReply?: (m: Message) => void;
  onDelete?: (m: Message) => void;
  /** Which edge to anchor the menu to, matches the bubble's side. */
  align: "start" | "end";
}) {
  const [info, setInfo] = useState(false);
  const canDelete = message.mine && !message.deletedAtUtc && onDelete;

  return (
    <>
      {open ? (
        <>
          {/* Backdrop: catches the outside tap/click that dismisses the menu. */}
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            onClick={onClose}
            onContextMenu={(e) => {
              e.preventDefault();
              onClose();
            }}
            className="fixed inset-0 z-40 cursor-default"
          />
          <div
            role="menu"
            className={cn(
              "absolute top-full z-50 mt-1 w-40 overflow-hidden rounded-xl border border-border bg-popover py-1 text-popover-foreground shadow-lg",
              align === "end" ? "right-0" : "left-0",
            )}
          >
            <MenuItem
              icon={<Reply className="size-4" aria-hidden />}
              label="Reply"
              onClick={() => {
                onClose();
                onReply?.(message);
              }}
            />
            {canDelete ? (
              <MenuItem
                icon={<Trash2 className="size-4" aria-hidden />}
                label="Delete"
                destructive
                onClick={() => {
                  onClose();
                  onDelete?.(message);
                }}
              />
            ) : null}
            <MenuItem
              icon={<Info className="size-4" aria-hidden />}
              label="More info"
              onClick={() => {
                onClose();
                setInfo(true);
              }}
            />
          </div>
        </>
      ) : null}

      <Modal open={info} onClose={() => setInfo(false)} title="Message info">
        <dl className="space-y-2.5 text-sm">
          <InfoRow label="Sent" value={`${formatDate(message.createdAtUtc, tz)} · ${formatTime(message.createdAtUtc, tz)}`} />
          <InfoRow
            label="Delivered"
            value={
              message.deliveredAtUtc
                ? `${formatDate(message.deliveredAtUtc, tz)} · ${formatTime(message.deliveredAtUtc, tz)}`
                : "-"
            }
          />
          <InfoRow
            label="Read"
            value={
              message.readAtUtc
                ? `${formatDate(message.readAtUtc, tz)} · ${formatTime(message.readAtUtc, tz)}`
                : "Not yet"
            }
          />
        </dl>
      </Modal>
    </>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  destructive,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-muted",
        destructive ? "text-destructive" : "text-foreground",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{value}</dd>
    </div>
  );
}
