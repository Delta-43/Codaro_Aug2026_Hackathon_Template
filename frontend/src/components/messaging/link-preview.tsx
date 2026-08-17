"use client";

/**
 * A lightweight, CLIENT-ONLY link chip. It regex-detects the first URL in a
 * message body and renders a bordered card with a globe icon + hostname — no
 * fetch, no OpenGraph, no backend work (a deliberate scope guardrail). The chip
 * reads on both bubble variants (semi-transparent card over either background).
 */
import { Globe } from "lucide-react";

const URL_RE = /https?:\/\/[^\s]+/i;

export function LinkPreview({ body }: { body: string }) {
  const match = body.match(URL_RE);
  if (!match) return null;
  // Trim trailing sentence punctuation that isn't part of the URL.
  const raw = match[0].replace(/[.,;:!?)\]]+$/, "");
  let host: string;
  try {
    host = new URL(raw).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
  return (
    <a
      href={raw}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="mt-1.5 flex items-center gap-2 rounded-xl border border-border bg-background/70 px-2.5 py-1.5 text-xs text-foreground no-underline transition-colors hover:bg-background"
    >
      <Globe className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
      <span className="truncate font-medium">{host}</span>
    </a>
  );
}
