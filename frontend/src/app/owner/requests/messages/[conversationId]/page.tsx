import { redirect } from "next/navigation";

/**
 * Retired thread route. Business threads now live under the Messages tab; this
 * redirect preserves the conversation id so an old link opens the same thread.
 */
export default function OwnerRequestsThreadRedirect({
  params,
}: {
  params: { conversationId: string };
}) {
  redirect(`/owner/messages/${params.conversationId}`);
}
