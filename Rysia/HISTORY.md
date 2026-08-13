# HISTORY.md — chronological action log (Rysia's build)

This is the raw, ordered record of every action taken on this part of the project — oldest first. Anyone (human or AI) picking this up should be able to reconstruct exactly what happened and in what order by reading top to bottom.

This is different from `AGENTS.md`'s Decisions & Progress Log: `AGENTS.md` §7 holds the *curated, high-level* "what was decided and why" (a few lines per major step). This file holds *every concrete action*, in order, including the small ones. When in doubt: skim `AGENTS.md` for the summary, read `HISTORY.md` for the play-by-play. New entries always get appended at the bottom.

---

1. **Kickoff conversation.** Discussed the Codaro Hackathon Track B requirements (resource & slot, booking & confirmation, change & cancellation, availability view), the pivot constraint (purpose/look can change with ~2 hours notice mid-event), and the intended stack: Next.js 14 + Tailwind + shadcn/ui (frontend), Python FastAPI (backend), Supabase/Postgres (database).

2. **Created `AGENTS.md`** — the shared memory-map file: project overview, MVP scope, tech stack + rationale, business rules placeholder, pivot-readiness principles, file map, decisions log, and a pivot playbook.

3. **Created `KICKOFF_PROMPT.md`** — a reusable prompt template so any teammate/AI session starts by reading `AGENTS.md` and works in small, acceptance-criteria-scoped steps.

4. **Connected to Aryna's Mac** via the device bridge and located the team repo at `~/Codaro_Aug2026_Hackathon_Template`.

5. **Inspected the existing `Rysia` entry** in the repo — it was a placeholder text file ("i am a contributor as well :)"), not a folder. Moved it to `_to_delete/Rysia_placeholder_file` (couldn't be deleted outright — the device bridge has no delete permission) and created a real `Rysia/` folder in its place.

6. **Wrote `AGENTS.md` and `KICKOFF_PROMPT.md` into `Rysia/`.**

7. **Attempted `git add`/`commit` via the device bridge** to push the change — hit a permissions wall: the bridge can't delete files, and git's own lock-file cleanup failed mid-command, leaving a stale `.git/index.lock`. Stopped before risking more git commands; handed the final `rm .git/index.lock && git add -A && git commit && git push` sequence to Aryna to run herself.

8. **Reviewed the rest of the repo** to understand what teammates had already built: `Alban.MD` (stack research + pivot notes), `Delta.md` (project brief, same stack + Track B minimum requirements), `Ola/` (a fully worked-out Postgres schema for `resources → slots → clients → reservations → reservation_events`, including a capacity trigger, buffer/cancellation columns, an occupancy view, and a Track B terminology-mapping plan), `Peter` (placeholder, no real content yet), `Philip` (frontend ownership, no code yet).

9. **Updated `AGENTS.md`** with the real team roles discovered above and a note that Ola's schema exists as a parallel reference.

10. **Decision: build Rysia's own full stack from scratch**, independently of Ola's version, so Aryna learns the structure and logic hands-on rather than reusing someone else's finished work.

11. **Designed and wrote `Rysia/supabase/schema.sql`** — `resources → slots → clients → bookings`, with `capacity`, `buffer_minutes`, and `cancellation_window_hours` as columns on `resources` (data, not hardcoded rules), a capacity-enforcing trigger, and an `availability` view for the frontend calendar.

12. **Wrote `Rysia/supabase/DECISIONS.md`** explaining every schema choice: why this shape, why business rules are columns, why capacity is DB-enforced but buffer time/cancellation window are left to the API layer, why `clients` is a standalone table for now, why there's no audit table yet, and what's deliberately deferred (RLS, Realtime, recurring slots).

13. **Delivered and committed** `schema.sql`, `DECISIONS.md` to `Rysia/supabase/`, and the updated `AGENTS.md` to Aryna's machine.

14. **Ran a research pass** (4 web searches + 5 page fetches) on booking-platform business rules/double-booking prevention, REST API security, Supabase Row Level Security, and FastAPI security best practices, before continuing to build.

15. **Found and fixed a real concurrency bug** the research surfaced: the capacity trigger counted existing bookings without locking the slot row first, so two simultaneous booking requests on the last open spot could both pass the check and both succeed — silent overbooking. Fixed by adding `SELECT ... FOR UPDATE` on the slot row before counting, forcing concurrent requests on the same slot to serialize correctly.

16. **Updated `DECISIONS.md`** with the research findings, the bug explanation, sources, and a forward plan for idempotency keys, RLS policies (once auth exists), and FastAPI-layer security — deliberately not applied yet since they need infrastructure (a real Supabase project, auth) that doesn't exist yet.

17. **Updated `AGENTS.md`'s decisions log** to match, and re-delivered/committed all three files.

18. **Created this file, `Rysia/HISTORY.md`.**

19. **Attempted to run `schema.sql` against a live Supabase project via `psql` from the cloud sandbox.** Failed twice for infrastructure reasons, not schema reasons: the direct-connection hostname (`db.xxx.supabase.co`) only resolves to IPv6, which this sandbox can't route; the session-pooler hostname resolves to IPv4 fine, but the sandbox's outbound network only allows a limited set of destinations and silently blocks arbitrary port 5432 connections. Switched approach: use Supabase's built-in SQL Editor (browser-based, no networking/credentials needed from this side) instead.

20. **Ran `schema.sql` successfully in the Supabase SQL Editor** (project "Rysia's Project") — all tables, the capacity trigger, and the `availability` view created with no errors.

21. **Smoke-tested the capacity trigger for real**, sequentially through the SQL editor: created a test resource (capacity 1), one slot, two clients. Client A's booking succeeded (`confirmed`). Client B's booking on the *same* slot failed with `ERROR: P0001: slot ... is already at capacity` — exactly the error the trigger is designed to raise. This confirms the capacity rule fires correctly for sequential requests. Noted as a follow-up: this doesn't yet prove the true-concurrency case (two simultaneous requests) that the `FOR UPDATE` lock specifically guards against — that needs an actual concurrent test once the FastAPI endpoint exists, tracked under Task #2.

22. **Cleaned up test data** (test resource/slot/bookings/clients) from the live database.

23. **Scaffolded `Rysia/backend/`** — a minimal FastAPI app (`app/main.py`) with a single `/health` endpoint, `requirements.txt`, and a `README.md` quick-start. Installed the dependencies and ran the server in the build sandbox to confirm `/health` actually returns `{"status":"ok"}` before sending it over — nothing delivered unverified.

24. _(next)_ Wire the backend to Supabase (needs the project URL + an API key from Aryna), then build the first real endpoint: `GET /availability`, reading the `availability` view built earlier.
