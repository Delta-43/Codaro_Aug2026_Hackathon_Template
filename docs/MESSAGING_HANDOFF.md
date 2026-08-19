# Messaging — Implementation Handoff (`40-messaging`)

In-app 1:1 messaging between a client and a business (iMessage/WhatsApp-style),
embedded at the top of the client **Bookings** tab and the business **Requests**
tab. This is a **working full-stack slice** (real FastAPI router + real Supabase
tables/RLS/Realtime), not a client-only mock — it was verified end-to-end in the
browser across both personas, including live Realtime delivery and read receipts.

This doc is the technical handoff for the backend/infra team to dispatch into
tickets. It is intentionally separate from `REPORT.md` / `TODO.md`, which are the
3-agent pipeline's whole-repo snapshots (regenerated, not hand-edited).

---

## What's implemented

**Database** — `supabase/schema.sql` (idempotent, appended; frozen base tables untouched):
- `conversations` (one per `(provider_id, client_id)`; denormalized `owner_id`,
  `last_message_at/preview`, `metadata`).
- `messages` (`conversation_id`, `sender_id`, `body`, `reply_to_id`,
  `delivered_at`/`read_at`/`deleted_at` soft-delete, `metadata`).
- RLS: participant-membership policies (client or provider owner) mirroring
  `booking_slots`; insert gated on `sender_id = auth.uid()`.
- `messages replica identity full` (so UPDATE Realtime payloads carry old+new).
- `touch_conversation()` trigger → stamps `last_message_at/preview` on insert.
- Guarded `alter publication supabase_realtime add table messages / conversations`.

**Backend** — `backend/app/`:
- `routers/messages.py` (new): `GET /conversations`, `GET /conversations/{id}`,
  `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages`,
  `POST /conversations/{id}/read`, `DELETE /conversations/{id}/messages/{mid}`,
  `POST /conversations` (find-or-create, client **and** owner directions).
- `serialize.py`: `serialize_conversation`, `serialize_message` (`mine` derived
  per-viewer, soft-deleted body blanked, `…Utc` keys).
- `models.py`: `MessageCreateReq`, `ConversationCreateReq` (CamelModel).
- `main.py`: router registered.
- `seed.py`: `_seed_messages` (+ `messages`/`conversations` added to the reseed
  wipe list) — seeds one two-sided owner↔client thread (with a URL, a reply, and
  unread tips both ways) plus 2 client inquiries.

**Frontend** — `frontend/src/`:
- `types/domain.ts`: `Conversation`, `Message`.
- `api/index.ts`: `getConversations`, `getConversation`, `getMessages`,
  `sendMessage`, `markConversationRead`, `deleteMessage`, `startConversation`.
- `hooks/use-conversation-realtime.ts`: the repo's first `.channel()` — `postgres_changes`
  INSERT/UPDATE + `broadcast` typing; no-ops gracefully when Supabase env is unset.
- `components/messaging/*`: `messaging-section`, `conversation-list`,
  `message-thread`, `message-bubble`, `message-actions`, `link-preview`,
  `typing-indicator` (self-contained, shell-agnostic — read identity from `useAuth()`).
- Placement: inbox in `bookings/page.tsx` + `owner/requests/page.tsx`; thread
  routes under each (`messages/[conversationId]`); "Message" entry points on the
  client provider profile (`provider/page.tsx`) and owner calendar booking modal.

## Verified live (manual, browser)

Client inbox + owner inbox · thread bubbles/timestamps/link-chip/reply-quote ·
send (optimistic → Delivered) · **Realtime** (message appeared in a 2nd tab, no
refetch) · **read receipts** ("Read at HH:MM") · action menu (Reply/Delete/More
info) · soft-delete ("Message deleted") · owner→customer name resolution +
perspective inversion · unread badges + clearing · client "Message" button
creates+opens a fresh thread, then send works.

---

## Action items for the backend / infra team (dispatchable)

### P0 — environment / correctness
- [ ] **Realtime publication is privilege-gated.** `alter publication
  supabase_realtime …` runs inside a guarded block that *silently skips* if the
  DB role lacks privilege. It succeeded on the current project, but on any other
  environment (staging/prod), if it skips, HTTP messaging still works but live
  updates won't. **Verify per environment**; if skipped, enable via
  Dashboard → Database → Replication → add `messages` + `conversations`.
  Frontend Realtime also needs `NEXT_PUBLIC_SUPABASE_URL` / `ANON_KEY`.

### P1 — production hardening
- [ ] **Pagination** on `GET /conversations/{id}/messages` (currently returns the
  entire thread) and on `GET /conversations`. Add cursor/limit.
- [ ] **Input limits**: enforce a max message length and basic rate limiting on
  `POST …/messages` (backend accepts any non-empty body today).
- [ ] **Abuse/moderation** hook if needed (none today).
- [ ] **Cross-user display resolution**: owner-side threads resolve the customer
  name/avatar via `auth.admin.get_user_by_id` (cached per request). Consider
  batching or denormalizing name/avatar onto `conversations` for scale.
- [ ] **Automated tests**: `test/` has **no messaging coverage yet**. Add
  `test/backend` (offline FakeSupabase) cases for each `/conversations` endpoint,
  RLS (non-participant 404/deny), the client-vs-owner `start_conversation`
  direction, serializer `mine`/soft-delete, and `mark_read`. Note the router uses
  PostgREST filters `.is_("read_at","null")`, `.neq`, `.in_`, `.order` and
  `auth.admin.get_user_by_id` — confirm/extend the FakeSupabase double for these.

### P2 — nice-to-have / product decisions
- [ ] **Typing indicator** is wired (ephemeral `broadcast`, no DB) but was not
  visually verified across two live sessions — smoke-test it.
- [ ] **Link preview** is a **client-only** regex chip (hostname + globe icon), no
  OpenGraph fetch — by design. Decide if real previews are wanted.
- [ ] **Read/delete live-flip**: read receipts and soft-deletes propagate via the
  same Realtime UPDATE wiring proven for INSERT; the exact live in-place flip
  wasn't captured — worth a confirmation pass.
- [ ] A benign one-off **400** appears in the browser console on load (Realtime
  socket's initial handshake/retry — it connects fine); don't chase it as a bug.

### Out of scope (per brief) — not built
Group chat, attachments, GIFs, animated reactions, and the "talk to an automated
agent" path.

---

## Run & verify

```bash
make start      # rebuilds + starts frontend :3000 / backend :8000 (schema auto-applies)
make reseed     # seeds demo conversations (also wipes + reseeds demo data)
```

Demo logins: `demo@codaro.app` / `Codaro-Demo-2026` (client, Bookings tab) and
`owner@codaro.app` / `Codaro-Owner-2026` (business, Requests tab). Open the same
thread in two sessions to see Realtime + receipts.

> Env note: the running backend image had been stale and crash-looping on a
> missing `python-multipart` (declared in `requirements.txt`, unrelated to
> messaging — from the profile-picture branch). `make start` rebuilds and fixes
> it; CI should rebuild images on `requirements.txt` changes.
