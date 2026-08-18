/**
 * Business thread view under the permanent Messages tab. `MessageThread` reads
 * the conversation id from the route params; back returns to the Messages panel.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function OwnerMessagesThreadPage() {
  return <MessageThread backHref="/owner/messages" />;
}
