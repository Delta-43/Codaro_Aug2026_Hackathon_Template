# Codaro Booking Engine — root guide

## What this is

A generic booking engine (`resource → slot → booking`) built so a completely
different niche can be adopted via a single config edit instead of a rewrite.
Stack: **Next.js 14 + Tailwind** frontend, **FastAPI** backend, hosted
**Supabase (Postgres)**. See `README.md` for the full run instructions and
`Project_Summary.md` for the original brief.

The pivot mechanism: `domain.config.json` is the single source of truth for
`terms` (vocabulary), `rules` (business rules), `copy`, `theme`, and
`metaFields`. The backend serves it at `GET /config`; the frontend renders
every label through `<Term>` and every number from `rules`. Nothing in code
should hard-code a domain term or a magic number. New domain-specific data
goes in each table's `metadata jsonb` column — no migrations at pivot time.
`supabase/schema.sql` is treated as frozen/idempotent once the event starts.

## Repo layout

| Path | Owns | Detail |
|------|------|--------|
| `backend/` | FastAPI engine: config loading, rules engine, `/resources` `/slots` `/bookings` routers, seeding | [backend/CLAUDE.md](backend/CLAUDE.md) |
| `frontend/` | Next.js UI: landing page, customer + owner dashboards, config-driven rendering | [frontend/CLAUDE.md](frontend/CLAUDE.md) |
| `supabase/` | `schema.sql` — neutral tables + occupancy view | [supabase/CLAUDE.md](supabase/CLAUDE.md) |
| `test/` | Stack + API tests (owned exclusively by the `test-writer` agent, see below) | [test/CLAUDE.md](test/CLAUDE.md) |
| `domain.config.json` | The pivot file | — |

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

## Commands

```bash
cp backend/.env.example backend/.env   # fill SUPABASE_URL + SUPABASE_SERVICE_KEY (+ SUPABASE_DB_URL)
make start                             # frontend :3000, backend :8000
make reload                            # re-read domain.config.json after an edit
make reseed                            # wipe + reseed demo data to match current config
make logs / make stop / make reset     # see `make` with no args for the full list
```
