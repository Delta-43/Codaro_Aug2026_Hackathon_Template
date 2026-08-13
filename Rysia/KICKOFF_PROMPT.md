# Kickoff Prompt — paste this to any AI coding agent to start/continue the project

Copy the block below verbatim as your first message in a new AI session (Claude Code, Cursor, Cowork, whatever your team is using). Fill in the blanks first. Every teammate should use this exact pattern so any AI session — theirs or a fresh one — starts from the same shared understanding.

---

```
Before doing anything, read AGENTS.md in this repo in full — it is our shared
project memory (scope, stack, business rules, architecture principles, and
progress log). Follow it. After you finish this task, append a short dated
entry to the Decisions & Progress Log section describing what you did and why
— a few lines, not a report.

TASK: <one specific, scoped thing — e.g. "Create the Supabase schema for
resources, slots, and bookings, with constraints enforcing max bookings per
slot and buffer time between slots">

CONSTRAINTS (non-negotiable, per AGENTS.md §5):
- Keep functions and components short and single-purpose. Split anything
  that does more than one thing.
- Business rules (cancellation window, capacity, buffer time) go in an
  isolated rules module as named pure functions — never inline in routes
  or components.
- Anything about naming, labels, copy, or theme/branding must come from the
  config file, not be hardcoded. This app must be re-themeable in ~2 hours
  during a mid-hackathon pivot.
- No speculative abstractions or frameworks-within-the-framework. Simple and
  readable beats clever.
- Stack: Next.js 14 (App Router) + Tailwind + shadcn/ui + react-big-calendar
  on frontend; Python FastAPI on backend; Supabase (Postgres) for data.

ACCEPTANCE CRITERIA: <how you'll know this specific task is done — be
concrete, e.g. "schema.sql runs cleanly against a fresh Supabase project;
inserting a booking that exceeds slot capacity fails with a clear error">

Ask me before making decisions that aren't covered by AGENTS.md (e.g. new
dependencies, schema changes affecting multiple features).
```

---

### Notes on using this well

- **One task per prompt.** Don't paste this once and ask for "the whole app." Reuse this template for each feature/endpoint/component — resources CRUD, slot generation, booking + confirmation, cancellation logic, availability calendar view, etc. Small, reviewable chunks are what makes the pivot survivable later.
- **Always name a concrete acceptance criterion.** "It should work" isn't checkable; "creating a booking for a full slot returns a 409" is.
- **When the pivot lands mid-hackathon**, the first message in your next AI session should be: *"Read AGENTS.md, especially §8 Pivot Playbook. Here is the new pivot brief: <paste it>. Update the log first, then propose the minimal set of changes to config/labels/rules needed — don't rewrite booking logic unless truly necessary."*
- **Keep AGENTS.md as the single source of truth.** If you and a teammate are in different AI sessions at the same time, whoever finishes first updates the log before the other starts their next task, so no one works from stale context.
