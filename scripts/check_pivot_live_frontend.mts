/**
 * Validate the FRONTEND contract against payloads the backend really produced.
 *
 * `check_pivot_frontend.mts` runs the client's parsers over the pivot FILES.
 * This runs them over `capture.jsonl` — the live `/config`, `/services` and
 * `/bookings/quote` responses recorded by `check_pivot_live.sh` — so it catches
 * the class the file-based pass cannot: a backend that serves something the
 * client cannot consume.
 *
 *   npx tsx scripts/check_pivot_live_frontend.mts [capture.jsonl]
 */
import { readFileSync } from "node:fs";
import { parsePivotConfig } from "../frontend/src/api/index.ts";
import { applyPivotVocabulary, VERTICALS } from "../frontend/src/config/verticals.ts";

const path = process.argv[2] ?? "/tmp/pivot-capture.jsonl";
const rows = readFileSync(path, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l));

/** Exactly what `types/domain.ts` declares non-optional on `Service`. A missing
 *  one is a runtime crash in the client, not a cosmetic gap. */
const SERVICE_FIELDS = [
  "id", "providerId", "name", "description", "bookingModel", "slotDurationMinutes",
  "minSlotsPerBooking", "maxSlotsPerBooking", "priceMinorUnits", "currency",
  "cancellationCutoffHours", "autoApprove", "capabilities", "pricingModel",
  "rateUnit", "paymentFlow", "billingCycle", "prerequisites", "recurrence",
  "waitlist", "resourceIds",
];
const QUOTE_FIELDS = ["amountMinorUnits", "currency", "depositMinorUnits", "breakdown", "paymentFlow", "entitlement"];

const fails: string[] = [];
const seen = { models: new Set<string>(), flows: new Set<string>(), units: new Set<number>() };

for (const row of rows) {
  const tag = `#${row.n} ${row.domain}`;
  for (const p of row.problems ?? []) fails.push(`${tag}: ${p}`);

  // The client must be able to parse what was actually served.
  let parsed;
  try {
    parsed = parsePivotConfig(row.config);
  } catch (e) {
    fails.push(`${tag}: parsePivotConfig threw on the LIVE config — ${e}`);
    continue;
  }
  for (const base of Object.values(VERTICALS)) {
    const v = applyPivotVocabulary(base, parsed.terms, parsed.copy);
    for (const [k, val] of Object.entries(v))
      if (typeof val === "string" && !val.trim()) fails.push(`${tag}/${base.id}: blank ${k}`);
  }

  const svc = row.service;
  if (!svc) { fails.push(`${tag}: no service to validate`); continue; }
  for (const f of SERVICE_FIELDS)
    if (svc[f] === undefined || svc[f] === null) fails.push(`${tag}: service.${f} is ${svc[f]}`);

  // Shape checks the TS types promise but JSON cannot enforce.
  if (!Array.isArray(svc.prerequisites)) fails.push(`${tag}: prerequisites not an array`);
  if (typeof svc.recurrence?.enabled !== "boolean") fails.push(`${tag}: recurrence.enabled not a boolean`);
  if (typeof svc.waitlist?.enabled !== "boolean") fails.push(`${tag}: waitlist.enabled not a boolean`);
  if (svc.recurrence?.enabled && !svc.recurrence.patterns?.length)
    fails.push(`${tag}: recurrence enabled with no patterns — a control that always fails`);
  if (svc.minSlotsPerBooking > svc.maxSlotsPerBooking)
    fails.push(`${tag}: min ${svc.minSlotsPerBooking} > max ${svc.maxSlotsPerBooking}`);
  seen.models.add(svc.pricingModel);
  seen.flows.add(svc.paymentFlow);
  seen.units.add(svc.slotDurationMinutes);

  const q = row.quote;
  if (!q) { fails.push(`${tag}: no quote captured`); continue; }
  for (const f of QUOTE_FIELDS)
    if (q[f] === undefined) fails.push(`${tag}: quote.${f} missing`);
  if (!Array.isArray(q.breakdown) || !q.breakdown.length)
    fails.push(`${tag}: quote has no breakdown — the confirm screen would render an empty bill`);
  // The confirm screen shows a breakdown AND a total; they must agree or the
  // customer sees lines that do not add up to what they are charged.
  const sum = (q.breakdown ?? []).reduce((a: number, b: { amountMinorUnits: number }) => a + b.amountMinorUnits, 0);
  if (sum !== q.amountMinorUnits)
    fails.push(`${tag}: breakdown sums to ${sum} but total is ${q.amountMinorUnits}`);
}

console.log(`pivots captured        : ${rows.length}`);
console.log(`pricing models served  : ${[...seen.models].sort().join(", ")}`);
console.log(`payment flows served   : ${[...seen.flows].sort().join(", ")}`);
console.log(`slot lengths served    : ${[...seen.units].sort((a, b) => a - b).join(", ")}`);

if (fails.length) {
  console.log(`\nFAILURES (${fails.length}):`);
  for (const f of fails.slice(0, 60)) console.log(`  ${f}`);
  if (fails.length > 60) console.log(`  ... and ${fails.length - 60} more`);
  process.exit(1);
}
console.log("\nevery captured pivot satisfies the frontend contract");
