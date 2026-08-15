import type { MockStore } from "@/api/storeTypes";
import { assembleStore, type VerticalSeedConfig } from "@/api/seed/common";

/**
 * One-to-one vertical: a single resource, capacity 1, hourly. Mapped to the
 * `one_to_one` booking model. Weekday working hours 09:00–17:00 with a 12:00
 * lunch gap (no weekend slots). maxSlotsPerBooking = 2 so two back-to-back
 * hours can be booked as one range.
 */

const WEEKDAYS = [1, 2, 3, 4, 5]; // Mon–Fri
// 09:00–17:00 hourly, lunch break at 12:00 (last start 16:00 → ends 17:00).
const WORK_HOURS = [9, 10, 11, 13, 14, 15, 16].map((hour) => ({ hour, minute: 0 }));

const config: VerticalSeedConfig = {
  verticalId: "oneToOne",
  bookingModel: "one_to_one",
  currency: "EUR",
  baseTz: "Europe/Warsaw",
  categories: [
    { id: "math", label: "Maths & sciences" },
    { id: "languages", label: "Languages" },
    { id: "music", label: "Music" },
    { id: "coding", label: "Coding" },
    { id: "exam", label: "Exam prep" },
  ],
  providers: [
    {
      name: "Northline Tutoring",
      tagline: "One-to-one, results-first",
      bio: "A small studio of specialist tutors covering STEM and languages. Sessions are hourly, in person near the centre or online.",
      categoryId: "math",
      city: "Warsaw",
      country: "Poland",
      lat: 52.2297,
      lng: 21.0122,
      publicCode: "NORTH-1180",
      rating: 4.9,
      reviewCount: 214,
      links: [{ label: "Website", url: "https://example.com/northline" }],
    },
    {
      name: "Verba Languages",
      tagline: "Conversational fluency",
      bio: "Native-speaker language coaching for adults and teens.",
      categoryId: "languages",
      city: "Kraków",
      country: "Poland",
      lat: 50.0647,
      lng: 19.945,
      publicCode: "VERBA-3320",
      rating: 4.7,
      reviewCount: 158,
    },
    {
      name: "Sono Music School",
      tagline: "Piano, guitar, voice",
      bio: "Instrument lessons for beginners through grade eight.",
      categoryId: "music",
      city: "Gdańsk",
      country: "Poland",
      lat: 54.352,
      lng: 18.6466,
      publicCode: "SONO-7745",
      rating: 4.8,
      reviewCount: 121,
    },
    {
      name: "Codeworks Mentors",
      tagline: "Learn to ship code",
      bio: "Practical programming mentorship in Python, JavaScript and SQL.",
      categoryId: "coding",
      city: "Wrocław",
      country: "Poland",
      lat: 51.1079,
      lng: 17.0385,
      publicCode: "CODE-2091",
      rating: 4.6,
      reviewCount: 89,
    },
    {
      name: "Apex Exam Prep",
      tagline: "SAT · IB · Matura",
      bio: "Targeted revision and mock exams with detailed feedback.",
      categoryId: "exam",
      city: "Poznań",
      country: "Poland",
      lat: 52.4064,
      lng: 16.9252,
      publicCode: "APEX-6612",
      rating: 4.8,
      reviewCount: 143,
    },
    {
      name: "Helix STEM",
      tagline: "Maths, physics, chemistry",
      bio: "University-level tutors for demanding science coursework.",
      categoryId: "math",
      city: "Kraków",
      country: "Poland",
      lat: 50.0619,
      lng: 19.9368,
      publicCode: "HELIX-4408",
      rating: 4.5,
      reviewCount: 67,
    },
  ],
  demoServices: [
    {
      name: "Mathematics",
      description: "Algebra, calculus and problem-solving with Ana.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 2,
      priceMinorUnits: 6000,
      cancellationCutoffHours: 24,
      grid: { daysBack: 28, daysForward: 56, weekdays: WEEKDAYS, startTimes: WORK_HOURS },
      resources: [
        {
          name: "Ana Ruiz",
          description: "PhD in applied mathematics, 8 years tutoring.",
          capacity: 1,
          attributes: [
            { label: "Levels", value: "GCSE → University" },
            { label: "Format", value: "In person or online" },
            { label: "Languages", value: "English, Polish" },
          ],
        },
      ],
    },
    {
      name: "Physics",
      description: "Mechanics, electromagnetism and lab report coaching.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 2,
      priceMinorUnits: 6500,
      cancellationCutoffHours: 24,
      grid: { daysBack: 28, daysForward: 56, weekdays: WEEKDAYS, startTimes: WORK_HOURS },
      resources: [
        {
          name: "Jon Vekic",
          description: "MSc physics, examiner for the national board.",
          capacity: 1,
          attributes: [
            { label: "Levels", value: "A-level → University" },
            { label: "Format", value: "Online" },
            { label: "Languages", value: "English" },
          ],
        },
      ],
    },
    {
      name: "Exam prep",
      description: "Structured revision with weekly mock papers.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 2,
      priceMinorUnits: 7000,
      cancellationCutoffHours: 24,
      grid: { daysBack: 28, daysForward: 56, weekdays: WEEKDAYS, startTimes: WORK_HOURS },
      resources: [
        {
          name: "Priya Nair",
          description: "Specialist in Matura and IB mathematics.",
          capacity: 1,
          attributes: [
            { label: "Focus", value: "Matura, IB" },
            { label: "Format", value: "In person or online" },
            { label: "Languages", value: "English, Polish" },
          ],
        },
      ],
    },
  ],
  simpleService: {
    name: "Introductory lesson",
    description: "A first hour to assess level and set a plan.",
    slotDurationMinutes: 60,
    minSlotsPerBooking: 1,
    maxSlotsPerBooking: 1,
    priceMinorUnits: 5000,
    cancellationCutoffHours: 24,
    grid: { daysBack: 7, daysForward: 42, weekdays: WEEKDAYS, startTimes: WORK_HOURS },
    resource: {
      name: "Lead tutor",
      description: "Assigned on booking.",
      capacity: 1,
      attributes: [
        { label: "Format", value: "In person or online" },
        { label: "Duration", value: "60 min" },
      ],
    },
  },
};

export function seedOneToOne(): MockStore {
  return assembleStore(config);
}
