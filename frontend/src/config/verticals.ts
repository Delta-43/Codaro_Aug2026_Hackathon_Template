import type { VerticalId } from "@/types/domain";

/**
 * The pivot surface for UI *vocabulary*. Every vertical-specific word the UI
 * renders comes from here — components read nouns/verbs/copy from the active
 * vertical, never a hard-coded string. The demo's *data* per vertical now lives
 * in the backend seed (POST /demo/vertical reseeds it); this file is only the
 * labels/nouns/copy the frontend renders.
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

export const VERTICAL_IDS: VerticalId[] = ["fleet", "oneToOne", "group"];

export function getVertical(id: VerticalId): VerticalConfig {
  return VERTICALS[id];
}
