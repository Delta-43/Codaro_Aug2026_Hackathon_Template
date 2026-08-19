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
  useRef,
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
  // Live view of the basket for the checkout loop: the callback's `items`
  // closure is a snapshot, so removals made while booking is in flight would
  // otherwise still be booked. Also the re-entrancy latch — `busy` state
  // re-renders too late to stop a double press.
  const itemsRef = useRef(items);
  itemsRef.current = items;
  const checkingOut = useRef(false);

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
      // be refused by the server for capacity it is itself holding. But a
      // re-add IS a changed intent (new party size / options), so it replaces
      // the stored item rather than being silently ignored.
      const slotKey = item.slotIds.join(",");
      const rest = prev.filter((i) => i.slotIds.join(",") !== slotKey);
      return [...rest, { ...item, key: `${item.serviceId}:${slotKey}` }];
    });
  }, []);

  const remove = useCallback((key: string) => {
    setItems((prev) => prev.filter((i) => i.key !== key));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const checkout = useCallback(async (): Promise<CheckoutResult> => {
    if (checkingOut.current) return { booked: [], failed: [] };
    checkingOut.current = true;
    setBusy(true);
    const booked: Booking[] = [];
    const bookedKeys = new Set<string>();
    const failed: CheckoutResult["failed"] = [];
    try {
      // Sequential, not parallel: two items competing for the last place in the
      // same slot must lose one and keep one, and the server decides which.
      for (const item of itemsRef.current) {
        // Removed from the basket while earlier items were booking — honor it.
        if (!itemsRef.current.some((i) => i.key === item.key)) continue;
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
          bookedKeys.add(item.key);
        } catch (e) {
          failed.push({
            key: item.key,
            serviceName: item.serviceName,
            message: isApiError(e) ? e.message : "Could not be booked.",
          });
        }
      }
      // Drop exactly what was booked. Failures stay for another try, and so
      // does anything added mid-checkout that this run never attempted.
      setItems((prev) => prev.filter((i) => !bookedKeys.has(i.key)));
    } finally {
      checkingOut.current = false;
      setBusy(false);
    }
    return { booked, failed };
  }, []);

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
