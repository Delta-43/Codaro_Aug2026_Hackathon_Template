"""Root test shim.

The backend uses absolute imports (`from app.db import ...`, `from seed
import ...`) that assume `backend/` is the working directory / on
`sys.path`. Rather than requiring contributors to `cd backend` or set
PYTHONPATH by hand, we fix `sys.path` here so `pytest test/backend` works
unchanged from the repo root (or from anywhere else).

This file is loaded by pytest before any test module in `test/`, because
pytest imports every `conftest.py` between the rootdir and the collected
test files.
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

if not (BACKEND_DIR / "app").is_dir():  # pragma: no cover - misconfigured checkout
    raise RuntimeError(
        f"Expected the FastAPI app at {BACKEND_DIR / 'app'}; is the repo layout intact?"
    )

# `backend/` first so `app` / `seed` resolve to the real backend package,
# then the suite's own dirs so `fakes` / `helpers` are importable regardless
# of pytest's import mode or the directory pytest was invoked from.
for path in (BACKEND_DIR, TEST_DIR, TEST_DIR / "backend"):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
