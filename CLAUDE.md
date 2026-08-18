# Codaro Booking Engine — root guide

## Token budget (read first)

Work to finish the task in as few tokens as possible — tokens are the user's
usage limit. **Screenshots/images are the #1 cost**; prefer text tools and take
at most one, only when a visual result must be shown. Read narrow (`grep` +
`sed -n` ranges, not whole files), don't re-read after editing, batch tool
calls, verify once, and keep prose/commit messages terse. Full rules:
[docs/token-budget.md](docs/token-budget.md). This applies to every agent.

## What this is

A generic booking engine — `provider → service → resource → slot → booking →
user` — built so a completely different niche can be adopted via config +
seed data instead of a rewrite. Multi-slot bookings, party size, reviews,
follows, search, day-availability and month-density all ride on that neutral
spine. Stack: **Next.js 14 + Tailwind** frontend, **FastAPI** backend, hosted
**Supabase (Postgres + Auth)**. See `README.md` for the full run instructions,
`Project_Summary.md` for the original brief, and `REPORT.md` for the current
frontend⇄backend wiring snapshot.

The pivot mechanism: `domain.config.json` (now **v2**, `configVersion: 2`) holds
the engine's **vocabulary + global defaults**. v1's five sections (`terms`,
`copy`, `theme`, `metaFields`, `rules`) only ever described one kind of business —
a time-slot calendar with a price per slot. v2 adds the blocks that let the
*shape* of the offering pivot too: `capabilities`, `booking`, `pricing`,
`payments`, `inventory`, `location`, `prerequisites`, `timing`, `recurrence`,
`entitlements`, `discovery`. It is strictly additive — `rules` and `search`
survive as deprecated aliases kept in sync with `timing` and `discovery`, so a v1
file still boots. The backend normalizes and **validates** it at load
(`app/config_schema.py`), so a typo fails at the edit rather than on the next
booking, and serves it at `GET /config`.

**Config is the default; the service row is the override.** A service's own
columns (duration, min/max slots, cutoff, price, booking model) win over the
config globals via `rules.py` `effective_service_rules`, and
`effective_service_config` lifts the same precedence to whole blocks through
`services.metadata.<block>` — which is what lets two businesses on one
marketplace deployment price and gate completely differently. The frontend renders
vertical vocabulary from `src/config/verticals.ts` (pure UI labels/nouns/copy).
New domain-specific data goes in each base table's `metadata jsonb` column — no
migrations at pivot time. `supabase/schema.sql` is treated as frozen/idempotent
once the event starts (new *entities* are added as new tables, base tables stay
frozen). On the backend, the pivot is enforced by the per-service rule resolver,
the legacy event-keyed rules registry (still used by `slots.py`), and a
config-driven `metaFields` validator — see [backend/CLAUDE.md](backend/CLAUDE.md).

## Auth (Supabase Auth)

Implemented on this branch (`16-auth-system`); it reverses the engine's
original "no auth" stance. Identity moved from *"trust the `client_email` in
the request body"* to **Supabase Auth**: Supabase handles email/password
sign-up + login and issues a JWT. The frontend attaches that JWT as
`Authorization: Bearer <token>`; the backend verifies it (both **ES256 via
JWKS** — this project's scheme — and legacy **HS256**) and reads the user
(`sub`, `email`) from the token instead of trusting the body.

- **Roles stay config-driven.** The owner/client split keeps using
  `terms.admin` / `terms.client`; the `actor` concept became a *verified* role,
  trusted from a `profiles` row rather than an unchecked flag.
- **Per-user isolation via Supabase RLS** (see
  [supabase/CLAUDE.md](supabase/CLAUDE.md)): clients see only their own
  bookings, owners manage only their own providers/resources. Every user-owned
  read/write goes through a JWT-scoped Supabase client so RLS applies live; the
  service key is kept for system/cross-user work.
- Auth is a cross-cutting layer on top of the engine — it does **not** change
  the pivot design. `domain.config.json` still owns vocabulary/defaults; no
  domain term or magic number moves into auth code.

Each subdir's `CLAUDE.md` records what's actually implemented; `REPORT.md` is
the current verified snapshot.

## Repo layout

| Path | Owns | Detail |
|------|------|--------|
| `backend/` | FastAPI engine: config + per-service rules, camelCase serialization, `/providers` `/services` `/resources` `/slots` `/availability` `/bookings` `/me` `/demo` routers, auth, three-vertical seeding | [backend/CLAUDE.md](backend/CLAUDE.md) |
| `frontend/` | Next.js app (`frontend/src/`): login + gated `(app)` group (search / calendar / bookings / provider / account), real HTTP API seam | [frontend/CLAUDE.md](frontend/CLAUDE.md) |
| `supabase/` | `schema.sql` — neutral base tables + extended entities (providers/services/booking_slots/reviews/follows), occupancy view, RLS | [supabase/CLAUDE.md](supabase/CLAUDE.md) |
| `test/` | Stack + API tests (owned exclusively by the `test-writer` agent, see below) | [test/CLAUDE.md](test/CLAUDE.md) |
| `domain.config.json` | The pivot file (v2) | [docs/PIVOT-SYSTEM.md](docs/PIVOT-SYSTEM.md) |
| `scripts/check_pivots.py` | 50 pivots run through the real validator + pricing engine | [docs/PIVOT-COVERAGE.md](docs/PIVOT-COVERAGE.md) |

`backend/`, `frontend/`, and `supabase/` are built out **independently** —
each has its own `CLAUDE.md` with the requirements and conventions for that
piece. Read this file first, then the relevant subdirectory's file, before
working in it.

## Development workflow — the 3-agent verification pipeline

To check the state of the codebase (what's built, whether it works, what's
left) without doing that analysis by hand every time, use the three custom
agents in `.claude/agents/`, run in this order:

1. **`codebase-analyst`** (read-only, full repo) — reads the root and every
   nested `CLAUDE.md` plus the actual code, and reports back a structured
   understanding: architecture, config flow, implemented endpoints/routes,
   schema shape, and gaps vs. the README checklist. It never edits anything.
2. **`test-writer`** (reads anywhere, writes only inside `test/`) — takes the
   analyst's findings and authors test plans/automated tests for the stack
   and the API endpoints under `test/`. It must never create or modify files
   outside `test/`.
3. **`test-runner`** (execute-only — no `Write`/`Edit`/`NotebookEdit`) — runs
   whatever `test-writer` produced (`pytest`, `npm test`, etc.) and reports
   pass/fail results. It cannot modify any file, including its own results.

The orchestrating session runs these three in sequence (each depends on the
previous one's output) and then writes two files at repo root from the
combined results:

- **`REPORT.md`** — what exists and how it's implemented (from the analyst +
  test results).
- **`TODO.md`** — what's missing or broken and what to do next, prioritized.

Re-run the pipeline whenever you want a fresh read on the codebase state —
`REPORT.md`/`TODO.md` are snapshots, not living docs, so regenerate rather
than hand-edit them.

## Per-issue documentation

When a Claude Code session finishes work on a GitHub issue, it writes a short
summary to `docs/issues/<issue#>-<slug>.md` (matching the branch name,
`<issue#>-<slug>`) covering what changed and why, and also posts the same
summary in chat, formatted to paste as a GitHub issue comment before opening
the PR. This keeps a durable trail per issue, independent of the `REPORT.md`/
`TODO.md` whole-repo snapshots above.

## Commands

```bash
cp backend/.env.example backend/.env   # SUPABASE_URL + SERVICE_KEY + ANON_KEY + JWT_SECRET (+ DB_URL)
make start                             # frontend :3000, backend :8000
make reload                            # re-read domain.config.json after an edit
make reseed                            # wipe + reseed demo data to match current config
make logs / make stop / make reset     # see `make` with no args for the full list
```
