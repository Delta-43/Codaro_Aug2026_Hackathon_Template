import Link from "next/link";
import { DocShell, type TocEntry } from "@/components/docs/doc-shell";
import { C, Code, H3, Item, List, Note, Section, Table } from "@/components/docs/prose";

/**
 * Public setup guide for `domain.config.json` — the pivot file. Ungated (sits
 * outside the `(app)` group, like `privacy/`), linked from the landing nav pill.
 *
 * This is a *configuration* reference, not an architecture tour: every block,
 * its real defaults, what each value is allowed to be, and the order to fill
 * them in. Source of truth is `backend/app/config_schema.py` (DEFAULTS +
 * validate) and `backend/app/pricing.py` — when either changes, change this.
 * Defaults quoted here are copied from DEFAULTS, not from the prose docs.
 */
export const metadata = {
  title: "Setting up domain.config.json",
  description:
    "Field-by-field setup guide for the pivot file: every block, its defaults, allowed values, per-service overrides, and how to apply and validate an edit.",
};

const SECTIONS: TocEntry[] = [
  { id: "start", label: "Before you edit" },
  { id: "tenancy", label: "1 · Tenancy" },
  { id: "capabilities", label: "2 · Capabilities" },
  { id: "booking", label: "3 · The booking" },
  { id: "pricing", label: "4 · Pricing" },
  { id: "payments", label: "5 · Payments" },
  { id: "timing", label: "6 · Timing" },
  { id: "location", label: "7 · Location" },
  { id: "optional", label: "8 · Optional blocks" },
  { id: "vocabulary", label: "9 · Words & fields" },
  { id: "overrides", label: "10 · Per-service overrides" },
  { id: "apply", label: "11 · Apply & validate" },
  { id: "enforced", label: "What actually runs" },
  { id: "example", label: "A complete file" },
];

export default function ConfigDocsPage() {
  return (
    <DocShell
      title="Setting up domain.config.json"
      subtitle="The pivot file, field by field: every block, its real default, what each value is allowed to be, and the order to fill them in. You declare only what you change — everything you leave out falls back to a built-in default, so a three-line file boots."
      sections={SECTIONS}
    >
      {/* Mobile TOC — the sidebar is desktop-only. */}
      <nav aria-label="On this page" className="lg:hidden">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          On this page
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                className="inline-block rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="start"
        title="Before you edit"
        lede="One JSON file at the repo root describes the whole business. Here is what to know before you open it."
      >
        <List>
          <Item>
            It lives at <C>domain.config.json</C> in the repo root. Point{" "}
            <C>DOMAIN_CONFIG_PATH</C> somewhere else if you move it.
          </Item>
          <Item>
            It is read once at startup and cached, then served to the app at{" "}
            <C>GET /config</C>.
          </Item>
          <Item>
            A bad edit fails at startup with every problem listed at once. There
            is no such thing as a half-applied config.
          </Item>
        </List>

        <H3 id="start-minimal">Declare only what you change</H3>
        <p>
          Every key has a default in <C>app/config_schema.py</C>. A file that
          declares three keys is complete and valid — the other ~120 resolve
          underneath it. This is the smallest useful file:
        </p>

        <Code label="domain.config.json">{`{
  "configVersion": 2,
  "domain": "clinic",
  "terms": { "provider": "Clinic", "client": "Patient" }
}`}</Code>

        <p>
          So the way to configure this engine is <em>not</em> to fill in a big
          template. Work through the blocks below in order, write down only the
          lines that differ from the default, and leave the rest out.
        </p>

        <H3 id="start-money">Two conventions that trip people up</H3>
        <List>
          <Item>
            <strong className="text-foreground">All money is an integer in minor
            units.</strong> <C>1200</C> with <C>currency: &quot;EUR&quot;</C> is
            €12.00. There are no decimals anywhere in this file.
          </Item>
          <Item>
            <strong className="text-foreground">Lists replace, objects
            merge.</strong> Declaring <C>pricing.tiers</C> means <em>those</em>{" "}
            tiers, not those plus any default. Declaring{" "}
            <C>pricing.rate.per</C> leaves the rest of <C>pricing</C> intact.
          </Item>
        </List>

        <p>
          After any edit, apply it with the two commands in{" "}
          <a href="#apply" className="text-primary underline underline-offset-4">
            step 11
          </a>
          .
        </p>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="tenancy"
        step="Step 1"
        title="Tenancy — one business, or a marketplace?"
        lede="Set this first. It changes the shape of the whole app, so every later choice reads differently depending on it."
      >
        <Table
          head={["Key", "Values", "Default", "What it does"]}
          rows={[
            [
              <C key="a">mode</C>,
              <C key="b">single | multi</C>,
              <C key="c">multi</C>,
              "single collapses the app to one implicit business: no Search tab, four tabs instead of five, the root redirects to the business page, and the business-signup link disappears",
            ],
            [
              <C key="a">providerCode</C>,
              "string | null",
              <C key="c">null</C>,
              "Required in single mode — it is how the app resolves its one business. Leaving it out is a load error",
            ],
            [
              <C key="a">selfOnboarding</C>,
              "bool",
              <span key="c">
                <C>true</C> if <C>mode</C> is <C>multi</C>
              </span>,
              "Whether businesses can sign themselves up. Omit it and it follows the mode; set it explicitly to disagree",
            ],
            [
              <C key="a">tenantVerification</C>,
              <C key="b">{"{required, credentials[]}"}</C>,
              <C key="c">{"{false, []}"}</C>,
              "Licence/KYC gating on the business side",
            ],
            [
              <C key="a">commission</C>,
              <C key="b">{"{enabled, rateBps, chargedOn}"}</C>,
              <C key="c">{"{false, 0, completion}"}</C>,
              "Your platform cut. rateBps is basis points and must be >= 0",
            ],
          ]}
        />

        <Code label="a single business">{`"tenancy": {
  "mode": "single",
  "providerCode": "VISTULA-4471"
}`}</Code>

        <Code label="a marketplace taking 8%">{`"tenancy": {
  "mode": "multi",
  "selfOnboarding": true,
  "commission": { "enabled": true, "rateBps": 800, "chargedOn": "completion" }
}`}</Code>

        <Note title="Global only">
          <p>
            <C>tenancy</C> cannot be overridden per service. Commission and
            tenant verification are platform terms, not a business&apos;s to set
            for itself.
          </p>
        </Note>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="capabilities"
        step="Step 2"
        title="Capabilities — switch features on"
        lede="Ten booleans. Off means the UI hides the surface and the API refuses the write."
      >
        <Table
          head={["Key", "Default", "Key", "Default"]}
          rows={[
            [<C key="a">payments</C>, <C key="b">true</C>, <C key="c">recurrence</C>, <C key="d">false</C>],
            [<C key="a">reviews</C>, <C key="b">true</C>, <C key="c">prerequisites</C>, <C key="d">false</C>],
            [<C key="a">follows</C>, <C key="b">true</C>, <C key="c">entitlements</C>, <C key="d">false</C>],
            [<C key="a">inventory</C>, <C key="b">false</C>, <C key="c">cart</C>, <C key="d">false</C>],
            [<C key="a">waitlist</C>, <C key="b">false</C>, <C key="c">quotes</C>, <C key="d">false</C>],
          ]}
        />

        <p>
          Switching a capability on does not configure it — it only unlocks the
          block. Turning on <C>inventory</C> still leaves{" "}
          <C>inventory.mode</C> at <C>none</C> until you set it.
        </p>

        <Note tone="warn" title="The one cross-check the loader enforces">
          <p>
            If you set <C>capabilities.payments: false</C> you must also set{" "}
            <C>payments.flow: &quot;none&quot;</C>. Otherwise the file is
            rejected: the UI would hide a step the API still enforces, and every
            booking would fail at a screen the customer cannot see.
          </p>
        </Note>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="booking"
        step="Step 3"
        title="Booking — what one booking actually is"
        lede="What is being reserved, in what units, for how long, and for how many people."
      >
        <Table
          head={["Key", "Values", "Default"]}
          rows={[
            [
              <C key="a">unitKind</C>,
              <span key="b">
                <C>time_slot</C> <C>staff</C> <C>asset</C> <C>seat</C> <C>room</C>{" "}
                <C>class_capacity</C> <C>stock_item</C> <C>subscription_slot</C>{" "}
                <C>project</C>
              </span>,
              <C key="c">time_slot</C>,
            ],
            [
              <C key="a">granularity</C>,
              <span key="b">
                <C>minute</C> <C>hour</C> <C>day</C> <C>night</C> <C>week</C>{" "}
                <C>month</C> <C>none</C>
              </span>,
              <C key="c">minute</C>,
            ],
            [
              <C key="a">duration.mode</C>,
              <span key="b">
                <C>fixed</C> <C>variable</C> <C>customer_chosen</C>{" "}
                <C>open_ended</C>
              </span>,
              <C key="c">fixed</C>,
            ],
            [
              <C key="a">duration.minUnits</C> ,
              "int >= 1",
              <C key="c">1</C>,
            ],
            [
              <C key="a">duration.maxUnits</C>,
              "int >= 1, and >= minUnits",
              <C key="c">1</C>,
            ],
            [<C key="a">duration.incrementUnits</C>, "int", <C key="c">1</C>],
            [
              <C key="a">party.mode</C>,
              <span key="b">
                <C>individual</C> <C>group</C> <C>buyout</C>
              </span>,
              <C key="c">individual</C>,
            ],
            [<C key="a">party.min</C>, "int >= 1", <C key="c">1</C>],
            [
              <C key="a">party.max</C>,
              "int >= 1, or null",
              <span key="c">
                <C>null</C> — the resource&apos;s own capacity is the ceiling
              </span>,
            ],
            [
              <C key="a">party.composition</C>,
              <C key="b">{"[{key, label, priceFactor}] | null"}</C>,
              <C key="c">null</C>,
            ],
            [<C key="a">party.matchResourceCapacity</C>, "bool", <C key="c">false</C>],
            [
              <C key="a">sequence</C>,
              <C key="b">{"{enabled, steps, minGapHours, maxGapHours}"}</C>,
              <C key="c">{"{false, 1, 0, null}"}</C>,
            ],
            [
              <C key="a">subject</C>,
              <C key="b">{"{enabled, noun, fields[]}"}</C>,
              <C key="c">{"{false, \"Subject\", []}"}</C>,
            ],
            [
              <C key="a">options</C>,
              <C key="b">{"[{key, label, type, choices[]}]"}</C>,
              <C key="c">[]</C>,
            ],
          ]}
        />

        <H3 id="booking-shapes">Four businesses, four setups</H3>

        <Code label="30-minute appointments — this is the default, write nothing">{`"booking": { "unitKind": "time_slot", "granularity": "minute" }`}</Code>

        <Code label="a court booked by the hour, 1-4 hours, 2-4 players">{`"booking": {
  "unitKind": "asset",
  "granularity": "hour",
  "duration": { "mode": "customer_chosen", "minUnits": 1, "maxUnits": 4 },
  "party": { "mode": "group", "min": 2, "max": 4 }
}`}</Code>

        <Code label="a class of up to 12, priced by age band">{`"booking": {
  "unitKind": "class_capacity",
  "party": {
    "mode": "group", "min": 1, "max": 12,
    "composition": [
      { "key": "adult", "label": "Adult", "priceFactor": 1 },
      { "key": "child", "label": "Child", "priceFactor": 0.5 }
    ]
  }
}`}</Code>

        <Code label="a room booked by the night, about a pet">{`"booking": {
  "unitKind": "room",
  "granularity": "night",
  "duration": { "mode": "customer_chosen", "minUnits": 1, "maxUnits": 30 },
  "subject": {
    "enabled": true, "noun": "Pet",
    "fields": [{ "key": "species", "label": "Species", "type": "select",
                 "options": ["Dog", "Cat"] }]
  }
}`}</Code>

        <H3 id="booking-options">Add-ons</H3>
        <p>
          Each entry in <C>options</C> needs a <C>key</C>, and a <C>type</C> of{" "}
          <C>boolean</C> or <C>select</C>. A <C>select</C> option{" "}
          <strong className="text-foreground">must</strong> carry a non-empty{" "}
          <C>choices</C> list, or the file is rejected.
        </p>
        <Code>{`"options": [
  { "key": "equipment", "label": "Racket hire", "type": "boolean" },
  { "key": "coach", "label": "Coach", "type": "select",
    "choices": ["None", "Group", "Private"] }
]`}</Code>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="pricing"
        step="Step 4"
        title="Pricing — what to charge"
        lede="The block with the most levers, and the one where a mistake costs real money."
      >
        <Note tone="warn" title="pricing.model does not price anything">
          <p>
            It is validated against a list of names, but nothing reads it. The
            arithmetic comes entirely from <C>rate</C>, <C>tiers</C>,{" "}
            <C>fees</C>, <C>caps</C> and <C>deposit</C>. Setting{" "}
            <C>model: &quot;per_hour&quot;</C> and leaving{" "}
            <C>rate.per: &quot;slot&quot;</C> prices per slot. Treat{" "}
            <C>model</C> as a label for humans and set <C>rate.per</C> to mean
            it.
          </p>
        </Note>

        <H3 id="pricing-rate">The rate</H3>
        <p>
          <C>rate.amountMinorUnits</C> is multiplied by a quantity that{" "}
          <C>rate.per</C> chooses:
        </p>

        <Table
          head={["rate.per", "Multiplied by", "Use it for"]}
          rows={[
            [<C key="a">booking</C>, "1", "a flat charge however long or large"],
            [<C key="a">slot</C>, "number of slots held", "the classic appointment (this is the default)"],
            [<C key="a">person</C>, "head count", "per-seat pricing"],
            [
              <C key="a">unit</C>,
              <span key="b">the booking&apos;s <C>unit_count</C></span>,
              "quantities — pallets, bikes, covers",
            ],
            [<C key="a">hour</C>, "fractional hours", "90 minutes is genuinely 1.5"],
            [
              <C key="a">day</C> ,
              "started days",
              "half a day of storage bills as a day",
            ],
            [<C key="a">night</C>, "started nights", "stays"],
            [<C key="a">week</C>, "started weeks", "long hire"],
            [<C key="a">month</C>, "started months", "storage, subscriptions"],
          ]}
        />

        <p>
          Then <C>chargePerPerson</C> decides whether the party multiplies that:
        </p>
        <List>
          <Item>
            <C>true</C> (the default) — <C>amount × quantity × party</C>. Each
            person is buying their own thing.
          </Item>
          <Item>
            <C>false</C> — the party shares one unit. A tennis court costs the
            same for two players or four.
          </Item>
        </List>
        <p>
          <C>rate.per: &quot;person&quot;</C> already counts heads, so it never
          double-counts regardless of this flag.
        </p>

        <Code label="€12.00 an hour for the court, whoever turns up">{`"pricing": {
  "currency": "EUR",
  "rate": { "per": "hour", "amountMinorUnits": 1200 },
  "chargePerPerson": false
}`}</Code>

        <H3 id="pricing-tiers">Tiers — a different price in some circumstance</H3>
        <p>
          Tiers are checked <strong className="text-foreground">in the order
          you write them and the first match wins</strong>, so put the most
          specific first. A matching tier replaces{" "}
          <C>rate.amountMinorUnits</C>. Each needs a <C>key</C> and an{" "}
          <C>amountMinorUnits</C> of 0 or more.
        </p>

        <Code>{`"tiers": [
  { "key": "offpeak", "label": "Off-peak", "amountMinorUnits": 800,
    "appliesWhen": { "timeOfDay": { "from": "08:00", "to": "16:00" } } },
  { "key": "group", "label": "Group of 4+", "amountMinorUnits": 1000,
    "appliesWhen": { "partySize": { "min": 4 } } },
  { "key": "earlybird", "label": "Early bird", "amountMinorUnits": 900,
    "validFrom": "2026-01-01", "validUntil": "2026-03-31" }
]`}</Code>

        <Table
          head={["appliesWhen clause", "Shape", "Matches on"]}
          rows={[
            [
              <C key="a">partySize</C>,
              <C key="b">{"{min, max}"}</C>,
              "head count (weighted, if you use party.composition)",
            ],
            [
              <C key="a">timeOfDay</C>,
              <C key="b">{"{from, to}"}</C>,
              "start time; a window may wrap midnight (18:00 → 06:00)",
            ],
            [<C key="a">zone</C>, "exact string", "seat or area zone"],
            [<C key="a">bookingIndex</C>, <C key="b">{"{min, max}"}</C>, "how many bookings this customer already has"],
            [
              <C key="a">subjectField</C>,
              <C key="b">{"{key, equals}"}</C>,
              "a field on the pet / vehicle / child",
            ],
            [<C key="a">distanceKm</C>, <C key="b">{"{min, max}"}</C>, "travel distance"],
          ]}
        />

        <p>
          Every clause you write must hold for the tier to apply. Any range
          accepts <C>{"{min, max}"}</C> or a bare value for an exact match.{" "}
          <C>validFrom</C> / <C>validUntil</C> gate when the tier is on sale at
          all.
        </p>

        <Note tone="warn" title="An unknown clause never matches">
          <p>
            Misspell <C>partySize</C> as <C>partysize</C> and the tier silently
            applies to nobody. That is deliberate — the alternative is a typo
            widening a discount to every customer — but it means a tier that
            &quot;does nothing&quot; is usually a misspelled clause.
          </p>
        </Note>

        <H3 id="pricing-fees">Fees</H3>
        <p>
          Fees are added after the base. Each needs a <C>kind</C>, and the kind
          decides which other field is required:
        </p>
        <Table
          head={["kind", "Required field", "Effect"]}
          rows={[
            [<C key="a">flat</C>, <C key="b">amountMinorUnits</C>, "added as-is"],
            [<C key="a">percent</C>, <C key="b">rateBps</C>, "basis points of the subtotal — 250 is 2.5%"],
            [
              <C key="a">distanceBand</C>,
              <C key="b">{"bands[{maxKm, feeMinorUnits}]"}</C>,
              "non-empty; picks the band the distance falls in",
            ],
          ]}
        />
        <Code>{`"fees": [
  { "key": "clean", "label": "Cleaning", "kind": "flat", "amountMinorUnits": 1500 },
  { "key": "service", "label": "Service fee", "kind": "percent", "rateBps": 250 },
  { "key": "travel", "label": "Travel", "kind": "distanceBand",
    "bands": [ { "maxKm": 5,  "feeMinorUnits": 0 },
               { "maxKm": 20, "feeMinorUnits": 900 },
               { "maxKm": null, "feeMinorUnits": 2000 } ] }
]`}</Code>

        <H3 id="pricing-caps">Caps and deposit</H3>
        <List>
          <Item>
            <C>caps.perBookingMinorUnits</C> clamps the total. Enforced.
          </Item>
          <Item>
            <C>caps.perDayMinorUnits</C> is accepted but{" "}
            <strong className="text-foreground">not enforced</strong> — it needs
            the customer&apos;s other bookings that day, which is a database
            question, not arithmetic. Do not rely on it.
          </Item>
          <Item>
            <C>deposit</C> is <C>{"{enabled, kind, value, refundable}"}</C>,
            where <C>kind</C> is <C>percent</C> or <C>flat</C>. It is derived
            from the final total. A non-refundable deposit is a prepayment and
            is clamped to never exceed the total; a refundable one is a bond and
            may exceed it.
          </Item>
        </List>

        <H3 id="pricing-order">The order it all runs in</H3>
        <Code>{`1. a matching tier replaces rate.amountMinorUnits
2. base      = amount × quantity(rate.per) × party factor
3. + secondaryRate   (an independent axis, ADDED — see below)
4. + fees            (flat, percent of subtotal, distance band)
5. clamp to caps.perBookingMinorUnits
6. derive the deposit from the final total`}</Code>

        <Note tone="warn" title="Three things that will not do what you expect">
          <List>
            <Item>
              <C>secondaryRate</C> is <strong className="text-foreground">added,
              never multiplied</strong>. &quot;20 pallets × 4 weeks&quot; cannot
              be expressed — you get 20 pallets <em>plus</em> 4 weeks.
            </Item>
            <Item>
              A tier is matched once, against the booking&apos;s{" "}
              <strong className="text-foreground">start</strong> time. A
              17:00–19:00 booking under a 17:00–18:00 happy hour bills entirely
              at the happy-hour rate. Do not configure a band that a booking can
              cross.
            </Item>
            <Item>
              <C>tiers[].quantityCap</C> validates but does not gate — an
              early-bird pool needs a count of what has been sold.
            </Item>
          </List>
        </Note>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="payments"
        step="Step 5"
        title="Payments — when the money moves"
        lede="Who pays, at what point, and on what cycle."
      >
        <Table
          head={["Key", "Values", "Default"]}
          rows={[
            [
              <C key="a">flow</C>,
              <span key="b">
                <C>prepay</C> <C>pay_on_site</C> <C>invoice_after</C>{" "}
                <C>split</C> <C>none</C>
              </span>,
              <C key="c">prepay</C>,
            ],
            [
              <C key="a">payer</C>,
              <span key="b">
                <C>customer</C> <C>third_party</C>
              </span>,
              <C key="c">customer</C>,
            ],
            [
              <C key="a">schedule</C>,
              <C key="b">{"[{key, kind: percent|flat, value}]"}</C>,
              <C key="c">[]</C>,
            ],
            [
              <C key="a">billingCycle</C>,
              <span key="b">
                <C>none</C> <C>weekly</C> <C>monthly</C> <C>annual</C>
              </span>,
              <C key="c">none</C>,
            ],
            [
              <C key="a">noShowFee</C>,
              <C key="b">{"{enabled, amountMinorUnits}"}</C>,
              <C key="c">{"{false, 0}"}</C>,
            ],
            [<C key="a">usageMetered</C>, "bool", <C key="c">false</C>],
            [<C key="a">adapter</C>, "string", <C key="c">manual</C>],
          ]}
        />

        <Note title="There is no payment provider in this build">
          <p>
            <C>adapter: &quot;manual&quot;</C> means the owner marks a booking
            paid by hand. Every flow above can be walked end to end that way, but
            no card is ever charged. <C>noShowFee</C> and <C>schedule</C> are
            recorded, not collected.
          </p>
        </Note>

        <Code label="pay at the counter">{`"capabilities": { "payments": true },
"payments": { "flow": "pay_on_site" }`}</Code>

        <Code label="no money in the product at all">{`"capabilities": { "payments": false },
"payments": { "flow": "none" }`}</Code>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="timing"
        step="Step 6"
        title="Timing — the scheduling rules"
        lede="Slot length, notice, cutoffs, and whether a booking is instant or has to be approved."
      >
        <Table
          head={["Key", "Values", "Default", "Enforced?"]}
          rows={[
            [
              <C key="a">confirmation</C>,
              <span key="b">
                <C>instant</C> <C>request_approve</C>
              </span>,
              <C key="c">instant</C>,
              "Yes — the default behind each service's auto-approve toggle",
            ],
            [<C key="a">leadTimeMinutes</C>, "int >= 0", <C key="c">0</C>, "Yes — minimum notice on booking"],
            [<C key="a">slotDurationMinutes</C>, "int >= 1", <C key="c">30</C>, "Yes"],
            [<C key="a">maxBookingsPerSlot</C>, "int >= 1", <C key="c">1</C>, "Yes, via slot capacity"],
            [<C key="a">cancellationWindowHours</C>, "int >= 0", <C key="c">24</C>, "Yes — on change/cancel"],
            [<C key="a">bufferMinutes</C>, "int >= 0", <C key="c">0</C>, "Yes — on slot creation"],
            [
              <C key="a">advanceBookingWindowDays</C>,
              "int >= 0",
              <C key="c">30</C>,
              "No — the demo seed lays slots further out than this allows",
            ],
            [<C key="a">approvalWindowHours</C>, "int", <C key="c">48</C>, "No — expiring a stale request needs a scheduled job"],
            [
              <C key="a">waitlist</C>,
              <C key="b">{"{enabled, autoPromote, maxPerSlot}"}</C>,
              <C key="c">{"{false, true, 0}"}</C>,
              "No",
            ],
            [
              <C key="a">seasons</C> ,
              <C key="b">{"[{startDate, endDate}]"}</C>,
              <C key="c">[]</C>,
              "No — but both dates are required if you declare one",
            ],
            [
              <C key="a">blackouts</C>,
              <C key="b">{"[{startDate, endDate}]"}</C>,
              <C key="c">[]</C>,
              "No — same shape rule",
            ],
          ]}
        />

        <Code label="24h notice, owner approves each request">{`"timing": {
  "confirmation": "request_approve",
  "leadTimeMinutes": 1440,
  "slotDurationMinutes": 60,
  "cancellationWindowHours": 48
}`}</Code>

        <Note title="The old rules block still works">
          <p>
            Five of these keys — <C>slotDurationMinutes</C>,{" "}
            <C>maxBookingsPerSlot</C>, <C>cancellationWindowHours</C>,{" "}
            <C>advanceBookingWindowDays</C>, <C>bufferMinutes</C> — also live
            under a deprecated <C>rules</C> block, and the loader keeps the two
            in sync in both directions. An old file still boots. In a new file,
            write them under <C>timing</C>; if you write both, <C>timing</C>{" "}
            wins.
          </p>
        </Note>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="location"
        step="Step 7"
        title="Location — where it happens"
        lede="Set the timezone even if you change nothing else in this block."
      >
        <Table
          head={["Key", "Values", "Default"]}
          rows={[
            [
              <C key="a">modes</C>,
              <span key="b">
                non-empty list of <C>on_site</C> <C>at_customer</C>{" "}
                <C>remote</C> <C>delivery</C> <C>pickup</C>
              </span>,
              <C key="c">[&quot;on_site&quot;]</C>,
            ],
            [
              <C key="a">default</C>,
              "one of your own modes — this is checked",
              <C key="c">on_site</C>,
            ],
            [
              <C key="a">timezone</C>,
              "a valid IANA zone — this is checked",
              <C key="c">UTC</C>,
            ],
            [
              <C key="a">distanceUnit</C>,
              <span key="b">
                <C>km</C> <C>mi</C>
              </span>,
              <C key="c">km</C>,
            ],
            [
              <C key="a">origin</C>,
              <C key="b">{"{city, lat, lng} | null"}</C>,
              <C key="c">null</C>,
            ],
            [
              <C key="a">serviceArea</C>,
              <C key="b">{"{radiusKm, travelBufferMinutes, feeBands}"}</C>,
              <C key="c">{"{null, 0, []}"}</C>,
            ],
            [<C key="a">remote.meetingLinkMode</C>, "string", <C key="c">none</C>],
            [
              <C key="a">fulfilment</C>,
              <C key="b">{"{windowMinutes, cutoffHoursBefore}"}</C>,
              <C key="c">{"{60, 0}"}</C>,
            ],
          ]}
        />

        <Code label="a Warsaw business that also travels to the customer">{`"location": {
  "modes": ["on_site", "at_customer"],
  "default": "on_site",
  "timezone": "Europe/Warsaw",
  "distanceUnit": "km",
  "origin": { "city": "Warsaw", "lat": 52.2297, "lng": 21.0122 }
}`}</Code>

        <Note title="Two of these have visible consequences today">
          <p>
            <C>timezone</C> is how availability is grouped for a visitor who is
            not signed in — leave it at <C>UTC</C> and an evening slot can show
            up on the wrong day. <C>origin</C> and <C>distanceUnit</C> are the
            point and unit every &quot;near me&quot; distance is measured with.
          </p>
        </Note>

        <Note tone="warn" title="The most common load error in this block">
          <p>
            <C>location.default</C> must appear in <C>location.modes</C>.
            Setting <C>default: &quot;remote&quot;</C> while <C>modes</C> is
            still <C>[&quot;on_site&quot;]</C> is rejected.
          </p>
        </Note>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="optional"
        step="Step 8"
        title="The optional blocks"
        lede="Leave these alone unless the matching capability is on."
      >
        <H3 id="optional-inventory">inventory</H3>
        <Table
          head={["Key", "Values", "Default"]}
          rows={[
            [
              <C key="a">mode</C>,
              <span key="b">
                <C>none</C> <C>finite</C> <C>rentable</C> <C>consumable</C>{" "}
                <C>serialised</C>
              </span>,
              <C key="c">none</C>,
            ],
            [<C key="a">reservationWindowMinutes</C>, "int >= 0", <C key="c">15</C>],
            [<C key="a">loanPeriodHours</C>, "int | null", <C key="c">null</C>],
            [<C key="a">returnRequired</C>, "bool", <C key="c">false</C>],
            [<C key="a">overdueFeePerDayMinorUnits</C>, "int", <C key="c">0</C>],
            [<C key="a">restockCycle</C>, "string", <C key="c">none</C>],
            [<C key="a">ratioConstraint</C>, "object | null", <C key="c">null</C>],
          ]}
        />

        <H3 id="optional-prereq">prerequisites</H3>
        <p>
          A list. Each entry needs a <C>key</C> and a valid <C>kind</C>;{" "}
          <C>appliesTo</C> defaults to <C>customer</C>.
        </p>
        <Code>{`"prerequisites": [
  { "key": "licence", "kind": "licence", "label": "Driving licence",
    "appliesTo": "customer", "required": true, "validityDays": 365,
    "blocksConfirmation": true }
]

kind      ∈ id_check | licence | intake_form | waiver |
             membership | approval | credential
appliesTo ∈ customer | tenant | subject`}</Code>

        <H3 id="optional-recurrence">recurrence · entitlements · discovery</H3>
        <Table
          head={["Key", "Values", "Default"]}
          rows={[
            [
              <C key="a">recurrence.patterns[]</C>,
              <span key="b">
                <C>weekly</C> <C>biweekly</C> <C>monthly</C>
              </span>,
              <C key="c">[]</C>,
            ],
            [<C key="a">recurrence.maxOccurrences</C>, "int", <C key="c">12</C>],
            [
              <C key="a">recurrence.term</C>,
              <C key="b">{"{mode, noticePeriodDays}"}</C>,
              <C key="c">{"{fixed, 0}"}</C>,
            ],
            [
              <C key="a">entitlements.kind</C>,
              <span key="b">
                <C>none</C> <C>credits</C> <C>membership</C> <C>pass</C>
              </span>,
              <C key="c">none</C>,
            ],
            [
              <C key="a">entitlements.plans[]</C>,
              "objects, each needs a key",
              <C key="c">[]</C>,
            ],
            [
              <C key="a">discovery.mode</C>,
              <span key="b">
                <C>browse</C> <C>reverse</C>
              </span>,
              <C key="c">browse</C>,
            ],
            [
              <C key="a">discovery.facets</C>,
              <C key="b">{"{price, distance, rating, availability, unitKind}"}</C>,
              <span key="c">all <C>true</C> except <C>unitKind</C></span>,
            ],
          ]}
        />
        <p>
          <C>discovery.facets</C> is the search filter row — the one part of
          these three that is wired up today.
        </p>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="vocabulary"
        step="Step 9"
        title="Words, copy, and your own fields"
        lede="Rename every noun in the product, and add fields the engine has never heard of."
      >
        <H3 id="vocab-terms">terms — 17 nouns</H3>
        <p>
          Each must be a non-empty string. Singular and plural are separate keys.
        </p>
        <Code>{`"terms": {
  "provider": "Clinic",   "providers": "Clinics",
  "service":  "Treatment","services":  "Treatments",
  "resource": "Room",     "resources": "Rooms",
  "slot":     "Appointment","slots":   "Appointments",
  "booking":  "Visit",    "bookings":  "Visits",
  "client":   "Patient",  "clients":   "Patients",
  "admin":    "Practice", "admins":    "Practices",
  "staff":    "Clinician","subject":   "Patient", "party": "Guests"
}`}</Code>

        <H3 id="vocab-copy">copy — 10 strings</H3>
        <p>
          <C>landingTitle</C>, <C>landingSubtitle</C>, <C>confirmTitle</C>,{" "}
          <C>emptyStateSlots</C>, <C>emptyStateBookings</C>,{" "}
          <C>requestPending</C>, <C>waitlistJoined</C>, <C>quoteRequested</C>,{" "}
          <C>depositDue</C>, <C>prerequisiteBlocked</C>. All must be non-empty.{" "}
          <C>theme</C> is just <C>{"{primaryColor, radius}"}</C>.
        </p>

        <H3 id="vocab-meta">metaFields — your own data</H3>
        <p>
          Six entities take custom fields: <C>providers</C>, <C>services</C>,{" "}
          <C>resources</C>, <C>slots</C>, <C>bookings</C>, <C>subjects</C>. This
          is the extension point that needs no migration — the values live in
          each table&apos;s <C>metadata</C> column.
        </p>
        <Code>{`"metaFields": {
  "bookings": [
    { "key": "reason", "label": "Reason for visit", "type": "text",
      "required": false, "helpText": null, "visibleTo": "both" },
    { "key": "referral", "label": "Referred by", "type": "select",
      "options": ["GP", "Self", "Insurer"] }
  ]
}`}</Code>
        <Table
          head={["Rule", "Detail"]}
          rows={[
            [
              "Required on every field",
              <span key="a">
                <C>key</C>, <C>label</C>, <C>type</C> — each a non-empty string
              </span>,
            ],
            [
              "Allowed types",
              <span key="a">
                <C>text</C> <C>number</C> <C>boolean</C> <C>date</C>{" "}
                <C>select</C> <C>file</C> (<C>string</C> is accepted as an alias
                for <C>text</C>)
              </span>,
            ],
            [
              <span key="a">A <C>select</C> field</span>,
              <span key="b">must carry a non-empty <C>options</C> list</span>,
            ],
            [
              "Undeclared keys",
              "always pass — you can put anything in metadata without declaring it. Declaring a field is how you opt into validation for it",
            ],
          ]}
        />
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="overrides"
        step="Step 10"
        title="When one service needs different rules"
        lede="Do not fork the file. Put the difference on the service."
      >
        <p>
          A service carries its own partial config, deep-merged over the global
          block. This is what lets two businesses on one deployment price and
          schedule completely differently.
        </p>

        <Code label="POST or PATCH /services">{`{
  "name": "Guided tour",
  "config": {
    "pricing": { "rate": { "per": "person", "amountMinorUnits": 4500 } },
    "timing":  { "confirmation": "request_approve", "leadTimeMinutes": 2880 }
  }
}`}</Code>

        <H3 id="overrides-which">Which blocks you may override</H3>
        <p>
          Exactly nine: <C>booking</C>, <C>pricing</C>, <C>payments</C>,{" "}
          <C>inventory</C>, <C>location</C>, <C>timing</C>, <C>recurrence</C>,{" "}
          <C>entitlements</C>, <C>capabilities</C>. Anything else is a{" "}
          <C>422</C> naming the allowed list.
        </p>
        <p>
          <C>tenancy</C>, <C>prerequisites</C>, <C>discovery</C>, <C>terms</C>,{" "}
          <C>copy</C>, <C>theme</C> and <C>metaFields</C> stay global —
          presentation and platform terms are not a single service&apos;s to
          change.
        </p>

        <H3 id="overrides-precedence">What wins</H3>
        <Code>{`explicit override in the service's config     ← highest
        ↓ falls back to
the service's own column (price, duration, cutoff …)
        ↓ falls back to
domain.config.json
        ↓ falls back to
a built-in default                            ← never null`}</Code>

        <p>
          Overrides go through{" "}
          <strong className="text-foreground">the same validator as the
          global file</strong>, against your deployment&apos;s resolved config —
          so a service cannot set <C>payments.flow: &quot;prepay&quot;</C> on a
          deployment where <C>capabilities.payments</C> is off. An invalid
          override is rejected on write with the problem list, not silently
          dropped.
        </p>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="apply"
        step="Step 11"
        title="Applying an edit, and reading the errors"
        lede="Two commands, and a validator that tells you everything wrong at once."
      >
        <Code label="terminal">{`make reload    # re-read domain.config.json
make reseed    # rebuild the demo catalog to match`}</Code>

        <p>
          <C>make reload</C> re-reads the file. <C>make reseed</C> is only
          needed when the <em>data</em> should change too — renaming your nouns
          does not require it, switching what you sell does.
        </p>

        <p>
          There is also an owner-gated <C>POST /config/reload</C>, which
          validates the new file <em>before</em> dropping the cached one: a bad
          edit comes back as <C>422</C> and the running app keeps serving the
          last good config.
        </p>

        <H3 id="apply-errors">What a rejected file looks like</H3>
        <p>Every problem is listed at once, each with its full path:</p>
        <Code>{`domain.config.json is not a usable domain config:
  - tenancy.providerCode is required when tenancy.mode is 'single'
    (it is how the app resolves its one business)
  - pricing.currency must be a 3-letter ISO 4217 code, got 'EURO'
  - location.timezone must be a valid IANA zone, got 'Europe/Warsawww'
  - capabilities.payments is false, so payments.flow must be 'none'
    (got 'prepay') — otherwise the UI hides a step the API still enforces
This is the file a pivot edits — fix the keys above.`}</Code>

        <H3 id="apply-common">The mistakes that actually happen</H3>
        <Table
          head={["You wrote", "What happens"]}
          rows={[
            [
              <span key="a"><C>&quot;timing&quot;: []</C></span>,
              "Rejected: a block must be the type it is declared as. Checked before anything reads it",
            ],
            [
              <span key="a"><C>mode: &quot;single&quot;</C> with no <C>providerCode</C></span>,
              "Rejected — nothing can resolve the business",
            ],
            [
              <span key="a"><C>location.default</C> not in <C>location.modes</C></span>,
              "Rejected",
            ],
            [
              <span key="a"><C>minUnits</C> above <C>maxUnits</C> (or <C>party.min</C> above <C>party.max</C>)</span>,
              "Rejected",
            ],
            [
              <span key="a">a <C>select</C> option or metaField with no choices/options</span>,
              "Rejected",
            ],
            [
              <span key="a">a fee with <C>kind: &quot;percentage&quot;</C></span>,
              "Rejected — the valid kinds are flat, percent, distanceBand",
            ],
            [
              <span key="a">a misspelled <C>appliesWhen</C> clause</span>,
              "Accepted, and the tier silently never matches. The one failure the validator cannot catch for you",
            ],
          ]}
        />
        <p>
          CI runs this same validator on the file, so a broken config fails the
          build rather than the deploy.
        </p>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="enforced"
        title="What actually runs today"
        lede="The file validates far more than the engine currently reads. Check here before you rely on a key."
      >
        <p>
          Every block above is accepted, stored and served. These are the ones
          with a real reader behind them end to end:
        </p>
        <List>
          <Item>
            <C>pricing.*</C> — the whole quote pipeline, except the three
            exceptions called out in{" "}
            <a href="#pricing" className="text-primary underline underline-offset-4">
              step 4
            </a>
          </Item>
          <Item>
            <C>timing</C> — <C>slotDurationMinutes</C>,{" "}
            <C>maxBookingsPerSlot</C>, <C>cancellationWindowHours</C>,{" "}
            <C>bufferMinutes</C>, <C>leadTimeMinutes</C>, <C>confirmation</C>
          </Item>
          <Item>
            <C>booking.duration.minUnits</C> / <C>maxUnits</C>
          </Item>
          <Item>
            <C>location.timezone</C>, <C>origin</C>, <C>distanceUnit</C>
          </Item>
          <Item>
            <C>metaFields.resources</C>, <C>metaFields.slots</C>,{" "}
            <C>discovery.facets</C>
          </Item>
          <Item>
            <C>tenancy.mode</C>, <C>providerCode</C>, and{" "}
            <C>terms.admin</C> / <C>terms.slot</C>
          </Item>
        </List>
        <p>
          Everything else — inventory, waitlist, prerequisites, recurrence,
          entitlements, the payment flows — is configurable and validated, and
          waiting on its reader. Configure it if you want the file to describe
          your business honestly; do not expect it to gate a booking yet.
        </p>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        id="example"
        title="A complete file"
        lede="A kayak-hire business: hourly asset rental, deposit, travel fee, approval required."
      >
        <Code label="domain.config.json">{`{
  "configVersion": 2,
  "domain": "kayak-hire",

  "tenancy": { "mode": "single", "providerCode": "RIVER-2210" },

  "capabilities": {
    "payments": true, "reviews": true, "follows": true,
    "inventory": true, "prerequisites": true
  },

  "booking": {
    "unitKind": "asset",
    "granularity": "hour",
    "duration": { "mode": "customer_chosen", "minUnits": 1, "maxUnits": 8 },
    "party": { "mode": "group", "min": 1, "max": 2 },
    "options": [
      { "key": "wetsuit", "label": "Wetsuit", "type": "boolean" }
    ]
  },

  "pricing": {
    "currency": "PLN",
    "rate": { "per": "hour", "amountMinorUnits": 4000 },
    "chargePerPerson": false,
    "tiers": [
      { "key": "weekday", "label": "Weekday mornings",
        "amountMinorUnits": 3000,
        "appliesWhen": { "timeOfDay": { "from": "08:00", "to": "12:00" } } }
    ],
    "fees": [
      { "key": "delivery", "label": "Riverside delivery", "kind": "distanceBand",
        "bands": [ { "maxKm": 10, "feeMinorUnits": 0 },
                   { "maxKm": null, "feeMinorUnits": 5000 } ] }
    ],
    "deposit": { "enabled": true, "kind": "flat", "value": 10000,
                 "refundable": true }
  },

  "payments": { "flow": "pay_on_site" },

  "inventory": { "mode": "rentable", "returnRequired": true,
                 "loanPeriodHours": 8, "overdueFeePerDayMinorUnits": 5000 },

  "location": {
    "modes": ["pickup", "delivery"],
    "default": "pickup",
    "timezone": "Europe/Warsaw",
    "distanceUnit": "km",
    "origin": { "city": "Warsaw", "lat": 52.2297, "lng": 21.0122 }
  },

  "prerequisites": [
    { "key": "waiver", "kind": "waiver", "label": "Safety waiver",
      "appliesTo": "customer", "required": true, "blocksConfirmation": true }
  ],

  "timing": {
    "confirmation": "request_approve",
    "leadTimeMinutes": 120,
    "slotDurationMinutes": 60,
    "cancellationWindowHours": 24
  },

  "terms": {
    "provider": "Boathouse", "providers": "Boathouses",
    "resource": "Kayak", "resources": "Kayaks",
    "slot": "Hire window", "slots": "Hire windows",
    "client": "Paddler", "clients": "Paddlers"
  },

  "metaFields": {
    "bookings": [
      { "key": "experience", "label": "Paddling experience", "type": "select",
        "options": ["First time", "Some", "Confident"], "required": true }
    ]
  }
}`}</Code>

        <p>
          Everything not named here — <C>discovery</C>, <C>recurrence</C>,{" "}
          <C>entitlements</C>, <C>copy</C>, <C>theme</C>, the rest of{" "}
          <C>booking</C> and <C>payments</C> — resolves from the defaults, which
          is why a file this short is a complete configuration.
        </p>

        <div className="pt-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary underline underline-offset-4"
          >
            Back to the landing page
          </Link>
        </div>
      </Section>
    </DocShell>
  );
}
