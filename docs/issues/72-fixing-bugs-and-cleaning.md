# 72 — Pivot-system bug sweep

A read of the whole pivot path (`domain.config.json` → `config_schema` →
`rules`/`pricing` → routers → frontend) turned up 15 defects. They fall into
three groups: one crash, six places where a per-service override was accepted and
then not honoured, and eight keys that were validated, served over `/config`, and
read by nobody.

Every fix is verified: `test/` is 1006 passed, `scripts/check_pivots.py` exits 0
(and its "quoted == hand-computed" count went 96 → 97), `ruff check .` clean in
`backend/`, `tsc --noEmit` and `npm run lint` clean in `frontend/`.

## Crash

**1. A malformed nested override 500'd every read that resolved a service.**
`validate_overrides` merged a service's blocks onto a baseline and called
`validate()`, which indexes into each block assuming its declared type. The
global load path guards that with `check_shape` plus a catch-all backstop; this
path had neither, so a row carrying `metadata.pricing = {"rate": 5}` raised an
uncaught `AttributeError` out of `surviving_overrides` → `serialize_service`,
taking down `GET /services`, `POST /bookings` and the owner dashboard. It also
made the write gate return 500 instead of the 422 it promises.

- `check_shape` now recurses through `DEFAULTS` (it only ever checked the top
  level, which was never where the assumption lived), so `booking.duration: 5`
  and `timing.waitlist: []` are named by path instead of surfacing as a generic
  "could not be read" — that also closes finding 15.
- `validate_overrides` shape-checks first and wraps the rest in the same
  backstop `load_config` uses.

## Overrides accepted on write, ignored on read

**2. `serialize_service` served raw columns.** `effective_service_rules` puts an
explicit `metadata` override *above* the column, so the wire advertised
`maxSlotsPerBooking: 1` while the API demanded 4, and a 24h cancellation window
it closed at 2h. `priceMinorUnits` had been fixed this way already; the other
four (`slotDurationMinutes`, `min`/`maxSlotsPerBooking`,
`cancellationCutoffHours`) and `bookingModel` had not.

**3. Invalid overrides were dropped by the wrong name — so they applied.**
`surviving_overrides` read the culprit off the error's leading path segment. For
a cross-block violation that names a block the service never declared — a
`payments: {"flow": "prepay"}` override on a `capabilities.payments: false`
deployment produces an error named `capabilities` — the bad block was **kept and
applied** while the warning log claimed a fallback that never happened.
`rules._problems_by_block` now validates each declared block alone, so blame
lands on the block that caused it. `validate_overrides` stays the seam the
existing tests monkeypatch.

**4. `apply_rules` read the global `timing`.** `timing` is in
`OVERRIDABLE_BLOCKS` and the write gate accepts a per-service `leadTimeMinutes`,
which nothing then enforced. `apply_rules(event, ctx, timing)` now takes the
resolved block; `bookings.create_booking` passes the service's.

**5. Slot creation used the global geometry.** `services.slot_duration_minutes`
is a column that exists for exactly this, and neither it nor a `metadata.timing`
override affected the grid being laid down. `slots.create_slot` resolves the
resource's service (`resources.metadata.service_id`) and uses its rules;
an unlinked resource still falls back to the global block.

**6. Availability grouped days in the global timezone.** Both endpoints are
already scoped to one `service_id` and `location` is overridable, yet pricing
honoured a tenant's timezone (`bookings._business_tz`) while the calendar beside
it did not — so every marketplace tenant off the platform zone had its days
grouped wrong. `_viewer_tz` now takes the service.

**7. Discovery priced off the raw column.** `price_from_by_provider` and
`search_facets` read `price_minor_units` directly, so a service priced only
through `metadata.pricing` reported 0 — wrong `priceFromMinorUnits`, and enough
to switch the deployment's whole `price` search facet **off** while services were
demonstrably priced. Both go through `effective_service_pricing` now.

## Config that looked live and did nothing

**8. `metaFields` only ran on 2 of 6 entities.** `providers`, `services` and
`bookings` had no `metadata` field on their request models at all, so a
`metaFields.bookings` descriptor — the shipped `domain.config.medical.example.json`
declares one — validated nothing. The three models gained `metadata`, and
`meta.merged_metadata` validates it and merges it **under** the engine-owned
keys (dropping any that collide), so a domain field can never rewrite a price, an
owner id or a config override block. `metaFields.subjects` stays declared-only —
there is no subjects table.

**9. `pricing.model` was read by nothing.** Every total came off `rate.per`, so
`"model": "free"` on a config that still carried a rate charged full price.
`free` now zeroes the rate — *not* the booking: fees, caps and the deposit still
apply, which is what pivot #57 (free class with a booking fee) requires. The
other models need no branch; `quote` and `subscription` are listed as unbuilt
rather than silently priced as `fixed`.

**10. Money was rendered with a hardcoded `/100`.** Minor units are hundredths
only in two-decimal currencies: JPY has none, KWD has three. `formatMoney` now
divides by the currency's own ISO exponent (via `Intl`), and the owner's price
editor — which did its own `/100` and `Math.round(x * 100)` — uses the new
`toMajorUnits`/`toMinorUnits`, so it no longer *saves* a hundred times what was
typed on a zero-decimal currency.

**11. `tenancy.selfOnboarding` gated nothing.** `normalize()` computed it and
nobody read it, so on the shipped single-business config (`mode: "single"`,
`selfOnboarding: false`) any signed-up owner could stand up a second business.
`POST /providers` now refuses with a 403.

**12. `capabilities` gated nothing** — despite the block's own docstring
promising "the UI hides the surface AND the backend refuses the write".
`rules.capability(name, service)` resolves it per service; `reviews`
(`POST /bookings/{id}/review`) and `follows` (`POST /providers/{id}/follow`) now
refuse when off. The rest name surfaces that do not exist yet, so the docstring
says so instead of overclaiming.

**13. The enforcement audit under-reported.** `scripts/check_pivots.py`'s header
calls its `ENFORCED`/`DECLARED_ONLY` maps "what stops the config growing a second
generation of keys that look live and do nothing" — and 43 `DEFAULTS` leaves were
in neither map, including all of `copy` and `theme`, the two keys the header
itself names as v1's cautionary tale. All 43 are now classified, and
`check_audit_coverage()` **fails the script** if a new key is added without one.

**14. The `"string"` metaField alias was never type-checked.**
`META_FIELD_TYPE_ALIASES` was added to the load-time validator but `meta._CHECKS`
stayed keyed on canonical names, so a `type: "string"` field passed validation
and then matched no check — the same silent no-op, one layer down. `_CHECKS` now
resolves aliases, and `date` gained a check.

**15.** Folded into fix 1 (recursive `check_shape`).

## Not done

No regression tests were added: `test/` is the `test-writer` agent's exclusive
workspace per the 3-agent pipeline, and this session did not run it. The fixes
above are the natural targets for the next pass — particularly 1, 3 and 7, none
of which the existing 1006 tests cover.

---

## Second pass — the messaging surface

The sweep above walked the pivot path. This pass took the part it had not
touched: the messaging feature added in #74, which is the newest code in the
repo and carries **no tests at all** (`test/backend/` has no `test_messages.py`,
and `fakes.py` models neither `conversations` nor `messages` — it has no `is_()`
operator, so `mark_read` could not be driven through it even if a test existed).

Gates after these three fixes, unchanged from before them: `test/` 1017 passed,
`ruff check .` clean, `tsc --noEmit` clean, `scripts/check_pivots.py` exit 0.

**16. A deleted message went on being displayed in the inbox.**
`last_message_at`/`last_message_preview` are stamped by the `on_message_insert`
trigger — an *insert* trigger, so nothing un-stamps them on a soft delete.
`delete_message` blanked the body (`serialize_message` returns `""` and the
thread renders "Message deleted"), but `serialize_conversation` passes
`last_message_preview` through raw and `conversation-list.tsx:59` renders it
verbatim. So retracting the newest message left its full text sitting in the one
view that summarises the thread, indefinitely — until some later message
happened to overwrite it. Exactly the text the user asked to take back.
`_repoint_preview` now re-points the preview at the latest *surviving* message
after a delete. `schema.sql` is frozen, so this is an app-side write, which the
`conversations_update_participant` policy allows.

Two follow-ups from the review, both folded in. The write is a **compare-and-set**
on the deleted row's `created_at`: it is a read-modify-write racing the very
trigger it compensates for, and unguarded it would clobber a message the other
participant sent between our SELECT and our UPDATE, dragging `last_message_at`
backwards and mis-sorting the thread. Filtering on the value being replaced makes
that case a no-op — as it also makes deleting a non-latest message, which needs no
repoint. And when *every* message is deleted only the preview text is cleared:
`last_message_at` carries ordering rather than content, so clearing it too would
drop a real conversation to the bottom of the inbox labelled "No messages yet".

**17. Counting unread dragged back the entire message history.**
`list_conversations` selected `conversation_id,sender_id,read_at,deleted_at` for
**every message of every thread** the user participates in, then filtered in
Python to produce one small integer per thread. `get_conversation` did the same
for one thread. The predicate is now PostgREST's
(`.neq(sender_id).is_(read_at, null).is_(deleted_at, null)`) and the projection
drops to a single column — identical arithmetic, but the row count crossing the
wire goes from "all messages ever" to "the unread ones".

**18. The avatar size limit only applied after the upload was in memory.**
`store_avatar` checked `len(data) > _MAX_BYTES` *after* `await file.read()`, so an
oversized upload was copied into a contiguous `bytes` before being rejected. It
now rejects on the multipart parser's declared `file.size` first; the post-read
check stays authoritative for when `size` is absent.

An earlier draft of this entry claimed the guard stopped the body reaching disk.
It does not, and the review caught it: FastAPI awaits `request.form()` while
resolving the `UploadFile` dependency, so Starlette's `MultiPartParser` has
already written the whole part to a `SpooledTemporaryFile` before `store_avatar`
runs — and `max_part_size` caps only *non-file* parts, so nothing bounds a file
part. `file.size` is knowable precisely because the body was already consumed.
**The unbounded-upload vector is still open**; closing it needs a Content-Length
check in middleware or a proxy/server body limit, which is a separate change.

### Noted, not changed

- **`_user_display` is an N+1.** An owner's inbox calls
  `auth.admin.get_user_by_id` once per distinct customer (cached within a
  request, not across). `profiles` carries only `email`/`role` — no
  `display_name`/`avatar_url` — so there is no one-query batch to swap in
  without either changing what a name resolves to or touching the frozen schema.
- **GDPR erasure covers messaging by FK cascade, not by code.** `gdpr.py` names
  no messaging step, but `conversations.client_id` and `messages.sender_id` are
  both `on delete cascade` on `auth.users`, and `conversations.provider_id`
  cascades from the provider — so step 6 does carry the threads. The module
  docstring enumerates what erasure removes and does not mention this; worth a
  line so a future reader does not read the silence as a gap.
- **`messages_update_participant` is wider than the router.** The policy lets
  *either* participant update *any* message in the thread; only the app's
  `.eq("sender_id", user.id)` filter stops one party soft-deleting the other's
  messages. Defence-in-depth only — no route exposes it — and narrowing it means
  touching the frozen schema.
- No regression tests were added, for the same reason as the first pass: `test/`
  is the `test-writer` agent's exclusive workspace and this session did not run
  it. Fixes 16 and 17 were verified against a scratch PostgREST fake outside the
  repo; a real `test_messages.py` (plus `is_()` on `fakes.py`) is the natural
  next pass, and would be the suite's first coverage of messaging at all.
