// Backend API load test, two scenarios:
//
// 1. api_browse — read path a search/browse session hits (config -> providers
//    -> services -> resources -> availability -> slots), plus, once logged
//    in, the authenticated reads a signed-in session also makes (/me,
//    /bookings). providers_search rotates through a few real query shapes
//    (unfiltered / by category / by text) instead of always the same URL.
// 2. booking_write — the actual write path: create a booking against a real
//    seeded slot, then cancel it, back to back. Low VU count on purpose (see
//    BOOKING_WRITE_VUS below) — this exercises slot-capacity locking and RLS
//    writes, which are heavier than the read path and the whole reason this
//    scenario exists, not something to hide behind read-path VU counts.
//
// Run via `make benchmark` (docker compose, see ../docker-compose.yml) or,
// from inside benchmark/, directly: docker run --rm --network host \
//   -v "$PWD/k6:/scripts" -v "$PWD/results:/results" \
//   --env-file ../backend/.env \
//   -e BASE_URL=http://localhost:8000 \
//   grafana/k6 run --out json=/results/k6-events.jsonl /scripts/api-load-test.js

import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
// This hits your real, hosted Supabase project (not a local DB) via the
// backend, so the default peak is deliberately modest. In testing, the
// backend's shared httpx client starts throwing connection-level errors
// (httpx.RemoteProtocolError, WriteError: Broken pipe, and even internal
// httpcore/h2 KeyErrors from corrupted HTTP/2 stream bookkeeping) once
// Supabase itself starts terminating connections under concurrent load —
// this is a real ceiling in the current stack, not a bug in the benchmark,
// and it triggers earlier now that api_browse carries 2 authenticated
// requests and booking_write adds write pressure on top. Raise PEAK_VUS
// deliberately if you want to find/confirm that ceiling; keep it low for a
// clean run.
const PEAK_VUS = Number(__ENV.PEAK_VUS || 10);
// Booking writes are heavier (multiple inserts + RLS) than the read path, so
// they run at a fraction of PEAK_VUS, capped low — this is meant to exercise
// slot-locking under *some* concurrency, not to hammer the write path as hard
// as the read path.
const BOOKING_WRITE_VUS = Number(__ENV.BOOKING_WRITE_VUS || Math.max(1, Math.min(5, Math.ceil(PEAK_VUS / 10))));

// Same account benchmark/create_bench_users.py provisions, logged in the same
// way the frontend does (Supabase GoTrue password grant) — the backend never
// issues tokens itself, see backend/app/auth.py.
const SUPABASE_URL = __ENV.SUPABASE_URL;
const SUPABASE_ANON_KEY = __ENV.SUPABASE_ANON_KEY;
const BENCH_EMAIL = __ENV.BENCH_EMAIL || "bench-customer-1@codaro.bench";
const BENCH_PASSWORD = __ENV.BENCH_PASSWORD || "Codaro-Bench-2026";

export const options = {
  scenarios: {
    api_browse: {
      executor: "ramping-vus",
      exec: "browse",
      startVUs: 0,
      stages: [
        { duration: "15s", target: Math.ceil(PEAK_VUS / 3) },
        { duration: "30s", target: PEAK_VUS },
        { duration: "30s", target: PEAK_VUS },
        { duration: "15s", target: Math.ceil(PEAK_VUS / 3) },
        { duration: "10s", target: 0 },
      ],
    },
    booking_write: {
      executor: "ramping-vus",
      exec: "bookingWrite",
      startVUs: 0,
      stages: [
        { duration: "10s", target: BOOKING_WRITE_VUS },
        { duration: "30s", target: BOOKING_WRITE_VUS },
        { duration: "10s", target: 0 },
      ],
    },
  },
};

// Logs in against Supabase directly (GoTrue password grant) — the same call
// the frontend's Supabase JS client makes, since the backend only verifies
// tokens, it never issues them.
function login() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error(
      "SUPABASE_URL / SUPABASE_ANON_KEY not set — pass --env-file ../backend/.env (docker-compose.yml's k6 " +
        "service does this already) so the benchmark can log in as the bench customer."
    );
  }
  const res = http.post(
    `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
    JSON.stringify({ email: BENCH_EMAIL, password: BENCH_PASSWORD }),
    {
      headers: { apikey: SUPABASE_ANON_KEY, "Content-Type": "application/json" },
      tags: { name: "setup" },
    }
  );
  const token = res.json("access_token");
  if (!token) {
    throw new Error(
      `Login as ${BENCH_EMAIL} failed (${res.status}) — run \`make benchmark\` (which provisions this ` +
        "account via create_bench_users.py) or create it manually first."
    );
  }
  return token;
}

// setup() runs once, outside the VU loop, to discover real seeded IDs so the
// timed requests below hit real data instead of 404s.
export function setup() {
  const providers = http.get(`${BASE_URL}/providers`, { tags: { name: "setup" } }).json();
  const provider = providers[0];
  if (!provider) {
    throw new Error("No seeded providers found — run `make reseed` before benchmarking.");
  }

  const services = http
    .get(`${BASE_URL}/services?provider_id=${provider.id}`, { tags: { name: "setup" } })
    .json();
  const service = services[0];

  const resources = http
    .get(`${BASE_URL}/resources?service_id=${service.id}`, { tags: { name: "setup" } })
    .json();
  const resource = resources[0];

  const now = new Date();
  const to = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

  // A few real query shapes to rotate providers_search through, instead of
  // always hitting the exact same unfiltered URL — built from the actual
  // seeded categories/names rather than hardcoded guesses.
  const categories = [...new Set(providers.map((p) => p.categoryId).filter(Boolean))];
  const searchVariants = [`${BASE_URL}/providers`];
  if (categories[0]) searchVariants.push(`${BASE_URL}/providers?category_id=${categories[0]}`);
  if (provider.name) {
    searchVariants.push(`${BASE_URL}/providers?text=${encodeURIComponent(provider.name.split(" ")[0])}`);
  }
  if (categories[1]) searchVariants.push(`${BASE_URL}/providers?category_id=${categories[1]}`);

  // Slots at least 72h out — comfortably past any cancellationCutoffHours
  // (24h default, per-service override possible) so the booking_write
  // scenario's cancel-right-after-create round trip never gets blocked by
  // the cutoff rule itself. Raw /slots rows are snake_case (unlike the
  // camelCase domain endpoints) — see backend/app/routers/slots.py.
  let bookableSlotIds = [];
  if (resource) {
    const slots = http
      .get(`${BASE_URL}/slots?resource_id=${resource.id}`, { tags: { name: "setup" } })
      .json();
    const safeFrom = new Date(now.getTime() + 72 * 60 * 60 * 1000);
    bookableSlotIds = slots.filter((s) => new Date(s.starts_at) > safeFrom).map((s) => s.id).slice(0, 20);
  }

  return {
    providerId: provider.id,
    serviceId: service.id,
    resourceId: resource ? resource.id : null,
    fromIso: now.toISOString(),
    toIso: to.toISOString(),
    searchVariants,
    bookableSlotIds,
    authToken: login(),
  };
}

export function browse(data) {
  const authHeaders = { headers: { Authorization: `Bearer ${data.authToken}` } };
  const searchUrl = data.searchVariants[(__VU + __ITER) % data.searchVariants.length];

  const reqs = [
    ["config", `${BASE_URL}/config`, {}],
    ["providers_search", searchUrl, {}],
    ["services_list", `${BASE_URL}/services?provider_id=${data.providerId}`, {}],
    ["resources_list", `${BASE_URL}/resources?service_id=${data.serviceId}`, {}],
    [
      "availability",
      `${BASE_URL}/availability?service_id=${data.serviceId}&from=${data.fromIso}&to=${data.toIso}`,
      {},
    ],
    ["me", `${BASE_URL}/me`, authHeaders],
    ["bookings_list", `${BASE_URL}/bookings?scope=upcoming`, authHeaders],
  ];
  if (data.resourceId) {
    reqs.push(["slots_list", `${BASE_URL}/slots?resource_id=${data.resourceId}`, {}]);
  }

  for (const [name, url, params] of reqs) {
    const res = http.get(url, { ...params, tags: { name } });
    check(res, { "status is 200": (r) => r.status === 200 }, { name });
  }
}

// Create a booking against a real slot, then cancel it — round-tripping so
// repeated runs never permanently consume a slot's capacity=1 seat. A
// booking_create 409 here (SLOT_UNAVAILABLE) can be a real signal, not
// automatically a bug — two VUs landing on the same slot in the same instant
// is exactly the capacity-locking contention this scenario exists to probe.
export function bookingWrite(data) {
  if (!data.bookableSlotIds.length) return;

  const headers = { Authorization: `Bearer ${data.authToken}`, "Content-Type": "application/json" };
  const slotId = data.bookableSlotIds[(__VU + __ITER) % data.bookableSlotIds.length];

  const createRes = http.post(
    `${BASE_URL}/bookings`,
    JSON.stringify({
      serviceId: data.serviceId,
      resourceId: data.resourceId,
      slotIds: [slotId],
      partySize: 1,
    }),
    { headers, tags: { name: "booking_create" } }
  );
  const created = check(createRes, { "status is 200": (r) => r.status === 200 }, { name: "booking_create" });
  if (!created) return;

  const bookingId = createRes.json("id");
  const cancelRes = http.post(`${BASE_URL}/bookings/${bookingId}/cancel`, null, {
    headers,
    tags: { name: "booking_cancel" },
  });
  check(cancelRes, { "status is 200": (r) => r.status === 200 }, { name: "booking_cancel" });
}

// bookingWrite() cancels what it creates, but a booking row survives a
// cancel (status flips to "cancelled", the row itself is never deleted —
// bookings.client_id has no FK/cascade, see supabase/schema.sql) and an
// iteration cut off mid-flight by scenario ramp-down (create succeeds,
// cancel never fires) leaves one "confirmed", permanently consuming a
// capacity=1 slot's seat. Left alone, every run would grow the bench
// account's booking history forever, which (a) never frees those stray
// confirmed seats and (b) makes GET /bookings itself slower and more
// failure-prone over time — it batches several Supabase calls (slot ids,
// slot times, reviews, provider/service names — see
// backend/app/routers/bookings.py's `_enrich`) over *every* booking the
// user has, not just the ones in scope, so a growing history directly
// inflates every future run's request cost.
//
// So teardown() doesn't just cancel stray bookings, it deletes the bench
// account entirely via the backend's own GDPR-erasure endpoint (DELETE
// /me — hard-deletes all of the user's bookings regardless of status, then
// the auth account itself). run.sh's create_bench_users.py step re-provisions
// a fresh bench-customer-1@codaro.bench before the *next* run's k6 step, so
// every run starts from the same blank slate instead of an ever-growing one.
export function teardown(data) {
  const res = http.del(`${BASE_URL}/me`, null, {
    headers: { Authorization: `Bearer ${data.authToken}` },
    tags: { name: "teardown" },
  });
  console.log(
    res.status === 204
      ? "teardown: erased the bench account (bookings + auth user) — run create_bench_users.py before the next run"
      : `teardown: DELETE /me failed (${res.status}) — bench account may carry over stray bookings into the next run`
  );
}
