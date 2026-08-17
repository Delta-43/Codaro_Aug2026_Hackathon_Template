#!/usr/bin/env python3
"""Turns one run's raw k6 + Playwright output into a static HTML report with
graphs (Chart.js via CDN — this file is opened locally in a normal browser,
not published anywhere, so a CDN script tag is fine).

Each run lives in its own folder, named by `run_context.py` for what was
actually running (`results/<commit-date>-<branch>-<short-sha>[-dirty]/`), so
reports from different commits/branches sit side by side instead of
overwriting each other — open two report files and compare.

Reads (inside the run folder):
  k6-events.jsonl        (k6 --out json=... NDJSON stream)
  playwright-results.json
  meta.json              (git context written by run_context.py)

Writes, inside that same run folder, named by which raw files are present —
so a `make benchmark-k6` folder (k6-events.jsonl only) never collides with a
`make benchmark-playwright` folder's (playwright-results.json only) report,
and a combined `make benchmark` folder (both files) gets its own name too:
  combined.html           both raw files present
  k6.html                 k6-events.jsonl only
  playwright.html         playwright-results.json only

Usage:
  python3 generate_report.py [path/to/results/<run-folder>]
  # with no argument, regenerates the most recently modified run folder
  # under results/ — reprocess without re-running the benchmarks
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmark" / "results"

ENDPOINT_ORDER = [
    "config",
    "providers_search",
    "services_list",
    "resources_list",
    "availability",
    "slots_list",
    "me",
    "bookings_list",
    "booking_create",
    "booking_cancel",
]
ENDPOINT_LABELS = {
    "config": "GET /config",
    "providers_search": "GET /providers",
    "services_list": "GET /services",
    "resources_list": "GET /resources",
    "availability": "GET /availability",
    "slots_list": "GET /slots",
    "me": "GET /me",
    "bookings_list": "GET /bookings",
    "booking_create": "POST /bookings",
    "booking_cancel": "POST /bookings/{id}/cancel",
}

DEVICE_ORDER = ["Desktop", "Mobile - iPhone 13", "Mobile - Pixel 5"]
NETWORK_ORDER = ["No throttle", "4G", "Slow 3G"]
PAGE_ORDER = ["Login (signed out)", "Search", "Calendar", "Bookings", "Account"]

# Reference categorical palette (dataviz skill), fixed slot order — never cycled.
CATEGORICAL = [
    {"light": "#2a78d6", "dark": "#3987e5"},  # 1 blue
    {"light": "#eb6834", "dark": "#d95926"},  # 2 orange
    {"light": "#1baf7a", "dark": "#199e70"},  # 3 aqua
    {"light": "#eda100", "dark": "#c98500"},  # 4 yellow
    {"light": "#e87ba4", "dark": "#d55181"},  # 5 magenta
    {"light": "#008300", "dark": "#008300"},  # 6 green
]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True)
        return out.strip() or None
    except Exception:
        return None


def git_context_fallback() -> dict:
    """Only used if a run folder is missing meta.json (e.g. someone dropped
    raw files in by hand) — the normal path reads meta.json instead of
    recomputing this, since the report must describe the commit the data was
    actually collected under, not whatever HEAD happens to be right now."""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "no-git"
    if branch == "HEAD":  # detached
        branch = _git("rev-parse", "--short", "HEAD") or "detached"
    short_sha = _git("rev-parse", "--short", "HEAD") or "nogit"
    commit_date = _git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d")
    dirty = bool(_git("status", "--porcelain"))
    return {"branch": branch, "shortSha": short_sha, "commitDate": commit_date, "dirty": dirty}


def find_latest_run_dir() -> Path | None:
    candidates = [p for p in RESULTS_DIR.iterdir() if p.is_dir() and (p / "meta.json").exists()] if RESULTS_DIR.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def load_k6(run_dir: Path) -> dict | None:
    k6_events_path = run_dir / "k6-events.jsonl"
    if not k6_events_path.exists():
        print(f"(no k6 results at {k6_events_path}, skipping backend section)")
        return None

    durations: dict[str, list[float]] = {}
    all_times: list[float] = []
    with k6_events_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") != "Point" or event.get("metric") != "http_req_duration":
                continue
            tags = event["data"].get("tags", {})
            name = tags.get("name")
            if not name or name in ("setup", "teardown"):
                continue
            durations.setdefault(name, []).append(event["data"]["value"])
            all_times.append(event["data"]["time"])

    if not durations:
        return None

    # Rough wall-clock window covered by the run, for a shared throughput denominator.
    from datetime import datetime

    parsed_times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in all_times]
    window_seconds = max((max(parsed_times) - min(parsed_times)).total_seconds(), 1.0)

    endpoints = [e for e in ENDPOINT_ORDER if e in durations] + [
        e for e in durations if e not in ENDPOINT_ORDER
    ]
    stats = []
    for name in endpoints:
        values = durations[name]
        stats.append(
            {
                "name": name,
                "label": ENDPOINT_LABELS.get(name, name),
                "count": len(values),
                "p50": round(percentile(values, 50), 1),
                "p95": round(percentile(values, 95), 1),
                "max": round(max(values), 1),
                "avg": round(statistics.mean(values), 1),
                "throughput": round(len(values) / window_seconds, 2),
            }
        )
    return {"stats": stats, "windowSeconds": round(window_seconds, 1)}


def load_playwright(run_dir: Path) -> dict | None:
    playwright_results_path = run_dir / "playwright-results.json"
    if not playwright_results_path.exists():
        print(f"(no Playwright results at {playwright_results_path}, skipping frontend section)")
        return None

    rows = json.loads(playwright_results_path.read_text())
    ok_rows = [r for r in rows if not r.get("error") and r.get("loadMs") is not None]
    failed_rows = [r for r in rows if r.get("error")]

    pages = [p for p in PAGE_ORDER if any(r["page"] == p for r in ok_rows)]
    devices = [d for d in DEVICE_ORDER if any(r["device"] == d for r in ok_rows)]
    networks = [n for n in NETWORK_ORDER if any(r["network"] == n for r in ok_rows)]

    # matrix[page][network][device] = avg loadMs (averaged in case of re-runs)
    matrix: dict[str, dict[str, dict[str, float]]] = {}
    for page in pages:
        matrix[page] = {}
        for network in networks:
            matrix[page][network] = {}
            for device in devices:
                vals = [
                    r["loadMs"]
                    for r in ok_rows
                    if r["page"] == page and r["network"] == network and r["device"] == device
                ]
                if vals:
                    matrix[page][network][device] = round(statistics.mean(vals), 1)

    # Overview: average load time per network/device across all pages.
    overview: dict[str, dict[str, float]] = {}
    for network in networks:
        overview[network] = {}
        for device in devices:
            vals = [
                r["loadMs"]
                for r in ok_rows
                if r["network"] == network and r["device"] == device
            ]
            if vals:
                overview[network][device] = round(statistics.mean(vals), 1)

    return {
        "pages": pages,
        "devices": devices,
        "networks": networks,
        "matrix": matrix,
        "overview": overview,
        "rawRows": ok_rows,
        "failedRows": failed_rows,
    }


def render_html(k6_data: dict | None, pw_data: dict | None, git_ctx: dict) -> str:
    from datetime import datetime, timezone

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_label = f"{git_ctx['branch']} @ {git_ctx['shortSha']}"
    if git_ctx["commitDate"]:
        commit_label += f" ({git_ctx['commitDate']})"
    if git_ctx["dirty"]:
        commit_label += " — uncommitted changes"

    backend_json = json.dumps(k6_data)
    frontend_json = json.dumps(pw_data)
    categorical_json = json.dumps(CATEGORICAL)

    backend_section = "" if k6_data is None else """
    <section class="card">
      <h2>Backend API load test</h2>
      <p class="muted">k6 ran two scenarios against the live backend: <code>api_browse</code>, ramping
        virtual users against the search/browse read path (config &rarr; providers &rarr; services &rarr;
        resources &rarr; availability &rarr; slots, plus the authenticated <code>/me</code> and
        <code>/bookings</code> reads a signed-in session also makes), and <code>booking_write</code>, a
        low-VU create&rarr;cancel loop against real seeded slots.</p>
      <div class="chart-wrap"><canvas id="latencyChart" role="img" aria-label="Latency percentiles per endpoint"></canvas></div>
      <div class="chart-wrap"><canvas id="throughputChart" role="img" aria-label="Throughput per endpoint"></canvas></div>
      <h3>Raw numbers</h3>
      <div class="table-wrap"><table id="backendTable"></table></div>
    </section>
    """

    frontend_section = "" if pw_data is None else """
    <section class="card">
      <h2>Frontend device &times; network matrix</h2>
      <p class="muted">Full page load time (ms), Playwright + Chrome DevTools network throttling,
        against the running Next.js dev server.</p>
      <h3>Overview &mdash; average load time across all pages</h3>
      <div class="chart-wrap"><canvas id="overviewChart" role="img" aria-label="Average load time by device and network"></canvas></div>
      <h3>Per-page breakdown</h3>
      <div id="pageCharts"></div>
      <h3>Raw numbers</h3>
      <div class="table-wrap"><table id="frontendTable"></table></div>
    </section>
    """

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Codaro Booking Engine &mdash; Performance Benchmark</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {{
    color-scheme: light;
    --page-plane:     #f9f9f7;
    --surface-1:      #fcfcfb;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --gridline:       #e1e0d9;
    --baseline:       #c3c2b7;
    --border:         rgba(11,11,11,0.10);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --page-plane:     #0d0d0d;
      --surface-1:      #1a1a19;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --gridline:       #2c2c2a;
      --baseline:       #383835;
      --border:         rgba(255,255,255,0.10);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--page-plane);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: 2rem 1.25rem 4rem;
  }}
  .page {{ max-width: 980px; margin: 0 auto; }}
  header {{ margin-bottom: 1.5rem; }}
  header h1 {{ font-size: 1.5rem; margin: 0 0 0.25rem; }}
  header p {{ margin: 0; color: var(--text-secondary); font-size: 0.9rem; }}
  .card {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .card h2 {{ margin-top: 0; font-size: 1.15rem; }}
  .card h3 {{ font-size: 0.95rem; color: var(--text-secondary); margin: 1.75rem 0 0.75rem; }}
  .muted {{ color: var(--text-secondary); font-size: 0.85rem; }}
  .chart-wrap {{ position: relative; height: 320px; margin: 1rem 0; }}
  .page-chart-wrap {{ position: relative; height: 260px; margin: 1rem 0 2rem; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
  th, td {{ text-align: left; padding: 0.45rem 0.75rem; border-bottom: 1px solid var(--gridline); white-space: nowrap; }}
  th {{ color: var(--text-secondary); font-weight: 600; }}
  .empty {{ color: var(--text-muted); font-style: italic; }}
</style>
</head>
<body>
  <div class="page">
    <header>
      <h1>Codaro Booking Engine &mdash; Performance Benchmark</h1>
      <p>{commit_label}</p>
      <p>Generated {generated_at}</p>
    </header>
    {backend_section}
    {frontend_section}
  </div>

<script>
const BACKEND = {backend_json};
const FRONTEND = {frontend_json};
const CATEGORICAL = {categorical_json};

const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => location.reload());

function seriesColor(i) {{ return isDark ? CATEGORICAL[i % CATEGORICAL.length].dark : CATEGORICAL[i % CATEGORICAL.length].light; }}

const ink = getComputedStyle(document.documentElement).getPropertyValue("--text-secondary").trim();
const grid = getComputedStyle(document.documentElement).getPropertyValue("--gridline").trim();

Chart.defaults.color = ink;
Chart.defaults.borderColor = grid;
Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";

function baseOptions(yTitle) {{
  return {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: "index", intersect: false }},
    plugins: {{ legend: {{ position: "top" }}, tooltip: {{ enabled: true }} }},
    scales: {{
      x: {{ grid: {{ display: false }} }},
      y: {{ title: {{ display: true, text: yTitle }}, beginAtZero: true, grid: {{ color: grid }} }},
    }},
  }};
}}

function renderTable(el, columns, rows) {{
  if (!rows.length) {{ el.innerHTML = '<p class="empty">No data.</p>'; return; }}
  const thead = "<thead><tr>" + columns.map(c => `<th>${{c.label}}</th>`).join("") + "</tr></thead>";
  const tbody = "<tbody>" + rows.map(r => "<tr>" + columns.map(c => `<td>${{r[c.key] ?? "&ndash;"}}</td>`).join("") + "</tr>").join("") + "</tbody>";
  el.innerHTML = thead + tbody;
}}

if (BACKEND) {{
  const labels = BACKEND.stats.map(s => s.label);

  new Chart(document.getElementById("latencyChart"), {{
    type: "bar",
    data: {{
      labels,
      datasets: [
        {{ label: "p50 (ms)", data: BACKEND.stats.map(s => s.p50), backgroundColor: seriesColor(0) }},
        {{ label: "p95 (ms)", data: BACKEND.stats.map(s => s.p95), backgroundColor: seriesColor(1) }},
        {{ label: "max (ms)", data: BACKEND.stats.map(s => s.max), backgroundColor: seriesColor(2) }},
      ],
    }},
    options: {{
      ...baseOptions("Response time (ms)"),
      plugins: {{ legend: {{ position: "top" }}, tooltip: {{ enabled: true }}, title: {{ display: true, text: "Latency percentiles per endpoint" }} }},
    }},
  }});

  new Chart(document.getElementById("throughputChart"), {{
    type: "bar",
    data: {{
      labels,
      datasets: [{{ label: "Requests / sec", data: BACKEND.stats.map(s => s.throughput), backgroundColor: labels.map((_, i) => seriesColor(i)) }}],
    }},
    options: {{
      ...baseOptions("req/s"),
      plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: `Throughput per endpoint (over a ${{BACKEND.windowSeconds}}s window)` }} }},
    }},
  }});

  renderTable(
    document.getElementById("backendTable"),
    [
      {{ key: "label", label: "Endpoint" }},
      {{ key: "count", label: "Requests" }},
      {{ key: "avg", label: "Avg (ms)" }},
      {{ key: "p50", label: "p50 (ms)" }},
      {{ key: "p95", label: "p95 (ms)" }},
      {{ key: "max", label: "Max (ms)" }},
      {{ key: "throughput", label: "req/s" }},
    ],
    BACKEND.stats
  );
}}

if (FRONTEND) {{
  function deviceDatasets(getValue) {{
    return FRONTEND.devices.map((device, i) => ({{
      label: device,
      backgroundColor: seriesColor(i),
      data: FRONTEND.networks.map(network => getValue(network, device) ?? null),
    }}));
  }}

  new Chart(document.getElementById("overviewChart"), {{
    type: "bar",
    data: {{
      labels: FRONTEND.networks,
      datasets: deviceDatasets((network, device) => FRONTEND.overview[network]?.[device]),
    }},
    options: {{
      ...baseOptions("Avg load time (ms)"),
      plugins: {{ legend: {{ position: "top" }}, tooltip: {{ enabled: true }}, title: {{ display: true, text: "Average full load time, all pages" }} }},
    }},
  }});

  const pageChartsEl = document.getElementById("pageCharts");
  FRONTEND.pages.forEach(page => {{
    const wrap = document.createElement("div");
    wrap.innerHTML = `<h4 style="margin:0 0 0.5rem;font-size:0.85rem;color:var(--text-secondary);">${{page}}</h4>
      <div class="page-chart-wrap"><canvas role="img" aria-label="Load time for ${{page}}"></canvas></div>`;
    pageChartsEl.appendChild(wrap);
    const canvas = wrap.querySelector("canvas");
    new Chart(canvas, {{
      type: "bar",
      data: {{
        labels: FRONTEND.networks,
        datasets: deviceDatasets((network, device) => FRONTEND.matrix[page]?.[network]?.[device]),
      }},
      options: {{
        ...baseOptions("Load time (ms)"),
        plugins: {{ legend: {{ position: "top" }}, tooltip: {{ enabled: true }} }},
      }},
    }});
  }});

  renderTable(
    document.getElementById("frontendTable"),
    [
      {{ key: "page", label: "Page" }},
      {{ key: "device", label: "Device" }},
      {{ key: "network", label: "Network" }},
      {{ key: "ttfbMs", label: "TTFB (ms)" }},
      {{ key: "domContentLoadedMs", label: "DOMContentLoaded (ms)" }},
      {{ key: "loadMs", label: "Load (ms)" }},
      {{ key: "firstContentfulPaintMs", label: "FCP (ms)" }},
      {{ key: "transferSizeBytes", label: "Transfer (bytes)" }},
    ],
    FRONTEND.rawRows.map(r => ({{
      ...r,
      ttfbMs: r.ttfbMs != null ? Math.round(r.ttfbMs) : null,
      domContentLoadedMs: r.domContentLoadedMs != null ? Math.round(r.domContentLoadedMs) : null,
      loadMs: r.loadMs != null ? Math.round(r.loadMs) : null,
      firstContentfulPaintMs: r.firstContentfulPaintMs != null ? Math.round(r.firstContentfulPaintMs) : null,
    }}))
  );

  if (FRONTEND.failedRows.length) {{
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = `${{FRONTEND.failedRows.length}} navigation(s) failed and were excluded from the charts above (see console for details).`;
    document.getElementById("frontendTable").parentElement.after(note);
    console.warn("Failed Playwright navigations:", FRONTEND.failedRows);
  }}
}}
</script>
</body>
</html>
"""


def main() -> None:
    if len(sys.argv) > 1:
        run_dir = Path(sys.argv[1]).resolve()
    else:
        run_dir = find_latest_run_dir()
        if run_dir is None:
            print("No benchmark run folder found under results/ — run `make benchmark` first.")
            return

    run_dir.mkdir(parents=True, exist_ok=True)
    k6_data = load_k6(run_dir)
    pw_data = load_playwright(run_dir)

    if k6_data is None and pw_data is None:
        print(f"No raw results found in {run_dir} — run the k6 and/or Playwright benchmarks first.")
        return

    meta_path = run_dir / "meta.json"
    git_ctx = json.loads(meta_path.read_text()) if meta_path.exists() else git_context_fallback()

    html = render_html(k6_data, pw_data, git_ctx)

    if k6_data is not None and pw_data is not None:
        filename = "combined.html"
    elif k6_data is not None:
        filename = "k6.html"
    else:
        filename = "playwright.html"

    report_path = run_dir / filename
    report_path.write_text(html)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
