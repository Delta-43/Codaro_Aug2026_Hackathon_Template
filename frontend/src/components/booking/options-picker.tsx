"use client";

/**
 * Paid extras — `booking.options`.
 *
 * Declared in v2 and offered nowhere: a config could sell kit hire, a meal plan
 * or a photo package and the customer had no way to add one. The prices here are
 * for DISPLAY only; `rules.resolve_options` re-derives every amount server-side
 * from the same config, so a client that invents an option or a price is
 * rejected rather than believed.
 */
import type { BookingOption } from "@/types/domain";
import { formatMoney } from "@/lib/format";

const SELECT_CLASS =
  "h-8 rounded-2xl border border-transparent bg-input/50 px-2.5 text-sm";

export function OptionsPicker({
  options,
  values,
  currency,
  onChange,
}: {
  options: BookingOption[];
  values: Record<string, string | boolean>;
  currency: string;
  onChange: (next: Record<string, string | boolean>) => void;
}) {
  if (!options.length) return null;
  const set = (key: string, value: string | boolean) => {
    const next = { ...values };
    if (value === false || value === "") delete next[key];
    else next[key] = value;
    onChange(next);
  };

  const price = (amount?: number) =>
    amount ? ` · ${formatMoney(amount, currency)}` : "";

  return (
    <div className="space-y-3">
      {options.map((option) => {
        const id = `option-${option.key}`;
        if (option.type === "select") {
          const value = typeof values[option.key] === "string" ? (values[option.key] as string) : "";
          return (
            <div key={option.key} className="flex items-center justify-between gap-4">
              <label htmlFor={id} className="text-sm font-medium">
                {option.label}
              </label>
              <select
                id={id}
                value={value}
                onChange={(e) => set(option.key, e.target.value)}
                className={SELECT_CLASS}
              >
                <option value="">None</option>
                {(option.choices ?? []).map((choice) => (
                  <option key={choice.key} value={choice.key}>
                    {choice.label}
                    {price(choice.priceMinorUnits)}
                  </option>
                ))}
              </select>
            </div>
          );
        }
        return (
          <div key={option.key} className="flex items-center justify-between gap-4">
            <label htmlFor={id} className="text-sm font-medium">
              {option.label}
              <span className="font-normal text-muted-foreground">
                {price(option.priceMinorUnits)}
              </span>
            </label>
            <input
              id={id}
              type="checkbox"
              checked={values[option.key] === true}
              onChange={(e) => set(option.key, e.target.checked)}
              className="size-4 accent-primary"
            />
          </div>
        );
      })}
    </div>
  );
}
