# Token budget — rules for every agent/session

Goal: finish the task using as few tokens as possible. Tokens ≈ the user's
5-hour usage limit, so every wasted read/screenshot costs them real budget.
These rules apply to the orchestrating session **and** every subagent.

## The expensive things (in order)

1. **Screenshots / images.** A single full-page screenshot can cost more than
   an entire file read. This is the #1 sink.
2. **Reading whole files** when only a slice is needed.
3. **Redundant tool round-trips** — re-reading a file you just edited,
   re-verifying something already confirmed, polling.
4. **Long prose** — verbose explanations, recaps, restating the plan.

## Rules

- **Screenshots: last resort, at most one.** Verify with text first
  (`read_page`, `get_page_text`, `read_console_messages`, `preview_logs`).
  Take a screenshot *only* when the change is visual **and** the user needs to
  see it — never to check your own work when text tools would do. Never take
  the same shot twice.
- **Read narrow.** Use `grep`/`rg` to locate, `sed -n 'A,Bp'` to read a range.
  Reach for a full-file read only when you genuinely need the whole file.
- **Don't re-read after editing.** Edit/Write already confirm success; trust it.
- **Batch independent calls** into one turn.
- **Verify once.** If `tsc` + one targeted check passes, stop. Don't re-run the
  same verification across breakpoints/modes unless the change specifically
  affects them.
- **Skip verification that proves nothing** (see `docs/verifying-changes.md`):
  don't spin up a preview for non-visual changes (docs, types, config).
- **Be terse.** Short answers, short commit messages, no recaps of what you
  just did or of the plan. Report the outcome and stop.
- **Don't spawn subagents** unless the user asks — each one starts cold and
  re-derives context, which is expensive.

## Quick reference

| Need | Cheap way | Avoid |
|------|-----------|-------|
| Find code | `grep -rn` | reading files to search |
| Read part of a file | `sed -n '40,80p'` | `cat` whole file |
| Confirm an edit landed | trust Edit's result | re-reading the file |
| Check a UI change | `read_page` / `get_page_text` | screenshot |
| Show the user a visual result | **one** screenshot | several |
