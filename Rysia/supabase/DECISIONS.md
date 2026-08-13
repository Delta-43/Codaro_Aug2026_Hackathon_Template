# Schema decisions — Rysia's build

Why the database looks the way it does. Read this alongside `schema.sql`.

## Why `resources -> slots -> bookings` and not something fancier

This is the whole domain in three nouns: a bookable *thing* (resource), a bookable *window of time* on that thing (slot), and someone claiming that window (booking). Every example we looked at — Zoho Bookings, Preply, a restaurant table, a doctor's appointment — reduces to this same shape. That's exactly why it survives a pivot: the pivot changes what a "resource" *represents* (tutor → doctor → car), not the shape of the data.

## Why business rules are columns on `resources`, not constants in code

`capacity`, `buffer_minutes`, `cancellation_window_hours` live on each resource row instead of being a number baked into a function. Two reasons: different resources can have different rules (a shared meeting room might allow capacity 8, a 1:1 tutor session capacity 1), and when the pivot changes the rule ("doctors need 24h cancellation notice, not 2h"), that's an `UPDATE` statement, not a code deploy.

## Why capacity is enforced with a DB trigger, but buffer time and cancellation window are NOT

Three business rules, three different enforcement points — this is a real design decision, not laziness:

- **Max bookings per slot (capacity):** enforced in the database via `check_slot_capacity()`. This is the one rule where a race condition matters — two people could hit "book" on the last spot in the same slot within milliseconds. Only the database can guarantee that check-and-insert happens atomically. If you only checked this in FastAPI, two simultaneous requests could both pass the check before either one has written its row, and you'd overbook.
- **Buffer time between slots:** this only matters *when slots are created* (someone scheduling a resource's calendar), not when someone books an existing slot. There's no race condition risk — slot creation is a low-frequency, usually-single-admin action. So it's simpler and just as safe to check it in the FastAPI layer, right before inserting a new slot: "does this overlap another slot on the same resource within `buffer_minutes`?"
- **Cancellation window:** this is a business rule about *time*, not about concurrency — "is `now()` within `cancellation_window_hours` of `slot.start_time`?" Nothing bad happens if two people check this at once. Keeping it in FastAPI means the error message can be specific and friendly ("you can't cancel within 2 hours of your appointment") instead of a raw database exception.

Rule of thumb we're using: **enforce in the database only when a race condition could otherwise cause bad data.** Everything else goes in the API layer, because it's faster to write, easier to give good error messages, and easier to change during the pivot.

## Why `clients` is its own table (for now)

Keeps the schema fully working with zero external dependencies while we're building against a fresh Supabase project. If we wire up Supabase Auth later, `clients` can be swapped for a view over `auth.users` — nothing in `slots`, `resources`, or `bookings` needs to change, because they only reference `clients.id`.

## Why there's no audit/history table yet

Track B's minimum requirements are resource+slot, booking+confirmation, change+cancellation, availability view — an audit trail isn't in that list. Adding one later (a `booking_events` table logging every status change) is a clean, additive change — a new table, not a rework of anything above — so it's a good stretch goal once the MVP works end-to-end, not a day-one requirement.

## The `availability` view

This is what the frontend calendar queries directly (Supabase client can hit it without going through FastAPI at all) — it pre-joins resources, slots, and live booking counts into `spots_left`, so the calendar UI never has to compute availability itself. Keeping this logic in SQL instead of frontend code means "how many spots are left" can never drift out of sync with the actual booking data.

## Research pass — and a real bug it caught

Before building further, I researched how production booking platforms and Postgres/Supabase/FastAPI experts actually handle this, instead of relying only on my own first draft. That surfaced a genuine correctness bug in the capacity trigger above, now fixed — worth understanding because it's a classic concurrency trap.

**The bug:** the original trigger counted existing bookings for a slot and rejected the new one if the slot was full — but it never *locked* anything first. Under Postgres's default isolation level, if two people click "book" on the last open spot within milliseconds of each other, both transactions can run that count *before either one has committed*. Both see "not full yet," both get inserted, and the slot ends up overbooked — silently, with no error. This is a well-documented failure mode for booking systems (double-booking research specifically flags "atomic transactions" and "the competing transaction should receive a recoverable conflict" as the fix — see sources).

**The fix:** the trigger now runs `select ... from slots where id = new.slot_id for update` before counting. `FOR UPDATE` locks that slot row, so if two bookings for the same slot arrive at the same instant, the second one's trigger simply waits until the first transaction finishes — then it counts against accurate, up-to-date data. This is the standard pattern; the alternative (a Postgres `EXCLUDE` constraint) is cleaner but only works cleanly for capacity-1 resources, so the lock-based trigger was kept since it handles any capacity value.

**Other things the research confirmed we should plan for** (not schema changes, so noted here rather than reworking `schema.sql` again):

- **Idempotency keys on the booking endpoint.** If a client's request times out and retries, the API should recognize the retry and return the original booking instead of creating a duplicate — this becomes a FastAPI concern (Task #2).
- **Row Level Security (RLS), once a real Supabase project + auth exists.** Planned shape: `resources`/`slots` stay publicly readable (anyone browsing availability), only an admin role can write them; `bookings` are only readable/cancellable by the client who made them (`client_id = auth.uid()`) or the resource owner. This requires `clients.id` to actually map to Supabase's `auth.users.id` — a decision to make explicitly once auth is wired up, not before.
- **API security for the FastAPI layer** (tracked for Task #2): validated input via Pydantic constraints, parameterized queries only (never raw string SQL), rate limiting on the booking endpoint specifically (it's the one attackers/bots would hammer), restricted CORS to the actual frontend domain, JWT-based auth via Supabase, and `/docs` disabled or auth-gated in production.

Sources: [Double bookings: why they happen and how systems prevent them (Bookibles)](https://bookibles.com/blog/prevent-double-bookings) · [API Security Best Practices For Booking Platforms (Bookafy)](https://bookafy.com/api-security-best-practices-every-booking-platform-needs/) · [REST API Security Best Practices (StackHawk)](https://www.stackhawk.com/blog/rest-api-security-best-practices/) · [Supabase RLS Best Practices (Makerkit)](https://makerkit.dev/blog/tutorials/supabase-rls-best-practices) · [A Practical Guide to FastAPI Security (David Muraya)](https://davidmuraya.com/blog/fastapi-security-guide/)

## What's deliberately *not* here yet

Row Level Security policies, Supabase Realtime subscriptions, recurring-slot generation. Not skipped by accident — just sequenced later, once the core booking flow works. Enable RLS before the demo, not the night before it (retrofitting it last-minute is genuinely painful — ask anyone who's done it).
