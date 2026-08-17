/**
 * Business thread view. `messages` is a literal sibling under the Requests tab,
 * so `startsWith("/owner/requests")` keeps that tab highlighted here.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function OwnerRequestsMessageThreadPage() {
  return <MessageThread backHref="/owner/requests" />;
}
