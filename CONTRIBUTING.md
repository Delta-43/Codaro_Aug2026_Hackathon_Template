# Contributing

One flow for everything. No direct pushes to `develop` or `main`.

```
issue  →  branch  →  PR into develop  →  PR develop into main (release)
```

## 1. Open an issue

There is a single issue form ([new issue](../../issues/new/choose)) — use it
for features, bugs, everything. Note the number GitHub gives it, e.g. **#42**.

## 2. Branch from `develop`

```bash
git checkout develop && git pull origin develop
git checkout -b 42-close-a-slot
```

Name the branch `<issue-number>-<short-description>`.

Two rules the reviewer checks every time:

- **No hard-coded domain words.** Say `resource`, never `room` or `doctor` —
  labels render through `<Term>` from `domain.config.json`.
- **No magic numbers.** Business values live in `rules` in `domain.config.json`.

`supabase/schema.sql` is frozen; new domain data goes in `metadata jsonb`.

## 3. Test, then open a PR into `develop`

```bash
python -m pytest test -q
python .github/scripts/validate_domain_config.py
cd frontend && npm ci && npx tsc --noEmit && npm run build
```

CI runs exactly these. Push your branch, open a PR, and **set the base branch
to `develop`** (GitHub defaults to `main`). Start the description with
`Closes #42`. Get one approval and green CI, then **Squash and merge**.

## 4. Releasing

When `develop` is worth shipping, open a PR from `develop` into `main` — the
only PR allowed to target `main` — and use **Merge commit** (not squash).

If production is broken and can't wait, branch `hotfix/<issue>-...` from
`main`, PR it into `main`, then merge `main` back into `develop` locally.
