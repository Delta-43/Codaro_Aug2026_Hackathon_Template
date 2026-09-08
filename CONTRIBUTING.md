# Working on this codebase

> **This repository is not accepting contributions.** Arbor is a finished
> showcase project and pull requests here are not reviewed. See
> [Project status](README.md#project-status).
>
> This document is kept because it is still the map of how the codebase is
> worked on. If you fork Arbor, this is the flow and these are the rules the
> code assumes.

One flow for everything. No direct pushes to `develop` or `main`.

```
issue  →  branch  →  PR into develop  →  PR develop into main (release)
```

## 1. Open an issue

Track the work as an issue in your fork and note its number, e.g. **#42**. The
issue forms under `.github/ISSUE_TEMPLATE/` come with the fork.

## 2. Branch from `develop`

```bash
git checkout develop && git pull origin develop
git checkout -b 42-close-a-slot
```

Name the branch `<issue-number>-<short-description>`.

Two rules the reviewer checks every time:

- **No hard-coded domain words.** Say `resource`, never `room` or `doctor`. In
  the frontend, labels come from the vertical config — `useVertical().resourceNoun`
  (`src/config/verticals.ts`), never a literal. Backend-side copy comes from
  `domain.config.json`'s `terms`/`copy`.
- **No magic numbers.** Business values live in `domain.config.json` — the v2
  blocks (`timing`, `booking`, `pricing`, …), not the deprecated v1 `rules`
  alias. A service row's own columns/`metadata` override the global default via
  `rules.effective_service_rules`, so read the resolved value, never a literal.

`supabase/schema.sql` is frozen; new domain data goes in `metadata jsonb`.

## 3. Test, then open a PR into `develop`

```bash
python -m pytest test -q
python .github/scripts/validate_domain_config.py
cd frontend && npm ci && npx tsc --noEmit && npm run build
```

CI runs exactly these (`.github/workflows/ci.yml`, which comes with the fork).
Push your branch, open a PR, and **set the base branch to `develop`** (GitHub
defaults to `main`). Start the description with `Closes #42`. Get one approval
and green CI, then **Squash and merge**.

## 4. Releasing

When `develop` is worth shipping, open a PR from `develop` into `main` — the
only PR allowed to target `main` — and use **Merge commit** (not squash).

If production is broken and can't wait, branch `hotfix/<issue>-...` from
`main`, PR it into `main`, then merge `main` back into `develop` locally.
