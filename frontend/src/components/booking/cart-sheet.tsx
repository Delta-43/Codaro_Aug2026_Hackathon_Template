"use client";

/**
 * The basket, and its checkout (`capabilities.cart`).
 *
 * Checkout is a sequence of ordinary bookings, so the outcome can be partial —
 * this reports exactly which items landed and which did not, and leaves the
 * failures in the basket. A basket that silently books three of five is the
 * same failure a repeating series already refuses to make.
 */
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { useCart, type CheckoutResult } from "@/context/cart-context";
import { useApp } from "@/context/app-context";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/modal";
import { formatBookingWhen, formatMoney } from "@/lib/format";

export function CartSheet({
  open,
  onClose,
  tz,
}: {
  open: boolean;
  onClose: () => void;
  tz: string;
}) {
  const { items, remove, checkout, busy } = useCart();
  const { vertical } = useApp();
  const [result, setResult] = useState<CheckoutResult | null>(null);

  const currency = items[0]?.currency ?? "EUR";
  // Only meaningful where every item is priced in one currency — a mixed basket
  // (a cross-border marketplace) gets no single total rather than a wrong one.
  const mixed = items.some((i) => i.currency !== currency);
  const total = items.reduce((sum, i) => sum + i.amountMinorUnits, 0);

  async function book() {
    const outcome = await checkout();
    setResult(outcome);
    if (!outcome.failed.length) onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title="Basket">
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Your basket is empty.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.key} className="flex items-start gap-3 border-b border-border pb-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{item.serviceName}</div>
                <div className="text-xs text-muted-foreground">
                  {item.providerName} · {item.resourceName}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatBookingWhen(item.startUtc, item.endUtc, tz)}
                </div>
              </div>
              <div className="shrink-0 text-sm font-medium">
                {formatMoney(item.amountMinorUnits, item.currency)}
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${item.serviceName}`}
                onPress={() => remove(item.key)}
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </div>
          ))}

          <div className="flex items-baseline justify-between pt-1">
            <span className="text-sm font-semibold">Total</span>
            <span className="text-base font-semibold">
              {mixed ? "—" : formatMoney(total, currency)}
            </span>
          </div>
          {mixed ? (
            <p className="text-xs text-muted-foreground">
              Items are priced in different currencies and are charged separately.
            </p>
          ) : null}

          {result?.failed.length ? (
            <div role="alert" className="rounded-xl border border-destructive/40 p-3">
              <p className="text-sm font-medium">
                {result.booked.length} booked, {result.failed.length} could not be:
              </p>
              <ul className="mt-1 space-y-1">
                {result.failed.map((f) => (
                  <li key={f.key} className="text-sm text-muted-foreground">
                    {f.serviceName} — {f.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <Button className="w-full" isDisabled={busy} onPress={book}>
            {busy
              ? "Working…"
              : `${vertical.bookingVerb} all ${items.length} ${
                  items.length === 1
                    ? vertical.bookingNoun.toLowerCase()
                    : vertical.bookingNounPlural.toLowerCase()
                }`}
          </Button>
        </div>
      )}
    </Modal>
  );
}
