/**
 * Client thread view. `messages` is a literal sibling of the `[id]` booking
 * detail segment, so there's no dynamic-route collision, and the shell's
 * `startsWith("/bookings")` keeps the Bookings tab highlighted here.
 */
import { MessageThread } from "@/components/messaging/message-thread";

export default function BookingsMessageThreadPage() {
  return <MessageThread backHref="/bookings" />;
}
