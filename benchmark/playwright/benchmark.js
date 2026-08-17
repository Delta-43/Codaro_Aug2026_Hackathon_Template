// Frontend device/network performance matrix. Loads key app pages under a
// grid of {device emulation} x {network throttle} combinations and records
// navigation timing (TTFB, DOMContentLoaded, full load, first contentful
// paint) for each. Logs in once per device with a dedicated benchmark
// customer account (see ../create_bench_users.py) — NOT the seeded
// demo@codaro.app account — so this never touches the bookings/reviews/
// follows attached to the "real" demo data. lib.sh's ensure_bench_user
// (called automatically by run.sh/run-k6.sh/run-playwright.sh, i.e. any
// `make benchmark*` target) must have run at least once so the account
// exists.
//
// Run via `make benchmark` (docker compose, see ../docker-compose.yml)
// or directly: BASE_URL=http://localhost:3000 node benchmark.js

const { chromium, devices } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const OUTPUT = process.env.OUTPUT || path.join(__dirname, "..", "results", "playwright-results.json");
// Slow 3G against an unminified Next dev bundle can genuinely take longer
// than this — a timeout there is a real finding, not a bug. Raise it (trading
// a longer run) if you want the actual tail load time instead of a cutoff.
const NAV_TIMEOUT_MS = Number(process.env.NAV_TIMEOUT_MS || 45000);

const BENCH_USER = {
  email: process.env.BENCH_EMAIL || "bench-customer-1@codaro.bench",
  password: process.env.BENCH_PASSWORD || "Codaro-Bench-2026",
};

const DEVICE_PROFILES = [
  { name: "Desktop", context: { viewport: { width: 1440, height: 900 } } },
  { name: "Mobile - iPhone 13", context: { ...devices["iPhone 13"] } },
  { name: "Mobile - Pixel 5", context: { ...devices["Pixel 5"] } },
];

// Throughput/latency numbers mirror Chrome DevTools' standard throttling presets.
const NO_THROTTLE = { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 };
const NETWORK_PROFILES = [
  { name: "No throttle", cdp: NO_THROTTLE },
  {
    name: "4G",
    cdp: { offline: false, latency: 20, downloadThroughput: (4 * 1024 * 1024) / 8, uploadThroughput: (3 * 1024 * 1024) / 8 },
  },
  {
    name: "Slow 3G",
    cdp: { offline: false, latency: 400, downloadThroughput: (500 * 1024) / 8, uploadThroughput: (500 * 1024) / 8 },
  },
];

const AUTHENTICATED_PAGES = [
  { name: "Search", path: "/search" },
  { name: "Calendar", path: "/calendar" },
  { name: "Bookings", path: "/bookings" },
  { name: "Account", path: "/account" },
];

async function applyNetwork(client, network) {
  await client.send("Network.emulateNetworkConditions", network.cdp);
}

async function collectTiming(page) {
  return page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    const paint = performance.getEntriesByType("paint");
    const fcp = paint.find((p) => p.name === "first-contentful-paint");
    if (!nav) return null;
    return {
      ttfbMs: nav.responseStart - nav.startTime,
      domContentLoadedMs: nav.domContentLoadedEventEnd - nav.startTime,
      loadMs: nav.loadEventEnd - nav.startTime,
      firstContentfulPaintMs: fcp ? fcp.startTime : null,
      transferSizeBytes: nav.transferSize || null,
    };
  });
}

async function measure(page, url, pageName, deviceName, networkName) {
  const startedAt = Date.now();
  let timing = null;
  let error = null;
  try {
    await page.goto(url, { waitUntil: "load", timeout: NAV_TIMEOUT_MS });
    timing = await collectTiming(page);
  } catch (err) {
    error = err.message;
  }
  console.log(
    `  [${deviceName} / ${networkName}] ${pageName}: ` +
      (timing
        ? `load=${Math.round(timing.loadMs)}ms fcp=${timing.firstContentfulPaintMs ? Math.round(timing.firstContentfulPaintMs) : "n/a"}ms`
        : `FAILED (${error})`)
  );
  return {
    page: pageName,
    device: deviceName,
    network: networkName,
    ...(timing || {}),
    error,
    measuredAt: new Date(startedAt).toISOString(),
  };
}

async function login(page, client) {
  await applyNetwork(client, { cdp: NO_THROTTLE }); // login itself isn't what we're timing
  await page.goto(`${BASE_URL}/login`, { waitUntil: "load", timeout: NAV_TIMEOUT_MS });
  await page.fill("#email", BENCH_USER.email);
  await page.fill("#password", BENCH_USER.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/search/, { timeout: NAV_TIMEOUT_MS });
}

async function warmUp(browser) {
  // Next dev compiles routes on first visit; that compile time would otherwise
  // swamp every other signal, so hit each route once before the timed runs.
  console.log("Warming up Next.js dev routes (first compile is slow and would skew results)...");
  const context = await browser.newContext();
  const page = await context.newPage();
  const client = await context.newCDPSession(page);
  try {
    await login(page, client);
    for (const p of AUTHENTICATED_PAGES) {
      await page.goto(`${BASE_URL}${p.path}`, { waitUntil: "load", timeout: NAV_TIMEOUT_MS }).catch(() => {});
    }
  } catch (err) {
    console.warn(`Warm-up login failed (${err.message}) — authenticated pages will be skipped.`);
  }
  await context.close();
}

async function run() {
  const browser = await chromium.launch();
  await warmUp(browser);

  const results = [];

  for (const device of DEVICE_PROFILES) {
    const context = await browser.newContext({ ...device.context });
    const page = await context.newPage();
    const client = await context.newCDPSession(page);

    for (const network of NETWORK_PROFILES) {
      await applyNetwork(client, network);
      results.push(await measure(page, `${BASE_URL}/login`, "Login (signed out)", device.name, network.name));
    }

    let loggedIn = true;
    try {
      await login(page, client);
    } catch (err) {
      loggedIn = false;
      console.warn(`[${device.name}] login failed (${err.message}) — skipping authenticated pages.`);
    }

    if (loggedIn) {
      for (const network of NETWORK_PROFILES) {
        await applyNetwork(client, network);
        for (const target of AUTHENTICATED_PAGES) {
          results.push(await measure(page, `${BASE_URL}${target.path}`, target.name, device.name, network.name));
        }
      }
    }

    await context.close();
  }

  await browser.close();

  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, JSON.stringify(results, null, 2));
  console.log(`Wrote ${results.length} measurements to ${OUTPUT}`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
