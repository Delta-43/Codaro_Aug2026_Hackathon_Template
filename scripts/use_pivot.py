#!/usr/bin/env python3
"""Swap `domain.config.json` for one of the pivots in `pivots/`.

    python3 scripts/use_pivot.py 3          # by number
    python3 scripts/use_pivot.py escape     # by name substring
    python3 scripts/use_pivot.py --list
    python3 scripts/use_pivot.py --restore  # put the previous config back

The file is re-validated before it is copied, and the config it replaces is kept
at `domain.config.json.bak`, so a pivot can be tried and undone without git.
Afterwards: `make reload` (drop the backend's cached config), `make reseed`
(rebuild demo data to match).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config_schema import normalize, validate  # noqa: E402
from seed_data import VERTICALS  # noqa: E402

# Every public code any vertical seeds. A single-tenant config naming a code
# outside this set validates fine and then resolves no business at runtime —
# the owner dashboard shows "No business yet" and the customer view is empty —
# so it is worth saying out loud at swap time rather than leaving it to be
# diagnosed from an empty screen.
SEEDED_CODES = {
    p["publicCode"] for v in VERTICALS.values() for p in v["providers"]
}

PIVOTS = REPO_ROOT / "pivots"
TARGET = REPO_ROOT / "domain.config.json"
BACKUP = REPO_ROOT / "domain.config.json.bak"


def manifest() -> list[dict]:
    path = PIVOTS / "manifest.json"
    if not path.exists():
        raise SystemExit("pivots/manifest.json is missing — run: python3 scripts/generate_pivots.py")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(query: str, rows: list[dict]) -> dict:
    if query.isdigit():
        matches = [r for r in rows if r["n"] == int(query)]
    else:
        needle = query.lower()
        matches = [r for r in rows if needle in r["name"].lower() or needle in r["file"]]
    if not matches:
        raise SystemExit(f"no pivot matches {query!r} — try: python3 scripts/use_pivot.py --list")
    if len(matches) > 1:
        listing = "\n  ".join(f"{r['n']:3d}  {r['name']}" for r in matches)
        raise SystemExit(f"{query!r} matches {len(matches)} pivots:\n  {listing}")
    return matches[0]


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if args[0] == "--list":
        for r in manifest():
            print(f"{r['n']:3d}  {r['tenancy']:<6}  {r['name']:<34}  {r['booked']}")
        return 0

    if args[0] == "--restore":
        if not BACKUP.exists():
            raise SystemExit("no domain.config.json.bak to restore from")
        shutil.copyfile(BACKUP, TARGET)
        print(f"restored {TARGET.name} from {BACKUP.name} — run `make reload`")
        return 0

    row = resolve(args[0], manifest())
    source = PIVOTS / row["file"]
    cfg = json.loads(source.read_text(encoding="utf-8"))
    errors = validate(normalize(cfg))
    if errors:
        raise SystemExit(f"{source.name} does not validate:\n  " + "\n  ".join(errors))

    if TARGET.exists():
        shutil.copyfile(TARGET, BACKUP)
    shutil.copyfile(source, TARGET)

    print(f"#{row['n']} {row['name']} -> {TARGET.name}  ({row['tenancy']}, "
          f"{row['unitKind']}, {row['pricingModel']}, {row['currency']})")
    code = cfg["tenancy"].get("providerCode")
    if cfg["tenancy"]["mode"] == "single" and code not in SEEDED_CODES:
        print(f"  WARNING: tenancy.providerCode {code!r} is not seeded by any vertical.")
        print("           Single mode resolves the business via /providers/by-code;"
              " an unknown code")
        print('           renders "No business yet" and an empty customer view.')
    if row.get("limitation"):
        print(f"  known schema gap: {row['limitation'].splitlines()[0].strip()}")
    if row.get("blocked"):
        print(f"  blocked on: {row['blocked']}")
    print(f"  previous config saved to {BACKUP.name} (undo: --restore)")
    print("  next: make reload && make reseed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
