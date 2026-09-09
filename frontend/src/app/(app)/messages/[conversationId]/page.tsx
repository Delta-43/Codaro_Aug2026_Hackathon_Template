// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Client thread view under the permanent Messaging tab. `MessageThread` reads
 * the conversation id from the route params and is shell-agnostic; back returns
 * to the inbox.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function MessagesThreadPage() {
  return <MessageThread backHref="/messages" />;
}
