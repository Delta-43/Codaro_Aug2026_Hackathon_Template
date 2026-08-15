import type {
  Booking,
  Provider,
  Resource,
  Service,
  Slot,
  User,
  VerticalId,
} from "@/types/domain";

/**
 * The in-memory store shape. A vertical's `seed()` returns one of these; the
 * live store (src/api/mockStore.ts) holds one and mutates it. This type is
 * internal to the frontend — the backend never sees `MockStore`, only the
 * per-entity shapes from src/types/domain.ts. Kept dependency-free so both the
 * seed builders and the store can import it without a cycle.
 */
export interface MockStore {
  verticalId: VerticalId;
  user: User;
  providers: Provider[];
  services: Service[];
  resources: Resource[];
  slots: Slot[];
  bookings: Booking[];
}
