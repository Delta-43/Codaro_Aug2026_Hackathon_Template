# Contributing

Everything reaches production the same way. No exceptions, no direct pushes.

```
issue  →  branch  →  PR into develop (staging)  →  PR develop into main (production)
```

`main` is what is deployed. `develop` is where finished work accumulates until
we decide to release. You never commit to either of them directly.

---

## 1. Open an issue

Before writing code, open an issue describing what you are doing
([new issue](../../issues/new/choose)). This is not paperwork — the issue
number is how your branch, your PR, and the review all stay tied together.

Note the number GitHub gives it, e.g. **#42**.

## 2. Branch from `develop`

Always branch from an up-to-date `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feat/42-close-a-slot
```

Name the branch `<type>/<issue-number>-<short-description>`:

| Prefix | Use for |
|---|---|
| `feat/` | new functionality |
| `fix/` | a bug fix |
| `chore/` | tooling, CI, dependencies |
| `docs/` | documentation only |
| `refactor/` | restructuring with no behavior change |
| `test/` | tests only |
| `hotfix/` | an emergency fix that must skip staging (see below) |

## 3. Do the work

Read the `CLAUDE.md` in whichever directory you are touching first — each of
`backend/`, `frontend/`, `supabase/`, and `test/` has its own conventions.

Two rules the reviewer will check every time, because they are the point of
this codebase:

- **No hard-coded domain words.** Say `resource`, never `room` or `doctor`.
  Every user-visible label renders through `<Term>`, which reads `terms` from
  `domain.config.json`.
- **No magic numbers.** A cancellation window, a slot length, a capacity cap —
  all of it lives in `rules` in `domain.config.json` and is read at runtime.

New domain-specific data goes in a table's `metadata jsonb` column.
`supabase/schema.sql` is frozen — changing it invalidates everyone else's
database, so it needs discussion in the issue first.

## 4. Run the tests before you push

```bash
python -m pytest test -q                             # backend (e2e auto-skips)
python .github/scripts/validate_domain_config.py     # the pivot file
cd frontend && npm ci && npx tsc --noEmit && npm run build
```

CI runs exactly these. Running them locally saves you a round trip.

## 5. Open a pull request into `develop`

```bash
git push -u origin feat/42-close-a-slot
```

GitHub will offer to open a PR. **Set the base branch to `develop`**, not
`main` — GitHub defaults to `main` and CI will reject it.

Fill in the template, and make sure the first line reads `Closes #42`. That
keyword auto-closes the issue on merge, and CI fails the PR if no issue is
referenced.

Then: get a review, get CI green, merge. Use **Squash and merge** so `develop`
keeps one commit per issue.

## 6. Releasing: `develop` → `main`

When staging is in a state worth shipping, open a PR from `develop` into
`main`. This is the only PR allowed to target `main`. Title it with the
release scope, e.g. `release: booking cancellation + occupancy view`.

Use **Merge commit** (not squash) for this one, so `main` keeps the individual
commits from `develop` and the two branches share history.

## Hotfixes

Only when production is broken and waiting for the next release is not an
option:

```bash
git checkout main && git pull origin main
git checkout -b hotfix/57-booking-500
```

PR it into `main`. Then immediately merge `main` back down so staging does not
lose the fix:

```bash
git checkout develop && git pull origin develop
git merge main && git push origin develop
```

(Merge locally — do not open a `main` → `develop` PR. CI blocks that, because
it produces a merge that is painful to untangle later.)

---

## What CI checks

Every PR into `develop` or `main` runs two workflows:

**`CI`** ([.github/workflows/ci.yml](.github/workflows/ci.yml)) — three parallel jobs:

| Job | What it does |
|---|---|
| `domain.config.json is valid` | Every key the engine reads exists and has a sane value |
| `Backend tests (pytest)` | `test/backend` against a fake in-memory Supabase — no credentials, no network. `test/e2e` is collected but skipped (it needs a running stack; set `E2E_BASE_URL` to run it locally) |
| `Frontend typecheck + build` | `npm ci`, `tsc --noEmit`, `next build` |

**`Branch policy`** ([.github/workflows/branch-policy.yml](.github/workflows/branch-policy.yml)) —
confirms the PR targets the right branch and references an issue. If it fails,
read the message in the job summary: it tells you exactly what to retarget.

## Recommended repo settings

These are set once by a maintainer under **Settings → Branches**, and are what
actually make the flow non-optional. Add a protection rule for both `main` and
`develop`:

- Require a pull request before merging (1 approval)
- Require status checks to pass: `Backend tests (pytest)`,
  `Frontend typecheck + build`, `domain.config.json is valid`,
  `PR targets the right branch`
- Require branches to be up to date before merging
- Block force pushes and deletions

Without these rules the workflows still report failures, but nothing stops
someone from merging anyway.
