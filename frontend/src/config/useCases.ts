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

export interface UseCaseService {
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
  /** Unit word for the "upcoming bookings" metric, e.g. "rentals" / "stays". */
  bookingUnit: string;
  /** On-brand profile-picture scene key (see business-art.tsx). */
  profileScene: string;
  /** Gallery/video scene keys, cycled for showcase media. */
  scenes: string[];
  /** The showcase business shown across business mode in this niche. */
  business: { name: string; tagline: string; bio: string; city: string; rating: number; reviewCount: number };
  services: UseCaseService[];
  clientNames: string[];
  requestNotes: string[];
  reviewLines: string[];
  galleryTitles: string[];
  videoTitles: string[];
  social: { label: string; handle: string; url: string }[];
}

const CLIENTS_A = ["Barbara Nowak", "Liam O'Connor", "Sofia Marin", "Marco Rossi", "Amara Diallo", "Tom Fischer"];
const CLIENTS_B = ["Elena Petrova", "Josh Bennett", "Aisha Khan", "Diego Alvarez", "Yuki Tanaka", "Nora Haddad"];
const CLIENTS_C = ["Priya Sharma", "Hannah Lee", "Mateo Silva", "Olga Ivanova", "Sam Wright", "Lucia Romano"];

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
    bookingUnit: "rentals",
    profileScene: "car-hero",
    scenes: ["car-hero", "car-offroad", "car-convertible", "car-city", "car-night", "car-buggy"],
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
    clientNames: CLIENTS_A,
    requestNotes: [
      "wants the Jeep for the whole weekend",
      "asking about airport pickup on the convertible",
      "needs a 7-seater for a family trip",
      "first-time renter — long weekend in the hills",
    ],
    reviewLines: [
      "Spotless car, effortless pickup. Made our trip.",
      "The 4x4 handled the trails like a dream — will book again.",
      "Best rates on the island and the convertible was immaculate.",
    ],
    galleryTitles: ["Porsche in the mountains", "Extreme 4x4 off-road", "Sunset convertible cruise", "Family hatchback tour", "Beach buggy day", "Night drive through town"],
    videoTitles: ["Driving in the mountains", "4x4 off-road in Ibiza", "How keyless pickup works", "Convertible sunset review", "A day with the buggy"],
    social: [
      { label: "Instagram", handle: "@ibiza.car.rentals", url: "https://instagram.com" },
      { label: "TikTok", handle: "@ibizacars", url: "https://tiktok.com" },
      { label: "Website", handle: "ibizacarrentals.example", url: "https://example.com" },
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
    bookingUnit: "stays",
    profileScene: "hotel-hero",
    scenes: ["hotel-hero", "hotel-room", "grad-teal", "hotel-hero", "grad-amber", "hotel-room"],
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
    clientNames: CLIENTS_B,
    requestNotes: [
      "wants a late checkout on the sea-view room",
      "asking about a cot for the family suite",
      "honeymoon stay — any upgrades?",
      "three nights, early check-in possible?",
    ],
    reviewLines: [
      "Woke up to the sea every morning — unforgettable.",
      "Immaculate rooms and the warmest staff.",
      "Breakfast on the terrace alone is worth the stay.",
    ],
    galleryTitles: ["Infinity pool at sunset", "Sea-view suite", "Terrace breakfast", "Lobby & lounge", "Golden hour balcony", "Deluxe room"],
    videoTitles: ["A tour of the sea-view suite", "Mornings at Azure Bay", "The rooftop pool", "Breakfast on the terrace", "Around the neighbourhood"],
    social: [
      { label: "Instagram", handle: "@azurebayhotel", url: "https://instagram.com" },
      { label: "Website", handle: "azurebay.example", url: "https://example.com" },
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
    bookingUnit: "events",
    profileScene: "venue-hero",
    scenes: ["venue-hero", "venue-stage", "grad-rose", "venue-hero", "grad-teal", "venue-stage"],
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
    clientNames: CLIENTS_C,
    requestNotes: [
      "150-guest wedding, needs the main hall",
      "product launch with in-house sound",
      "asking about rooftop availability in June",
      "corporate offsite for 80 people",
    ],
    reviewLines: [
      "Our wedding looked magical in that light.",
      "Seamless from planning to pack-down.",
      "The rooftop stole the show at our launch.",
    ],
    galleryTitles: ["Rooftop at dusk", "Main hall set for a wedding", "Launch night lights", "Studio loft", "Skyline terrace", "Conference layout"],
    videoTitles: ["A wedding at The Glasshouse", "Rooftop walkthrough", "Setting the main hall", "Launch night highlights", "Meet the events team"],
    social: [
      { label: "Instagram", handle: "@theglasshouse", url: "https://instagram.com" },
      { label: "Website", handle: "glasshouse.example", url: "https://example.com" },
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
    bookingUnit: "events",
    profileScene: "catering-hero",
    scenes: ["catering-hero", "catering-table", "grad-amber", "catering-hero", "grad-rose", "catering-table"],
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
    clientNames: CLIENTS_A,
    requestNotes: [
      "plated dinner for 60, two vegan tables",
      "canapés for a gallery opening",
      "asking about a tasting next week",
      "BBQ buffet for a summer party",
    ],
    reviewLines: [
      "Every plate was a moment. Guests still talk about it.",
      "Flawless service and genuinely delicious.",
      "Handled our dietary needs without a hitch.",
    ],
    galleryTitles: ["Plated main course", "Grazing table", "Canapé tray", "Dessert selection", "Chef at the pass", "Table setting"],
    videoTitles: ["Behind a plated dinner", "Building a grazing table", "A tasting session", "Canapés, close up", "Meet the kitchen"],
    social: [
      { label: "Instagram", handle: "@saffronandsage", url: "https://instagram.com" },
      { label: "Website", handle: "saffronsage.example", url: "https://example.com" },
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
    bookingUnit: "hires",
    profileScene: "equipment-hero",
    scenes: ["equipment-hero", "equipment-drill", "grad-amber", "equipment-hero", "grad-teal", "equipment-drill"],
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
    clientNames: CLIENTS_B,
    requestNotes: [
      "needs a breaker for the weekend",
      "asking about delivery to a site on Friday",
      "access tower for a two-day job",
      "PA system for a small event",
    ],
    reviewLines: [
      "Kit was spotless and ready on time.",
      "Saved my job — same-day delivery to site.",
      "Fair prices and genuinely helpful staff.",
    ],
    galleryTitles: ["Tool wall", "Access tower on site", "Event PA rig", "Serviced generators", "Ready for collection", "Camera kit"],
    videoTitles: ["How delivery works", "Setting up an access tower", "Our servicing process", "Event gear rundown", "Same-day collection"],
    social: [
      { label: "Instagram", handle: "@gearshedhire", url: "https://instagram.com" },
      { label: "Website", handle: "gearshed.example", url: "https://example.com" },
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
    bookingUnit: "appointments",
    profileScene: "services-hero",
    scenes: ["services-hero", "grad-rose", "grad-teal", "services-hero", "grad-amber", "grad-rose"],
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
    clientNames: CLIENTS_C,
    requestNotes: [
      "wants a full colour before the weekend",
      "asking for a senior stylist",
      "first massage — any advice?",
      "cut & finish, prefers mornings",
    ],
    reviewLines: [
      "Best cut I've had in years. Genuinely listened.",
      "The studio is calm and the work is flawless.",
      "Left glowing — booked my next three visits.",
    ],
    galleryTitles: ["Fresh colour", "The studio", "Styling chair", "Before & after", "Product shelf", "Calm treatment room"],
    videoTitles: ["A colour transformation", "Inside the studio", "Our styling approach", "A massage session", "Meet the team"],
    social: [
      { label: "Instagram", handle: "@lumenstudio", url: "https://instagram.com" },
      { label: "Website", handle: "lumenstudio.example", url: "https://example.com" },
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
    bookingUnit: "jobs",
    profileScene: "trades-hero",
    scenes: ["trades-hero", "trades-tools", "grad-amber", "trades-hero", "grad-teal", "trades-tools"],
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
    clientNames: CLIENTS_A,
    requestNotes: [
      "leaking radiator, needs someone this week",
      "asking for a quote on rewiring a room",
      "fitted wardrobe build",
      "emergency call-out for a blocked drain",
    ],
    reviewLines: [
      "On time, tidy and fixed it first visit.",
      "Clear quote and no surprises. Rare these days.",
      "Saved us in an emergency — highly recommend.",
    ],
    galleryTitles: ["Finished bathroom fit", "Tidy consumer unit", "Built-in wardrobe", "On the job", "Before & after", "The van kit"],
    videoTitles: ["A bathroom refit", "How we quote", "Emergency call-out", "Carpentry in progress", "Meet the team"],
    social: [
      { label: "Instagram", handle: "@meridiantrades", url: "https://instagram.com" },
      { label: "Website", handle: "meridiantrades.example", url: "https://example.com" },
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
    bookingUnit: "cleans",
    profileScene: "cleaning-hero",
    scenes: ["cleaning-hero", "cleaning-spray", "grad-teal", "cleaning-hero", "grad-rose", "cleaning-spray"],
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
    clientNames: CLIENTS_B,
    requestNotes: [
      "weekly clean, prefers the same cleaner",
      "end-of-tenancy before Saturday",
      "asking about eco products",
      "one-off deep clean after a party",
    ],
    reviewLines: [
      "Spotless every time and always on schedule.",
      "Got my full deposit back after the tenancy clean.",
      "Trustworthy and thorough — a real relief.",
    ],
    galleryTitles: ["Spotless kitchen", "Deep-cleaned bathroom", "Fresh living room", "Office ready for Monday", "Streak-free windows", "Eco kit"],
    videoTitles: ["A weekly clean, sped up", "Our deep-clean checklist", "End-of-tenancy walkthrough", "The eco products we use", "Meet your cleaner"],
    social: [
      { label: "Instagram", handle: "@freshnestclean", url: "https://instagram.com" },
      { label: "Website", handle: "freshnest.example", url: "https://example.com" },
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
    bookingUnit: "lessons",
    profileScene: "tutor-hero",
    scenes: ["tutor-hero", "tutor-flag", "tutor-board", "tutor-online", "tutor-cap", "tutor-books"],
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
    clientNames: CLIENTS_C,
    requestNotes: [
      "wants weekly Spanish taught in English",
      "GCSE maths, twice a week before exams",
      "conversational practice for a work move",
      "beginner coding for their teenager",
    ],
    reviewLines: [
      "My Spanish went from zero to conversations in months.",
      "Patient, structured and genuinely encouraging.",
      "My daughter's grades jumped a full band before exams.",
    ],
    galleryTitles: ["Whiteboard problem-solving", "Exam coaching", "Conversation practice", "Student success wall", "Study plans", "Online lesson setup"],
    videoTitles: ["How lessons are structured", "A student's turnaround", "5 tips for spoken Spanish", "Inside an online session", "Building a study plan"],
    social: [
      { label: "Instagram", handle: "@brightmindstutoring", url: "https://instagram.com" },
      { label: "YouTube", handle: "@brightmindsteach", url: "https://youtube.com" },
      { label: "Website", handle: "brightminds.example", url: "https://example.com" },
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
    bookingUnit: "sessions",
    profileScene: "consulting-hero",
    scenes: ["consulting-hero", "consulting-chart", "grad-teal", "consulting-hero", "grad-rose", "consulting-chart"],
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
    clientNames: CLIENTS_A,
    requestNotes: [
      "wants a strategy session before a raise",
      "asking about a finance review for Q3",
      "product audit for a new launch",
      "monthly advisory retainer?",
    ],
    reviewLines: [
      "Cut through months of indecision in one session.",
      "Practical, sharp and refreshingly honest.",
      "Left with a plan the whole team believed in.",
    ],
    galleryTitles: ["Strategy workshop", "The whiteboard wall", "Client offsite", "Data deep-dive", "Roadmap session", "The team"],
    videoTitles: ["How an engagement works", "A strategy session", "Reading your numbers", "Running an audit", "Meet the advisors"],
    social: [
      { label: "LinkedIn", handle: "Northpoint Advisory", url: "https://linkedin.com" },
      { label: "Website", handle: "northpoint.example", url: "https://example.com" },
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
