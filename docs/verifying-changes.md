# Verifying changes, the local CI recipe

These checks mirror `.github/workflows/ci.yml`. Run the ones that touch what you
changed, or all of them before opening a PR. Passing them locally means the PR's
CI will pass too.

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
npx tsc --noEmit
npm run build
```

`tsc` catches type errors fast; `npm run build` is the closest thing to "would
this deploy" (it also lints and prerenders). Run after any `frontend/` change.

> **Footgun:** don't run `npm run build` while a `next dev` server is live on the
> same checkout, it overwrites the dev server's `.next` and the running page
> stops hydrating. Stop the dev server first (or use the Docker preview, whose
> `.next` is an isolated volume).

## Frontend-only changes

A change confined to `frontend/` (e.g. the landing page) only needs check **3**.
Checks 1–2 cover the backend/config and are unaffected, but running all three
before a PR is the safe default.
