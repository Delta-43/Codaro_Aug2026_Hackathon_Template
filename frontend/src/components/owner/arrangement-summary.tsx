// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Who a request is actually FOR.
 *
 * The requests list screens the person who *submitted* the request. On a
 * deployment where `booking.subject` is enabled that is not the important
 * party: the booking is about someone (or something) else — the pet, the
 * vehicle, the patient) and on a `payments.payer: "third_party"` deployment
 * the person paying can be a third one again. This block renders all three off
 * the booking the API already returns:
 *
 * - `booking.subject`, labelled through the SERVICE's own
 *   `booking.subject.fields` descriptors, so the labels pivot with the config
 *   and an undeclared key still renders (humanised) rather than vanishing.
 * - `booking.options` — the chosen paid extras, priced server-side.
 * - the payer, from the booking's `metaFields.bookings` values.
 *
 * The payer read is defensive on purpose: `serialize_booking` does not currently
 * echo the booking's `metadata` back, so `payer_name` / `payer_relationship` are
 * written on create and not returned. It is read here from `metadata` if the
 * backend starts sending it, and from `subject` otherwise; when neither has it
 * the block simply doesn't render. Nothing here breaks either way.
 */

import type { Booking, SubjectField } from "@/types/domain";
import { formatMoney } from "@/lib/format";

/** `date_of_death` -> "Date of death". Last resort only — a declared field uses
 *  its descriptor's label. */
function humanise(key: string): string {
  return key.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(renderValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  const s = String(value);
  // ISO dates are stored as typed; say them the way the rest of the app does.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: "UTC",
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(`${s}T00:00:00Z`));
  }
  return s;
}

/** The booking's declared domain metadata, if the API sends it. Typed locally
 *  rather than on `Booking` — `src/types/domain.ts` is owned elsewhere. */
type WithMetadata = Booking & { metadata?: Record<string, unknown> | null };

export function ArrangementSummary({
  booking,
  fields,
  subjectNoun,
}: {
  booking: Booking;
  /** `service.subject.fields` — the label descriptors. Empty is fine. */
  fields: SubjectField[];
  /** `service.subject.noun` — "The Deceased", "The Pet", "The Vehicle". */
  subjectNoun?: string;
}) {
  const subject = booking.subject ?? {};
  const meta = (booking as WithMetadata).metadata ?? {};
  const labels = new Map(fields.map((f) => [f.key, f.label]));

  // Descriptor order first (the config's own idea of importance), then any key
  // the config never declared, so nothing the customer typed is hidden.
  const keys = [
    ...fields.map((f) => f.key).filter((k) => k in subject),
    ...Object.keys(subject).filter((k) => !labels.has(k)),
  ];
  const rows = keys
    .map((k) => ({ key: k, label: labels.get(k) ?? humanise(k), value: subject[k] }))
    .filter((r) => r.value !== null && r.value !== undefined && r.value !== "");

  const pick = (key: string): string => {
    const v = meta[key] ?? (subject as Record<string, unknown>)[key];
    return typeof v === "string" || typeof v === "number" ? String(v) : "";
  };
  const payerName = pick("payer_name");
  const payerRelationship = pick("payer_relationship");

  const options = booking.options ?? [];

  if (rows.length === 0 && options.length === 0 && !payerName) return null;

  return (
    <div className="mt-2.5 space-y-2 rounded-xl border border-border bg-muted/30 p-2.5">
      {rows.length > 0 ? (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {subjectNoun || "Subject"}
          </p>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
            {rows.map((r) => (
              <div key={r.key} className="contents">
                <dt className="text-muted-foreground">{r.label}</dt>
                <dd className="min-w-0 truncate font-medium">{renderValue(r.value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {options.length > 0 ? (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Selected
          </p>
          <ul className="mt-1 flex flex-wrap gap-1">
            {options.map((o) => (
              <li
                key={o.key}
                className="rounded-full bg-card px-2 py-0.5 text-[11px]"
                title={o.label}
              >
                {o.label}
                {o.amountMinorUnits > 0 ? (
                  <span className="text-muted-foreground">
                    {" "}
                    · {formatMoney(o.amountMinorUnits, booking.currency)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {payerName ? (
        <p className="text-xs">
          <span className="text-muted-foreground">Account settled by </span>
          <span className="font-medium">{payerName}</span>
          {payerRelationship ? (
            <span className="text-muted-foreground"> ({payerRelationship})</span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
