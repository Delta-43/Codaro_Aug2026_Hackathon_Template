// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Business thread view under the permanent Messages tab. `MessageThread` reads
 * the conversation id from the route params; back returns to the Messages panel.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function OwnerMessagesThreadPage() {
  return <MessageThread backHref="/owner/messages" />;
}
