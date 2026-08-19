"use client";

/**
 * The basket — `capabilities.cart`.
 *
 * The capability shipped in v2 with nothing behind it in either half of the
 * stack: the config could turn a cart on and the app had no basket, no
 * add-to-basket and no checkout, so a customer buying three things made three
 * separate trips through the booking flow.
 *
 * Items are held client-side and checked out as a sequence of ordinary
 * `POST /bookings` calls. That is deliberate: the engine commits one booking at
 * a time (capacity is held per booking, and a series already reports partial
 * success the same way), so a basket that claimed to be atomic would be lying.
 * Checkout therefore reports per-item outcomes and keeps the failures in the
 * basket for another try.
 *
 * Persisted to localStorage so a basket survives a tab change or a refresh —
 * losing it on navigation is what makes a cart useless.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Booking, ID, IsoUtc } from "@/types/domain";
import { createBooking, isApiError, type BookingShape } from "@/api";

export type CartItem = BookingShape & {
  /** Client-side id: the basket is a list of intents, not of bookings yet. */
  key: string;
  serviceId: ID;
  serviceName: string;
  providerName: string;
  resourceId: ID;
  resourceName: string;
  slotIds: ID[];
  startUtc: IsoUtc;
  endUtc: IsoUtc;
  partySize: number;
  metadata?: Record<string, unknown>;
  /** What the engine quoted when the item was added, for the basket total. A
   *  re-quote happens at checkout — this is a display value, never a promise. */
  amountMinorUnits: number;
  currency: string;
};

export type CheckoutResult = {
  booked: Booking[];
  failed: { key: string; serviceName: string; message: string }[];
};

interface CartValue {
  items: CartItem[];
  add: (item: Omit<CartItem, "key">) => void;
  remove: (key: string) => void;
  clear: () => void;
  /** Books every item, in order. Successful ones leave the basket; failures
   *  stay in it with their reason reported to the caller. */
  checkout: () => Promise<CheckoutResult>;
  busy: boolean;
}

const CartContext = createContext<CartValue | null>(null);
const STORAGE_KEY = "codaro.cart.v1";

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [busy, setBusy] = useState(false);

  // Hydrated after mount, never during render: the server has no localStorage
  // and a first paint that differs from the server's would hydrate-mismatch.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setItems(JSON.parse(raw) as CartItem[]);
    } catch {
      /* a corrupt basket is an empty basket, not a crash */
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      /* quota/private mode — the basket just does not survive the session */
    }
  }, [items]);

  const add = useCallback((item: Omit<CartItem, "key">) => {
    setItems((prev) => {
      // The same slots twice is a mistake, not two bookings: the second would
      // be refused by the server for capacity it is itself holding.
      const slotKey = item.slotIds.join(",");
      if (prev.some((i) => i.slotIds.join(",") === slotKey)) return prev;
      return [...prev, { ...item, key: `${item.serviceId}:${slotKey}` }];
    });
  }, []);

  const remove = useCallback((key: string) => {
    setItems((prev) => prev.filter((i) => i.key !== key));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const checkout = useCallback(async (): Promise<CheckoutResult> => {
    setBusy(true);
    const booked: Booking[] = [];
    const failed: CheckoutResult["failed"] = [];
    try {
      // Sequential, not parallel: two items competing for the last place in the
      // same slot must lose one and keep one, and the server decides which.
      for (const item of items) {
        try {
          booked.push(
            await createBooking({
              serviceId: item.serviceId,
              resourceId: item.resourceId,
              slotIds: item.slotIds,
              partySize: item.partySize,
              partyBands: item.partyBands,
              options: item.options,
              subject: item.subject,
              metadata: item.metadata,
            }),
          );
        } catch (e) {
          failed.push({
            key: item.key,
            serviceName: item.serviceName,
            message: isApiError(e) ? e.message : "Could not be booked.",
          });
        }
      }
      const failedKeys = new Set(failed.map((f) => f.key));
      setItems((prev) => prev.filter((i) => failedKeys.has(i.key)));
    } finally {
      setBusy(false);
    }
    return { booked, failed };
  }, [items]);

  const value = useMemo(
    () => ({ items, add, remove, clear, checkout, busy }),
    [items, add, remove, clear, checkout, busy],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within <CartProvider>");
  return ctx;
}
