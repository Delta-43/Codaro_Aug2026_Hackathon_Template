#!/usr/bin/env python3
"""Computes the git-derived name for a benchmark run folder
(<commit-date>-<branch>-<short-sha>-<seq>[-dirty]), creates it under the
given results directory, and writes a meta.json inside it recording that
context. <seq> (001, 002, ...) counts prior runs of the same commit, so
re-running the benchmark without committing anything still gets its own
folder instead of colliding with the last run's.

Called once at the very start of run.sh so k6, Playwright, and
generate_report.py all agree on the same folder/commit description for the
whole run — computing git state independently in bash *and* Python (or
re-deriving it after the run) risks the two disagreeing, e.g. if HEAD moves
mid-run.

Usage: python3 run_context.py <results-dir>
Prints the run folder's name (not full path) to stdout, so a caller can do:
    RUN_NAME=$(python3 report/run_context.py results)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True)
        return out.strip() or None
    except Exception:
        return None


def git_context() -> dict:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "no-git"
    if branch == "HEAD":  # detached
        branch = _git("rev-parse", "--short", "HEAD") or "detached"
    short_sha = _git("rev-parse", "--short", "HEAD") or "nogit"
    commit_date = _git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d") or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d"
    )
    dirty = bool(_git("status", "--porcelain"))
    return {"branch": branch, "shortSha": short_sha, "commitDate": commit_date, "dirty": dirty}


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "unknown"


def _next_seq(results_dir: Path, base: str) -> int:
    """Highest existing <base>-NNN[-dirty] folder's NNN, plus one — so
    re-running against the same commit (dirty or not) never collides with a
    prior run's folder."""
    pattern = re.compile(rf"^{re.escape(base)}-(\d{{3}})(?:-dirty)?$")
    highest = 0
    if results_dir.exists():
        for entry in results_dir.iterdir():
            if not entry.is_dir():
                continue
            m = pattern.match(entry.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def run_name(ctx: dict, results_dir: Path) -> str:
    base = f"{ctx['commitDate']}-{sanitize(ctx['branch'])}-{ctx['shortSha']}"
    seq = _next_seq(results_dir, base)
    name = f"{base}-{seq:03d}"
    if ctx["dirty"]:
        name += "-dirty"
    return name


def main() -> None:
    results_dir = Path(sys.argv[1]).resolve()
    ctx = git_context()
    name = run_name(ctx, results_dir)
    run_dir = results_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "meta.json").write_text(json.dumps(ctx))
    print(name)


if __name__ == "__main__":
    main()
