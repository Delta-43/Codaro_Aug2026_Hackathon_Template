/**
 * Run every `pivots/*.json` through the FRONTEND's own parsers.
 *
 * `check_pivot_states.py` proves the backend serves a coherent product for each
 * pivot. This is the other half: that the client can parse what it is served
 * and render a complete vocabulary from it.
 *
 * It imports the real `parsePivotConfig` and `applyPivotVocabulary` rather than
 * reimplementing them, so a change to either is exercised here automatically —
 * a copy would pass long after the app started failing.
 *
 *   npx tsx scripts/check_pivot_frontend.mts      # from frontend/
 *   make checkfront                               # or via the Makefile
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { parsePivotConfig } from "../frontend/src/api/index.ts";
import { applyPivotVocabulary, VERTICALS } from "../frontend/src/config/verticals.ts";
import type { VerticalConfig } from "../frontend/src/config/verticals.ts";

const PIVOTS = join(import.meta.dirname, "..", "pivots");

/** Every noun the UI renders. An empty or `undefined` one is a blank label on
 *  screen, which is the failure this whole file exists to catch. */
const NOUNS: (keyof VerticalConfig)[] = [
  "label", "providerNoun", "providerNounPlural", "serviceNoun", "serviceNounPlural",
  "resourceNoun", "resourceNounPlural", "bookingVerb", "searchPlaceholder",
  "slotNoun", "slotNounPlural", "bookingNoun", "bookingNounPlural",
  "clientNoun", "clientNounPlural",
];

const files = readdirSync(PIVOTS).filter((f) => /^\d+.*\.json$/.test(f)).sort();
const fails: string[] = [];
const seen = { tenancy: new Set<string>(), unit: new Set<string>(), themed: 0, single: 0 };

for (const file of files) {
  const raw = JSON.parse(readFileSync(join(PIVOTS, file), "utf8"));
  let parsed;
  try {
    parsed = parsePivotConfig(raw);
  } catch (e) {
    fails.push(`${file}: parsePivotConfig threw — ${e}`);
    continue;
  }

  seen.tenancy.add(parsed.tenancy.mode);
  if (parsed.tenancy.mode === "single") seen.single++;
  if (parsed.theme.primaryColor) seen.themed++;

  // Single-tenant collapses the marketplace onto one business resolved by code.
  // Without one the app renders its "no business" empty state forever.
  if (parsed.tenancy.mode === "single" && !parsed.tenancy.providerCode)
    fails.push(`${file}: single tenancy with no providerCode`);

  if (!["km", "mi"].includes(parsed.location.distanceUnit))
    fails.push(`${file}: distanceUnit ${parsed.location.distanceUnit}`);
  if (!parsed.location.timezone) fails.push(`${file}: empty timezone`);

  // Assert on the RAW config, not the parsed one. The parsers sanitise — a
  // non-boolean capability and a blank term are both dropped — so checking
  // after them can never fire. What matters is that nothing the author WROTE
  // was silently discarded: a `capabilities.reviews: "yes"` is ignored and the
  // surface stays on, which is the opposite of what they asked for.
  for (const [k, v] of Object.entries(raw.capabilities ?? {}))
    if (typeof v !== "boolean")
      fails.push(`${file}: capabilities.${k} is ${typeof v}, silently ignored`);
  for (const block of ["terms", "copy"] as const)
    for (const [k, v] of Object.entries(raw[block] ?? {}))
      if (typeof v !== "string" || !v.trim())
        fails.push(`${file}: ${block}.${k} is ${JSON.stringify(v)}, silently ignored`);

  // A radius/colour the browser cannot parse yields an invisible broken theme.
  if (parsed.theme.radius && !/^-?[\d.]+(rem|px|em|%)$/.test(parsed.theme.radius))
    fails.push(`${file}: theme.radius ${parsed.theme.radius}`);

  // The overlay must produce a complete vocabulary from EVERY vertical, because
  // which one is active is decided by the seeded data, not by the config.
  for (const base of Object.values(VERTICALS)) {
    const v = applyPivotVocabulary(base, parsed.terms, parsed.copy);
    for (const noun of NOUNS) {
      const value = v[noun];
      if (typeof value !== "string" || !value.trim())
        fails.push(`${file}/${base.id}: ${String(noun)} is ${JSON.stringify(value)}`);
    }
    for (const [key, value] of Object.entries(v.copy))
      if (typeof value !== "string" || !value.trim())
        fails.push(`${file}/${base.id}: copy.${key} is ${JSON.stringify(value)}`);
    seen.unit.add(v.slotNoun);
  }
}

console.log(`pivots checked            : ${files.length}`);
console.log(`tenancy modes             : ${[...seen.tenancy].sort().join(", ")} (${seen.single} single)`);
console.log(`configs with a theme colour: ${seen.themed}`);
console.log(`distinct slot nouns rendered: ${seen.unit.size}`);

if (fails.length) {
  console.log(`\nFAILURES (${fails.length}):`);
  for (const f of fails.slice(0, 40)) console.log(`  ${f}`);
  if (fails.length > 40) console.log(`  ... and ${fails.length - 40} more`);
  process.exit(1);
}
console.log("\nall pivots parse and render a complete vocabulary");
