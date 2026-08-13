# AGENTS.md — Codaro Hackathon, Track B (Resource Booking & Scheduling)

> **Read this file first, every time.** This is the shared memory for the project — for every teammate and every AI agent/session that touches this repo. Before doing any work, read this whole file. After finishing any meaningful chunk of work, append a dated entry to the **Decisions & Progress Log** at the bottom. Keep entries short — a few lines, not a essay.
>
> For the raw, action-by-action sequence of everything done so far (not just the curated summary below), see **`HISTORY.md`** in this same folder.

---

## 1. Event & Team

- **Event:** Codaro Hackathon, Warsaw, August 2026 (codaro.dev/hackathon)
- **Track:** B — Resource & Slot Booking / Scheduling
- **Team members / roles:** Alban (stack research), Delta (project brief/coordination), Ola (database — see `Ola/supabase`), Philip (frontend, "pretty UI, liquid glass"), Peter (TBD), Rysia/Aryna (building a full independent stack solo, this folder, for a deep understanding of the whole app before the event)
- **Repo:** _fill in GitHub URL_
- **Key constraint:** mid-event, the organizers will announce a **pivot** — the app's purpose, look, and usage may need to change substantially with only ~2 hours to adapt. Every decision below is made with that in mind. See §6.

## 2. MVP Scope (Track B minimum requirements)

1. **Resource & slot management** — define bookable resources, each with a schedule of time slots.
2. **Booking & confirmation** — a user can book an available slot and receive confirmation.
3. **Change & cancellation** — a user can modify or cancel an existing booking, subject to business rules.
4. **Availability view** — a calendar/grid view showing what's free/booked per resource.

Everything else (auth polish, notifications, payments, etc.) is stretch scope — only build it once the four items above work end-to-end.

## 3. Tech Stack & Why

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui | Fast to scaffold, component-driven, easy to reskin (important for the pivot) |
| Calendar UI | react-big-calendar (fallback: FullCalendar if we need more built-in views) | Handles availability/booking views out of the box |
| Backend | Python FastAPI | Async, straightforward for booking logic, fast to iterate |
| Database | Supabase (PostgreSQL) | Managed Postgres + auth + realtime if we need it; schema: `resources → slots → bookings` |

_If any of these change, update this table and say why in the log below — don't just silently drift._

## 4. Business Rules (living list)

These live in **one isolated module** (`backend/rules.py` or equivalent) as small, pure, named functions — never scattered inline in route handlers. This is what makes them safe to change fast during a pivot.

- **Cancellation window:** _fill in, e.g. "can cancel up to X hours before slot start"_
- **Max bookings per slot:** _fill in, e.g. capacity per resource_
- **Buffer time between slots:** _fill in, e.g. 15 min gap enforced per resource_
- _More rules will surface as we build — add them here as soon as they're decided, don't let them live only in code._

Inspiration for what "good" looks like: Zoho Bookings, Preply, Booking.com, Uber — look at how they handle overbooking, buffer time, and cancellation policy UX, not just the visuals.

## 5. Pivot-Readiness Principles (the whole point of this doc)

The organizers can change the app's *purpose* mid-hackathon. The underlying model — `resource → slot → booking` — is intentionally generic (a "resource" could be a tutor, a room, a car, a driver). To survive a pivot in 2 hours:

1. **One config file drives naming/branding/copy.** Labels like "Resource," "Slot," "Booking," theme colors, and app name live in a single config (e.g. `config/app.config.ts` on frontend, `.env`/`config.py` on backend) — never hardcoded in components or routes. Pivoting the *look and vocabulary* of the app should mostly mean editing this file.
2. **Business rules are isolated, named functions**, not inline conditionals — see §4.
3. **Functions and components stay short and single-purpose.** If a function does more than one thing, split it. Small pieces are swappable; a 200-line function is not.
4. **No premature abstraction.** Don't build a plugin system or generic framework "just in case" — that adds complexity without buying speed. Straightforward, small, readable files beat clever architecture here.
5. **Every non-obvious decision gets logged** (§7) so a teammate — or a fresh AI session with zero memory of this conversation — can get up to speed in under a minute.

## 6. Repo / File Map (this folder — `Rysia/`)

```
Rysia/
  AGENTS.md            — this file (curated decisions log)
  HISTORY.md           — raw chronological action log (every step, in order)
  KICKOFF_PROMPT.md     — reusable prompt template
  supabase/
    schema.sql          — resources, slots, clients, bookings + capacity trigger + availability view (done)
    DECISIONS.md         — why each schema/enforcement choice was made (done)
  backend/              — FastAPI app (next up)
  frontend/             — Next.js app (after backend)
```

Note: `Ola/` has a parallel, independently-built version of the same schema (with an added audit-trail table). Worth comparing the two before the team merges on one for the real submission.

## 7. Decisions & Progress Log

_Newest entries on top. Format: `YYYY-MM-DD — who — what/why`._

- **2026-08-13 — Aryna (with Claude) — FastAPI backend scaffolded (`Rysia/backend/`).** Minimal app with one `/health` endpoint, tested locally in the build sandbox before delivery (real request, real `{"status":"ok"}` response — not just written and assumed correct). Next: connect it to Supabase (need project URL + API key from Aryna) and build the first real endpoint, `GET /availability`.
- **2026-08-13 — Aryna — schema live-tested on a real Supabase project, capacity rule confirmed.** `schema.sql` ran cleanly via the Supabase SQL Editor (couldn't connect via `psql` from the build sandbox — its network blocks direct Postgres connections, both the IPv6-only direct host and the IPv4 pooler on port 5432 — so the SQL Editor is the working path for running SQL against Supabase from here on). Smoke test: one resource (capacity 1) + one slot + two clients; first booking succeeded, second was correctly rejected by the capacity trigger. Still open: a true concurrent-request test (two bookings at the exact same instant) — needs a real API endpoint to hit, deferred to the FastAPI task. Full step-by-step in `HISTORY.md`.
- **2026-08-13 — Aryna (with Claude) — research pass, fixed a real concurrency bug.** Researched booking-platform business rules, REST API security, Supabase RLS, and FastAPI security (sources in `Rysia/supabase/DECISIONS.md`). Found and fixed a genuine race condition in the capacity trigger: it counted bookings without locking the slot row first, so two simultaneous bookings on the last open spot could both succeed (silent overbooking). Fixed with `SELECT ... FOR UPDATE` to serialize concurrent bookings on the same slot. Also planned (not yet built): idempotency keys on the booking endpoint, RLS policies once Supabase auth exists, and a FastAPI security checklist (input validation, rate limiting, CORS, JWT auth, `/docs` disabled in prod) — all tracked for the backend task.
- **2026-08-13 — Aryna (with Claude) — database schema built solo (`Rysia/supabase/schema.sql`).** Built `resources -> slots -> clients -> bookings` from scratch (independently of Ola's version — see `Ola/supabase` for comparison; both converged on the same core shape, which is a good sign it's the right model). Key decision: capacity is enforced with a DB trigger (race-condition risk on simultaneous bookings), while buffer time and cancellation window are enforced in FastAPI instead (no concurrency risk, better error messages, easier to change during a pivot). Full reasoning in `Rysia/supabase/DECISIONS.md`. No audit/history table yet — not in Track B's minimum requirements, added as a stretch goal if time allows. Next: FastAPI backend implementing booking, confirmation, cancellation (with the window check), and availability query.
- **2026-08-13 — Aryna (with Claude) — kickoff.** Confirmed Track B scope, stack (Next.js/Tailwind/shadcn + FastAPI + Supabase), and pivot-readiness principles. Created this file and the kickoff prompt (`KICKOFF_PROMPT.md`).

## 8. Pivot Playbook

_When the pivot is announced, do these in order:_

1. Re-read the new prompt/theme from organizers. Write it here as a new log entry immediately.
2. Update `config/app.config.ts` (and backend `config.py`) — names, labels, theme colors, copy.
3. Check §4 business rules — do the numbers/rules change (e.g. different cancellation window)? Update `rules.py` and this doc.
4. Check if the *meaning* of "resource" changes (e.g. tutor → car). Usually no schema change needed — just labels — but verify.
5. Do NOT rewrite booking/slot logic from scratch unless the data model genuinely no longer fits. Re-skin and re-label first; that's usually 90% of the pivot.
6. Log what changed and why, immediately after.
