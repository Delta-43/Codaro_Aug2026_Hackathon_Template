// Arbor — a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * A form built from CONFIG descriptors, not from hand-written inputs.
 *
 * Two v2 blocks describe fields the same way — `booking.subject.fields` (the
 * pet/vehicle/child a booking is about) and `metaFields.{entity}` (the
 * no-migration extension point) — and both were declared, validated on write by
 * the backend, and rendered by nothing. A deployment could require a health
 * questionnaire or a purchase-order number and the app offered nowhere to type
 * it, so the only way to satisfy the field was curl.
 *
 * Values are held by the caller (the booking flow owns everything it will POST),
 * so this component stays pure: descriptors in, edits out.
 */
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

/** The shape both `booking.subject.fields[]` and `metaFields.{entity}[]` use. */
export type FieldDescriptor = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
};

export type FieldValues = Record<string, unknown>;

export function FieldForm({
  fields,
  values,
  onChange,
  idPrefix,
}: {
  fields: FieldDescriptor[];
  values: FieldValues;
  onChange: (next: FieldValues) => void;
  idPrefix: string;
}) {
  if (!fields.length) return null;
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });

  return (
    <div className="space-y-3">
      {fields.map((field) => {
        const id = `${idPrefix}-${field.key}`;
        const value = values[field.key];
        return (
          <div key={field.key}>
            <label htmlFor={id} className="mb-1 block text-sm font-medium">
              {field.label}
              {field.required ? <span className="text-muted-foreground"> *</span> : null}
            </label>

            {field.type === "boolean" ? (
              <input
                id={id}
                type="checkbox"
                checked={value === true}
                onChange={(e) => set(field.key, e.target.checked)}
                className="size-4 accent-primary"
              />
            ) : field.type === "select" ? (
              <Select
                id={id}
                value={typeof value === "string" ? value : ""}
                onChange={(e) => set(field.key, e.target.value || undefined)}
              >
                <option value="">—</option>
                {(field.options ?? []).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            ) : (
              // `file` renders as text on purpose: there is no upload endpoint
              // for domain metadata, so the honest control is a reference (a
              // link, a document number) rather than a picker that drops the file.
              <Input
                id={id}
                type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                value={value === undefined || value === null ? "" : String(value)}
                onChange={(e) => {
                  const raw = e.target.value;
                  if (raw === "") return set(field.key, undefined);
                  set(field.key, field.type === "number" ? Number(raw) : raw);
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Drop keys the user left empty, so an untouched optional field is absent from
 *  the request rather than sent as `""` — which a `select` validator would then
 *  reject as "not one of the allowed values". */
export function pruneValues(values: FieldValues): FieldValues {
  const out: FieldValues = {};
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === "") continue;
    out[key] = value;
  }
  return out;
}

/** The required descriptors the user has not answered yet.
 *
 *  Deliberately the mirror image of `pruneValues`: a field counts as missing
 *  exactly when the value it holds is one `pruneValues` would drop from the
 *  request — so the button this gates is disabled precisely when the backend's
 *  `required` check would 422, and never a keystroke longer. */
export function missingRequired(
  fields: FieldDescriptor[],
  values: FieldValues,
): FieldDescriptor[] {
  return fields.filter((field) => {
    if (!field.required) return false;
    const value = values[field.key];
    return value === undefined || value === null || value === "";
  });
}
