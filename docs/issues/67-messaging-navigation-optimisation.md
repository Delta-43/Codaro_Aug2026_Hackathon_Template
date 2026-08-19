# Issue #67 — Messaging navigation optimisation

Branch: `67-messaging-navigation-optimisation`

## Why

Yesterday's branch shipped 1:1 messaging, but the inboxes were tucked *inside*
other tabs — the client inbox lived in the Bookings page and the business inbox
inside Requests. Messaging is meant to be the product's hub, so it now gets a
**permanent, central nav button** (button 3 of 5, paper-plane icon), with the
surrounding tabs re-slotted so five buttons still fit cleanly.

This pass is **frontend-only**. Behaviours that need backend work — auto-starting
a thread on approval ("The business approved your request"), turning requests
into literal threads, and an **Archived** view (needs a conversation
`archived_at` flag) — are deferred to a second pass (see below).

## Target nav bars (both shells, Messaging centred)

| # | User mode | icon | Business mode | icon |
|---|-----------|------|---------------|------|
| 1 | Search | `Search` | Dashboard | `Rocket` |
| 2 | Services | `Store` | Services | `SlidersHorizontal` |
| 3 | **Messaging** | `Send` | **Messages** | `Send` |
| 4 | Bookings | `CalendarDays` | Bookings | `CalendarDays` |
| 5 | Profile | `CircleUser` | Profile | `CircleUser` |

`Send` is lucide's paper plane. Both bars stay at 5 tabs (marketplace user's
Calendar folds into Bookings; business's Requests + Calendar collapse into
Messages + Bookings).

**Single-business customer mode also keeps 5 tabs** — there's no discovery, so
Search drops and the availability **Calendar un-merges back out** of Bookings:
`Services · Calendar · Messaging · Bookings · Profile` (Messaging still centred).
There, Calendar is the availability/booking flow and Bookings is the list only
(no my-bookings calendar, since a dedicated Calendar tab covers it). In the
marketplace, Bookings keeps the merged my-bookings calendar + list.

## What changed

### Nav shells + unread badge
- `frontend/src/components/app-shell.tsx`, `frontend/src/components/business/business-shell.tsx`
  — reordered `TABS`, added the centred Messaging/Messages tab (`Send`), Bookings
  now uses `CalendarDays`. Added a `TabBadge` (exported from `app-shell`) shown on
  the messaging tab, fed by a new hook.
- `frontend/src/hooks/use-unread-count.ts` — sums unread across `getConversations()`,
  refetches on window focus; shell-agnostic (no AppProvider dependency).

### Messaging as its own tab
- New `frontend/src/app/(app)/messages/page.tsx` (inbox + empty state) and
  `messages/[conversationId]/page.tsx` (thread). Deleted the old
  `bookings/messages/…` thread route.
- New `frontend/src/app/owner/messages/page.tsx` — the **Messages panel**: pending
  request cards + the auto-approve switch at the top (moved from the old Requests
  page), then the conversation inbox. New `owner/messages/[conversationId]/page.tsx`.
- Reused `MessagingSection`, `ConversationList`, `MessageThread` unchanged.

### Calendar + Bookings merged
- `frontend/src/app/(app)/bookings/page.tsx` — a month/week/day calendar of the
  customer's own bookings on top (reuses `BookingCalendar` via a local
  `Booking → DemoBooking` mapper; a calendar tap deep-links to the booking
  detail), then the existing Upcoming/Past list. The embedded inbox was removed.
  The my-bookings calendar is **marketplace-only** — in single-business mode it's
  hidden (and its fetch skipped) because that mode has its own Calendar tab.
- New `frontend/src/app/owner/bookings/page.tsx` — the owner calendar (moved) plus
  an Upcoming/Past list of the same feed below it.
- The customer availability/booking flow lives at `(app)/calendar`: a **non-tab
  route** in the marketplace (reached from selecting a service), promoted to a
  **top-level Calendar tab in single-business mode** (the un-merged 5th tab).

### Services tab → followed-businesses experience
- New `frontend/src/components/provider/provider-profile.tsx` — the reusable
  business profile (cover/avatar/meta/follow + **Message**/bio/links/services),
  extracted from the old Services page. Booking a service locks that provider in
  then routes to the calendar, so it works for any profile shown.
- New `frontend/src/components/provider/following-services.tsx` — top-3 followed
  strip (the viewed one wears a **pink aura halo**) + a quick view of the selected
  business, with a small back-stack: **Show full bio** → full-screen bio;
  **View more** → all-following list → drill into any bio → back unwinds.
- `frontend/src/app/(app)/provider/page.tsx` — thin container: marketplace + ≥1
  follow → `FollowingServices`; else a single business profile; else an empty
  state. Wired up the previously dead "Message this business" action.

### Retired routes → redirects
- `owner/requests`, `owner/calendar`, and `owner/requests/messages/[conversationId]`
  are now redirect stubs to `/owner/messages` / `/owner/bookings` (deep links
  preserved). Owner dashboard CTAs repointed to the new routes.

## Deferred to pass 2 (needs backend)
- Auto-thread on approval (`POST /bookings/{id}/approve` opens the thread + posts
  "The business approved your request").
- Requests rendered as literal threads.
- Conversation `archived_at` flag + an Archived view in the business Messages panel
  (plus the `test-writer` coverage).

## Verification
- `make start`; sign in as `demo@codaro.app` (client) and `owner@codaro.app` (owner).
- Both bars: 5 items, paper-plane Messaging centred, unread badge on it.
- Messaging tab lists threads and opens them; "Message this business" (Services)
  and "Message client" (owner Bookings modal) land in the new routes.
- Bookings tab: client sees a calendar of their bookings + Upcoming/Past list;
  owner sees calendar + list; approve/reject still works from Messages.
- Services tab: top-3 strip with a pink halo on the viewed business; Show full
  bio / View more back-stack works; single-business vertical still shows one Home.

> Note: automated verification (dev server / build) could not be run in the
> authoring session due to a transient tool-availability outage; the changes were
> reviewed statically. Run `make start` (or `next dev`) to confirm before merging.
