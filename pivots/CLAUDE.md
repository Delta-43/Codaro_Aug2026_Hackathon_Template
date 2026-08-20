# Pivot library

100 complete, validated `domain.config.json` files — one per business the engine
was designed to become. See [index.md](index.md) for the full table.

## Why they exist

`docs/PIVOT-SYSTEM.md` argues that a pivot is a config edit, not a rewrite, and
`docs/PIVOT-COVERAGE.md` proves it by running 100 businesses through the real
validator and pricing engine. But those 100 live in the harness as *fragments* —
only the keys each business changes. That is right for evidence and wrong for
use: you cannot drop a fragment into the repo and start the app.

This folder is the same 100 businesses as whole files. Each one boots.

## Using one

```bash
python3 scripts/use_pivot.py 3          # by number
python3 scripts/use_pivot.py escape     # by name substring
python3 scripts/use_pivot.py --list
python3 scripts/use_pivot.py --restore  # put the previous config back
```

`use_pivot.py` validates the file, backs up the current `domain.config.json` to
`domain.config.json.bak`, and copies the pivot into place. Then:

```bash
make reload    # drop the backend's cached config
make reseed    # rebuild the demo data
make checkseed # report where that data and the new config disagree
```

`make reseed` rebuilds the demo data **from the config** (via
`backend/seed_config.py`): currency, timezone, durations, prices, cutoffs, slot
capacity and the single-tenant provider code all come from the file you just
loaded, `pricing.tiers` become the catalogue, and `terms` supply the nouns.
`make checkseed` verifies it and names anything that still disagrees.

## How they are generated

`scripts/generate_pivots.py` merges each fragment over the tenancy base, runs the
engine's own `normalize()` (materialising every default, so the file is explicit
rather than relying on fill-in) and `validate()`, and writes the result. A pivot
that fails validation aborts the run — these files cannot drift from the schema.

Three things are **derived**, not taken from the fragment, because the fragments
never carried them:

- `domain` — a slug of the business name.
- `terms` — the resource/slot/booking nouns and the business/offering nouns,
  from `booking.unitKind`; the party noun from `booking.party.mode`; the subject
  noun from `booking.subject`. The seeder builds provider and service names out
  of these, so they are what makes reseeded demo data read as the right niche.
- `copy` — landing title/subtitle and the two empty states, from the name and the
  one-line description in the harness.

One value is **substituted**: single-tenant pivots get `tenancy.providerCode`
from the seed (`seed_data.VERTICALS[DEFAULT_VERTICAL].providers[0].publicCode`)
instead of the harness's `"DEMO-0001"` placeholder. Single mode resolves *the*
business through `GET /providers/by-code/{code}`; a code no seed ever wrote 404s,
and the app then shows "No business yet" on the owner dashboard and an empty
customer view. Reseed after switching (`make reseed`) so the code still resolves.

The rest are the label layer; none of them changes engine behaviour. Everything
that does — `capabilities`, `booking`, `pricing`, `payments`, `inventory`,
`location`, `prerequisites`, `timing`, `recurrence`, `entitlements`, `discovery`,
`tenancy` — comes from the pivot definition unchanged.

## What these files do and do not prove

They prove the schema can **express** each business: every file here validates
against the same `app/config_schema.validate()` the backend boots on.

They do not prove the engine **enforces** every key in them. Enforcement is
narrower than the schema on purpose — `docs/PIVOT-SYSTEM.md` §6 lists what is
wired end to end, and the `blocked` / `limitation` columns in
[index.md](index.md) name, per business, what is still missing. A file marked
"schema gap" validates and quotes, but quotes the wrong model; the gap is
documented in `docs/PIVOT-COVERAGE.md`.

Regenerate after editing a pivot definition or adding a config key:

```bash
python3 scripts/generate_pivots.py
python3 scripts/generate_pivots.py --check   # CI-friendly: fails if stale
```
