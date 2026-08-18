/**
 * Client thread view under the permanent Messaging tab. `MessageThread` reads
 * the conversation id from the route params and is shell-agnostic; back returns
 * to the inbox.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function MessagesThreadPage() {
  return <MessageThread backHref="/messages" />;
}
