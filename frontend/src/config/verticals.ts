import type { VerticalId } from "@/types/domain";

/**
 * The pivot surface for UI *vocabulary*. Every vertical-specific word the UI
 * renders comes from here — components read nouns/verbs/copy from the active
 * vertical, never a hard-coded string. The *data* per vertical lives in the
 * backend seed (the active one is served by GET /vertical); this file is only
 * the labels/nouns/copy the frontend renders.
 */
export interface VerticalConfig {
  id: VerticalId;
  label: string; // human name of the vertical, e.g. "Vehicle rental"
  providerNoun: string; // "Rental company"
  providerNounPlural: string;
  serviceNoun: string; // "Vehicle class"
  serviceNounPlural: string;
  resourceNoun: string; // "Vehicle"
  resourceNounPlural: string;
  bookingVerb: string; // primary CTA, e.g. "Reserve"
  /** Word for the party-size unit in shared_capacity verticals (else null). */
  partyNoun: string | null;
  /** The unit of the calendar — `terms.slot`. "Billing period" for a monthly
   *  plan, "Night" for a hotel. Capitalised; lowercase it mid-sentence. */
  slotNoun: string;
  slotNounPlural: string;
  /** What a completed reservation is called — `terms.booking`. */
  bookingNoun: string;
  bookingNounPlural: string;
  /** What the person booking is called — `terms.client`. */
  clientNoun: string;
  clientNounPlural: string;
  categories: { id: string; label: string }[];
  searchPlaceholder: string;
  copy: {
    /** Empty state on tabs 2 & 3 when no provider is locked in. */
    noProviderTitle: string;
    noProviderBody: string;
    /** Empty state when a calendar has no availability in range. */
    noAvailability: string;
  };
}

export const VERTICALS: Record<VerticalId, VerticalConfig> = {
  fleet: {
    id: "fleet",
    label: "Vehicle rental",
    providerNoun: "Rental company",
    providerNounPlural: "Rental companies",
    serviceNoun: "Vehicle class",
    serviceNounPlural: "Vehicle classes",
    resourceNoun: "Vehicle",
    resourceNounPlural: "Vehicles",
    bookingVerb: "Reserve",
    partyNoun: null,
    // These three default to the wording already on screen, so a config that
    // says nothing about them renders exactly as before. They exist to be
    // overridden by `terms.slot` / `terms.booking` / `terms.client`.
    slotNoun: "Time slot",
    slotNounPlural: "Time slots",
    bookingNoun: "Booking",
    bookingNounPlural: "Bookings",
    clientNoun: "Client",
    clientNounPlural: "Clients",
    categories: [
      { id: "economy", label: "Economy" },
      { id: "suv", label: "SUV" },
      { id: "van", label: "Van" },
      { id: "electric", label: "Electric" },
      { id: "luxury", label: "Luxury" },
    ],
    searchPlaceholder: "Search rental companies",
    copy: {
      noProviderTitle: "No rental company selected",
      noProviderBody: "Find a company in Search to see its vehicles and availability.",
      noAvailability: "No vehicles available in this period.",
    },
  },
  oneToOne: {
    id: "oneToOne",
    label: "Private tutoring",
    providerNoun: "Tutor studio",
    providerNounPlural: "Tutor studios",
    serviceNoun: "Subject",
    serviceNounPlural: "Subjects",
    resourceNoun: "Tutor",
    resourceNounPlural: "Tutors",
    bookingVerb: "Book",
    partyNoun: null,
    // These three default to the wording already on screen, so a config that
    // says nothing about them renders exactly as before. They exist to be
    // overridden by `terms.slot` / `terms.booking` / `terms.client`.
    slotNoun: "Time slot",
    slotNounPlural: "Time slots",
    bookingNoun: "Booking",
    bookingNounPlural: "Bookings",
    clientNoun: "Client",
    clientNounPlural: "Clients",
    categories: [
      { id: "math", label: "Maths & sciences" },
      { id: "languages", label: "Languages" },
      { id: "music", label: "Music" },
      { id: "coding", label: "Coding" },
      { id: "exam", label: "Exam prep" },
    ],
    searchPlaceholder: "Search tutors",
    copy: {
      noProviderTitle: "No tutor studio selected",
      noProviderBody: "Find a studio in Search to see its subjects and open hours.",
      noAvailability: "No open hours in this period.",
    },
  },
  group: {
    id: "group",
    label: "Group classes",
    providerNoun: "Studio",
    providerNounPlural: "Studios",
    serviceNoun: "Class",
    serviceNounPlural: "Classes",
    resourceNoun: "Room",
    resourceNounPlural: "Rooms",
    bookingVerb: "Book",
    partyNoun: "spots",
    // These three default to the wording already on screen, so a config that
    // says nothing about them renders exactly as before. They exist to be
    // overridden by `terms.slot` / `terms.booking` / `terms.client`.
    slotNoun: "Time slot",
    slotNounPlural: "Time slots",
    bookingNoun: "Booking",
    bookingNounPlural: "Bookings",
    clientNoun: "Client",
    clientNounPlural: "Clients",
    categories: [
      { id: "vinyasa", label: "Vinyasa" },
      { id: "hatha", label: "Hatha" },
      { id: "pilates", label: "Pilates" },
      { id: "meditation", label: "Meditation" },
      { id: "strength", label: "Strength" },
    ],
    searchPlaceholder: "Search studios",
    copy: {
      noProviderTitle: "No studio selected",
      noProviderBody: "Find a studio in Search to see its classes and session times.",
      noAvailability: "No sessions scheduled in this period.",
    },
  },
};

export const DEFAULT_VERTICAL: VerticalId = "fleet";

export function getVertical(id: VerticalId): VerticalConfig {
  return VERTICALS[id];
}

// --- pivot overlay ---------------------------------------------------------

/** Overlay the pivot file's `terms`/`copy` onto a static vertical.
 *
 *  The three verticals above are default UI vocabulary — they exist so the
 *  fleet/tutoring/yoga datasets read naturally. `domain.config.json` is the real
 *  pivot surface, and until now the UI ignored its `terms`/`copy` entirely: a
 *  config declaring `service: "Plan"`, `slot: "Billing period"` still rendered
 *  "Subject" and "session", because `getVertical()` was the only source of nouns.
 *  This makes the config win where it speaks and the vertical fill the rest.
 *
 *  Per-field notes, since the two vocabularies are not the same shape:
 *  - `bookingVerb` has no `terms` equivalent, so it always comes from the
 *    vertical. `terms.booking` is a NOUN ("Subscription"); using it as the CTA
 *    would render a button reading "Subscription" instead of "Book".
 *  - `partyNoun` is overridden only when the vertical already has one. `null`
 *    means "this vertical has no party-size concept" and drives whether the
 *    party stepper renders at all; `terms.party` is always populated (it
 *    defaults to "Guests"), so overriding null would surface a party control on
 *    every one-to-one deployment.
 *  - `categories` stay from the vertical: they must match the `categoryId`s the
 *    backend actually seeded, which `terms` says nothing about.
 */
export function applyPivotVocabulary(
  base: VerticalConfig,
  terms: Partial<Record<string, string>>,
  copy: Partial<Record<string, string>>,
): VerticalConfig {
  const pick = (term: string | undefined, fallback: string) => term ?? fallback;
  const providerNounPlural = pick(terms.providers, base.providerNounPlural);
  return {
    ...base,
    label: pick(copy.landingTitle, base.label),
    providerNoun: pick(terms.provider, base.providerNoun),
    providerNounPlural,
    serviceNoun: pick(terms.service, base.serviceNoun),
    serviceNounPlural: pick(terms.services, base.serviceNounPlural),
    resourceNoun: pick(terms.resource, base.resourceNoun),
    resourceNounPlural: pick(terms.resources, base.resourceNounPlural),
    // See the note above: null is a structural signal, not a missing word.
    partyNoun: base.partyNoun === null ? null : pick(terms.party, base.partyNoun),
    slotNoun: pick(terms.slot, base.slotNoun),
    slotNounPlural: pick(terms.slots, base.slotNounPlural),
    bookingNoun: pick(terms.booking, base.bookingNoun),
    bookingNounPlural: pick(terms.bookings, base.bookingNounPlural),
    clientNoun: pick(terms.client, base.clientNoun),
    clientNounPlural: pick(terms.clients, base.clientNounPlural),
    searchPlaceholder: terms.providers
      ? `Search ${providerNounPlural.toLowerCase()}`
      : base.searchPlaceholder,
    copy: {
      // `terms.provider` alone is enough to rebuild these two: they are the
      // "nothing locked in" empty state and only ever name the provider.
      noProviderTitle: terms.provider
        ? `No ${terms.provider.toLowerCase()} selected`
        : base.copy.noProviderTitle,
      noProviderBody: terms.provider
        ? `Find a ${terms.provider.toLowerCase()} in Search to see what it offers.`
        : base.copy.noProviderBody,
      noAvailability: pick(copy.emptyStateSlots, base.copy.noAvailability),
    },
  };
}
