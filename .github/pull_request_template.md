<!--
  Feature branches target `develop`. Only `develop` (or a `hotfix/*` branch)
  targets `main`. CI enforces this — see CONTRIBUTING.md.
-->

Closes #

## What changed

<!-- One or two sentences. What does the reviewer need to know before reading the diff? -->

## How to verify

<!-- The exact commands or click path a reviewer should follow. -->

```bash
make start
```

## Checklist

- [ ] This PR references its issue above (`Closes #<number>`)
- [ ] `python -m pytest test -q` passes locally
- [ ] No hard-coded domain word — vocabulary comes from `terms` via `<Term>`
- [ ] No magic number — business values come from `rules` in `domain.config.json`
- [ ] New domain-specific data went into a `metadata jsonb` column, not a new column
- [ ] `supabase/schema.sql` is unchanged (it is frozen once the event starts)

<!--
  If you did change schema.sql or added a dependency, say so here and explain
  why — those are the two changes most likely to break everyone else's setup.
-->
