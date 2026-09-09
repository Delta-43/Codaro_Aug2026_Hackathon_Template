# Verifying changes, the local CI recipe

These are the checks `.github/workflows/ci.yml` runs. Run the ones that touch
what you changed, or all of them before opening a PR.

CI has five jobs and more gates than the four sections below spell out in
detail. The full list, any one of which fails the build:

| Gate | Command |
|---|---|
| Config valid | `python3 .github/scripts/validate_domain_config.py` |
| Schema current | `python3 scripts/gen_config_schema.py --check` |
| Lint (Python) | `ruff check .` |
| Backend tests | `python -m pytest test -q` |
| Config types current | `cd frontend && npm run codegen:config` then `git diff --exit-code src/api/config.generated.ts` |
| Lint (JS) | `cd frontend && npm run lint` |
| Typecheck | `cd frontend && npm run typecheck` |
| Build | `cd frontend && npm run build` |
| Unused code | `cd frontend && npx knip` |
| Dependency audit | `pip-audit`, `npm audit` |
| Images build | `docker build` for both Dockerfiles |

The two easiest to forget are the schema/codegen pair, because they fail only
when a *generated* file drifts from its source, and `knip`.

**Run the lint over the whole repository, not just the directory you edited.**
CI runs a bare `ruff check .`, so a stray import left in `test/` fails the build
exactly as one in `backend/` would. The repo also has a `test-runner` agent
(`.claude/agents/`) that executes the same suite and reports pass/fail.

## 1. Pivot config (fast, always cheap)

```bash
python3 .github/scripts/validate_domain_config.py
```

Confirms `domain.config.json` still has every required section/key with the
right types. Run it after **any** edit to `domain.config.json`, a typo there
breaks the backend at startup and every UI label.

## 2. Lint

```bash
ruff check .
```

The whole repository, `test/` included. This is its own CI step and it fails the
build on its own, so a green test run is not enough.

## 3. Backend tests

```bash
# one-time: a venv with backend + test deps
python3 -m venv .venv-test
.venv-test/bin/pip install -r backend/requirements.txt -r test/requirements-test.txt

# run (dummy creds; the suite stubs Supabase, no network, e2e auto-skips)
SUPABASE_URL=http://localhost:54321 SUPABASE_SERVICE_KEY=ci-dummy-key \
  .venv-test/bin/python -m pytest test -q
```

Expected: all `test/backend` pass; `test/e2e` skips unless `SUPABASE_URL` +
`SUPABASE_ANON_KEY` point at a live stack. Run after any `backend/` change.

## 4. Frontend typecheck + build

```bash
cd frontend
npm ci
npm run codegen:config && git diff --exit-code src/api/config.generated.ts
npm run lint
npm run typecheck
npm run build
npx knip
```

Use `npm run typecheck`, not a bare `tsc --noEmit`: the script points at
`tsconfig.typecheck.json`, so a bare run checks a different file set than CI
does. `npm run build` is the closest thing to "would this deploy". Run these
after any `frontend/` change.

> **Footgun:** don't run `npm run build` while a `next dev` server is live on the
> same checkout, it overwrites the dev server's `.next` and the running page
> stops hydrating. Stop the dev server first (or use the Docker preview, whose
> `.next` is an isolated volume).

## Frontend-only changes

A change confined to `frontend/` needs check **4**, all of it, including the
codegen diff and `knip`. Checks 1 to 3 cover the backend and config and are
unaffected. Running everything before a PR is still the safe default, and takes
a couple of minutes.
