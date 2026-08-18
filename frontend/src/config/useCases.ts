/**
 * Demo use cases — the switchable "niche" layer for the demo.
 *
 * The engine itself is niche-agnostic (provider → service → resource → slot →
 * booking). This registry is a *frontend* demo overlay: each entry carries the
 * vocabulary + a full set of hard-coded mock data (a showcase business, its
 * offers, requests, reviews, gallery) so the demo can present any of these
 * niches without backend seeding. Selected in Settings → Demo; stored
 * client-side (see `lib/demo-use-case.ts`). Adding a niche is pure data here —
 * keep that flexibility (remember the 16:00 pivot).
 *
 * Vocabulary field names mirror `config/verticals.ts` so components can read
 * nouns/verbs the same way regardless of which layer supplies them.
 */
import type { BookingModel } from "@/types/domain";

export type UseCaseId =
  | "cars"
  | "hotels"
  | "venues"
  | "catering"
  | "equipment"
  | "services"
  | "trades"
  | "cleaning"
  | "tutors"
  | "consulting";

interface UseCaseService {
  name: string;
  priceMajor: number;
  currency: string;
  model: BookingModel;
}

export interface UseCase {
  id: UseCaseId;
  label: string; // "Hotel Rooms"
  providerNoun: string;
  providerNounPlural: string;
  serviceNoun: string;
  serviceNounPlural: string;
  resourceNoun: string;
  resourceNounPlural: string;
  bookingVerb: string;
  partyNoun: string | null;
  categories: { id: string; label: string }[];
  searchPlaceholder: string;
  /** The showcase business shown across business mode in this niche. */
  business: { name: string; tagline: string; bio: string; city: string; rating: number; reviewCount: number };
  services: UseCaseService[];
}

export const USE_CASES: Record<UseCaseId, UseCase> = {
  cars: {
    id: "cars",
    label: "Cars",
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
    business: {
      name: "Ibiza Car Rentals",
      tagline: "Spotless cars, keyless pickup",
      bio: "Premium & everyday vehicles across the island — spotless cars, keyless pickup and honest rates. From beach buggies to weekend 4x4s, we get you on the road fast.",
      city: "Ibiza",
      rating: 4.8,
      reviewCount: 412,
    },
    services: [
      { name: "City hatchback", priceMajor: 39, currency: "EUR", model: "unit_selection" },
      { name: "SUV & 4x4", priceMajor: 79, currency: "EUR", model: "unit_selection" },
      { name: "Convertible", priceMajor: 95, currency: "EUR", model: "unit_selection" },
    ],
  },
  hotels: {
    id: "hotels",
    label: "Hotel Rooms",
    providerNoun: "Hotel",
    providerNounPlural: "Hotels",
    serviceNoun: "Room type",
    serviceNounPlural: "Room types",
    resourceNoun: "Room",
    resourceNounPlural: "Rooms",
    bookingVerb: "Book",
    partyNoun: "guests",
    categories: [
      { id: "standard", label: "Standard" },
      { id: "deluxe", label: "Deluxe" },
      { id: "suite", label: "Suite" },
      { id: "family", label: "Family" },
      { id: "sea", label: "Sea view" },
    ],
    searchPlaceholder: "Search hotels",
    business: {
      name: "Azure Bay Hotel",
      tagline: "Sea-view rooms, slow mornings",
      bio: "A boutique seafront hotel with sunlit rooms, an infinity pool and breakfast on the terrace. Walk to the old town in ten minutes and the beach in two.",
      city: "Palma",
      rating: 4.7,
      reviewCount: 968,
    },
    services: [
      { name: "Standard double", priceMajor: 120, currency: "EUR", model: "unit_selection" },
      { name: "Deluxe sea view", priceMajor: 190, currency: "EUR", model: "unit_selection" },
      { name: "Family suite", priceMajor: 260, currency: "EUR", model: "shared_capacity" },
    ],
  },
  venues: {
    id: "venues",
    label: "Venue Hire",
    providerNoun: "Venue",
    providerNounPlural: "Venues",
    serviceNoun: "Space",
    serviceNounPlural: "Spaces",
    resourceNoun: "Hall",
    resourceNounPlural: "Halls",
    bookingVerb: "Book",
    partyNoun: "guests",
    categories: [
      { id: "wedding", label: "Weddings" },
      { id: "conference", label: "Conference" },
      { id: "party", label: "Parties" },
      { id: "studio", label: "Studio" },
      { id: "rooftop", label: "Rooftop" },
    ],
    searchPlaceholder: "Search venues",
    business: {
      name: "The Glasshouse",
      tagline: "Light-filled spaces for any event",
      bio: "A converted warehouse of light-filled event spaces — weddings, launches, conferences and parties. In-house sound, staging and a rooftop with a skyline view.",
      city: "Lisbon",
      rating: 4.9,
      reviewCount: 233,
    },
    services: [
      { name: "Rooftop terrace", priceMajor: 900, currency: "EUR", model: "one_to_one" },
      { name: "Main hall", priceMajor: 1500, currency: "EUR", model: "one_to_one" },
      { name: "Studio loft", priceMajor: 450, currency: "EUR", model: "one_to_one" },
    ],
  },
  catering: {
    id: "catering",
    label: "Catering",
    providerNoun: "Caterer",
    providerNounPlural: "Caterers",
    serviceNoun: "Menu",
    serviceNounPlural: "Menus",
    resourceNoun: "Package",
    resourceNounPlural: "Packages",
    bookingVerb: "Order",
    partyNoun: "guests",
    categories: [
      { id: "canape", label: "Canapés" },
      { id: "buffet", label: "Buffet" },
      { id: "plated", label: "Plated" },
      { id: "bbq", label: "BBQ" },
      { id: "vegan", label: "Vegan" },
    ],
    searchPlaceholder: "Search caterers",
    business: {
      name: "Saffron & Sage",
      tagline: "Seasonal menus, beautifully served",
      bio: "Event catering built around the season — canapés, plated dinners and grazing tables made from local produce. Full service, from tasting to the last plate cleared.",
      city: "Barcelona",
      rating: 4.8,
      reviewCount: 187,
    },
    services: [
      { name: "Canapé reception", priceMajor: 28, currency: "EUR", model: "shared_capacity" },
      { name: "Plated three-course", priceMajor: 55, currency: "EUR", model: "shared_capacity" },
      { name: "Grazing buffet", priceMajor: 34, currency: "EUR", model: "shared_capacity" },
    ],
  },
  equipment: {
    id: "equipment",
    label: "Equipment Hire",
    providerNoun: "Rental depot",
    providerNounPlural: "Rental depots",
    serviceNoun: "Equipment class",
    serviceNounPlural: "Equipment classes",
    resourceNoun: "Item",
    resourceNounPlural: "Items",
    bookingVerb: "Hire",
    partyNoun: null,
    categories: [
      { id: "power", label: "Power tools" },
      { id: "access", label: "Access" },
      { id: "garden", label: "Garden" },
      { id: "event", label: "Event" },
      { id: "camera", label: "Camera" },
    ],
    searchPlaceholder: "Search hire depots",
    business: {
      name: "GearShed Hire",
      tagline: "Pro kit, ready when you are",
      bio: "Tools and equipment for trade and home — drills, mixers, access towers and event gear, all serviced and ready. Same-day collection or we deliver to site.",
      city: "Manchester",
      rating: 4.6,
      reviewCount: 341,
    },
    services: [
      { name: "Power tools", priceMajor: 25, currency: "GBP", model: "unit_selection" },
      { name: "Access towers", priceMajor: 60, currency: "GBP", model: "unit_selection" },
      { name: "Event gear", priceMajor: 45, currency: "GBP", model: "unit_selection" },
    ],
  },
  services: {
    id: "services",
    label: "Services",
    providerNoun: "Service provider",
    providerNounPlural: "Service providers",
    serviceNoun: "Service",
    serviceNounPlural: "Services",
    resourceNoun: "Specialist",
    resourceNounPlural: "Specialists",
    bookingVerb: "Book",
    partyNoun: null,
    categories: [
      { id: "hair", label: "Hair" },
      { id: "beauty", label: "Beauty" },
      { id: "massage", label: "Massage" },
      { id: "nails", label: "Nails" },
      { id: "spa", label: "Spa" },
    ],
    searchPlaceholder: "Search services",
    business: {
      name: "Lumen Studio",
      tagline: "Your best look, every visit",
      bio: "A calm studio for hair, beauty and massage — unhurried appointments, senior stylists and products we actually believe in. Walk out feeling like yourself, amplified.",
      city: "Amsterdam",
      rating: 4.9,
      reviewCount: 604,
    },
    services: [
      { name: "Cut & finish", priceMajor: 55, currency: "EUR", model: "one_to_one" },
      { name: "Colour", priceMajor: 110, currency: "EUR", model: "one_to_one" },
      { name: "Massage (60 min)", priceMajor: 80, currency: "EUR", model: "one_to_one" },
    ],
  },
  trades: {
    id: "trades",
    label: "Tradespeople",
    providerNoun: "Trade business",
    providerNounPlural: "Trade businesses",
    serviceNoun: "Job type",
    serviceNounPlural: "Job types",
    resourceNoun: "Tradesperson",
    resourceNounPlural: "Tradespeople",
    bookingVerb: "Book",
    partyNoun: null,
    categories: [
      { id: "plumbing", label: "Plumbing" },
      { id: "electrical", label: "Electrical" },
      { id: "carpentry", label: "Carpentry" },
      { id: "painting", label: "Painting" },
      { id: "roofing", label: "Roofing" },
    ],
    searchPlaceholder: "Search tradespeople",
    business: {
      name: "Meridian Trades",
      tagline: "Reliable work, done right",
      bio: "A trusted team of plumbers, electricians and carpenters. Clear quotes, tidy work and jobs finished when we say. Emergency call-outs available across the city.",
      city: "Dublin",
      rating: 4.8,
      reviewCount: 512,
    },
    services: [
      { name: "Plumbing call-out", priceMajor: 90, currency: "EUR", model: "one_to_one" },
      { name: "Electrical work", priceMajor: 110, currency: "EUR", model: "one_to_one" },
      { name: "Carpentry", priceMajor: 85, currency: "EUR", model: "one_to_one" },
    ],
  },
  cleaning: {
    id: "cleaning",
    label: "Cleaning",
    providerNoun: "Cleaning company",
    providerNounPlural: "Cleaning companies",
    serviceNoun: "Cleaning plan",
    serviceNounPlural: "Cleaning plans",
    resourceNoun: "Cleaner",
    resourceNounPlural: "Cleaners",
    bookingVerb: "Book",
    partyNoun: null,
    categories: [
      { id: "home", label: "Home" },
      { id: "deep", label: "Deep clean" },
      { id: "office", label: "Office" },
      { id: "endtenancy", label: "End of tenancy" },
      { id: "windows", label: "Windows" },
    ],
    searchPlaceholder: "Search cleaners",
    business: {
      name: "FreshNest Cleaning",
      tagline: "Come home to spotless",
      bio: "Vetted, insured cleaners for homes and offices — regular visits, deep cleans and end-of-tenancy. Same trusted cleaner each time, eco products as standard.",
      city: "London",
      rating: 4.7,
      reviewCount: 789,
    },
    services: [
      { name: "Home clean (weekly)", priceMajor: 45, currency: "GBP", model: "one_to_one" },
      { name: "Deep clean", priceMajor: 130, currency: "GBP", model: "one_to_one" },
      { name: "End of tenancy", priceMajor: 180, currency: "GBP", model: "one_to_one" },
    ],
  },
  tutors: {
    id: "tutors",
    label: "Tutors",
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
    business: {
      name: "Bright Minds Tutoring",
      tagline: "Real progress, one lesson at a time",
      bio: "Certified tutors helping adults and students reach real goals — from spoken Spanish to exam prep. Structured plans, patient coaching, online or in person.",
      city: "Barcelona",
      rating: 4.9,
      reviewCount: 274,
    },
    services: [
      { name: "Spanish for adults", priceMajor: 30, currency: "EUR", model: "one_to_one" },
      { name: "Maths & sciences", priceMajor: 35, currency: "EUR", model: "one_to_one" },
      { name: "Exam prep", priceMajor: 40, currency: "EUR", model: "one_to_one" },
    ],
  },
  consulting: {
    id: "consulting",
    label: "Consulting",
    providerNoun: "Consultancy",
    providerNounPlural: "Consultancies",
    serviceNoun: "Engagement",
    serviceNounPlural: "Engagements",
    resourceNoun: "Consultant",
    resourceNounPlural: "Consultants",
    bookingVerb: "Book",
    partyNoun: null,
    categories: [
      { id: "strategy", label: "Strategy" },
      { id: "finance", label: "Finance" },
      { id: "marketing", label: "Marketing" },
      { id: "product", label: "Product" },
      { id: "legal", label: "Legal" },
    ],
    searchPlaceholder: "Search consultants",
    business: {
      name: "Northpoint Advisory",
      tagline: "Clarity for your next move",
      bio: "Independent advisors in strategy, finance and product. We embed with your team, cut through the noise and leave you with decisions you can act on — not a slide deck.",
      city: "Berlin",
      rating: 4.8,
      reviewCount: 146,
    },
    services: [
      { name: "Strategy session", priceMajor: 220, currency: "EUR", model: "one_to_one" },
      { name: "Finance review", priceMajor: 180, currency: "EUR", model: "one_to_one" },
      { name: "Product audit", priceMajor: 200, currency: "EUR", model: "one_to_one" },
    ],
  },
};

export const USE_CASE_IDS: UseCaseId[] = [
  "cars",
  "hotels",
  "venues",
  "catering",
  "equipment",
  "services",
  "trades",
  "cleaning",
  "tutors",
  "consulting",
];

export const DEFAULT_USE_CASE: UseCaseId = "cars";

export function getUseCase(id: UseCaseId): UseCase {
  return USE_CASES[id] ?? USE_CASES[DEFAULT_USE_CASE];
}

export function isUseCaseId(v: string | null | undefined): v is UseCaseId {
  return !!v && v in USE_CASES;
}
