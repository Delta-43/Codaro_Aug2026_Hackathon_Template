import type { MockStore } from "@/api/storeTypes";
import { assembleStore, type VerticalSeedConfig } from "@/api/seed/common";

/**
 * Group vertical: a single resource, capacity > 1, fixed sessions. Mapped to
 * the `shared_capacity` booking model — the user picks a party size capped at
 * the session's remaining capacity. A handful of 60-minute sessions per day,
 * every day.
 */

// A handful of sessions per day (07:00, 09:00, 12:00, 17:00, 18:30).
const SESSIONS = [
  { hour: 7, minute: 0 },
  { hour: 9, minute: 0 },
  { hour: 12, minute: 0 },
  { hour: 17, minute: 0 },
  { hour: 18, minute: 30 },
];

const config: VerticalSeedConfig = {
  verticalId: "group",
  bookingModel: "shared_capacity",
  currency: "EUR",
  baseTz: "Europe/Warsaw",
  categories: [
    { id: "vinyasa", label: "Vinyasa" },
    { id: "hatha", label: "Hatha" },
    { id: "pilates", label: "Pilates" },
    { id: "meditation", label: "Meditation" },
    { id: "strength", label: "Strength" },
  ],
  providers: [
    {
      name: "Lotus Studio",
      tagline: "Breathe, move, reset",
      bio: "A light-filled studio in the old town offering daily classes for every level. Mats and props provided; walk-ins welcome when space allows.",
      categoryId: "vinyasa",
      city: "Warsaw",
      country: "Poland",
      lat: 52.2297,
      lng: 21.0122,
      publicCode: "LOTUS-5150",
      rating: 4.9,
      reviewCount: 402,
      links: [
        { label: "Website", url: "https://example.com/lotus" },
        { label: "Timetable", url: "https://example.com/lotus/timetable" },
      ],
    },
    {
      name: "Riverside Yoga",
      tagline: "Hatha by the Vistula",
      bio: "Slow, alignment-focused classes suitable for beginners.",
      categoryId: "hatha",
      city: "Kraków",
      country: "Poland",
      lat: 50.0647,
      lng: 19.945,
      publicCode: "RIVER-3380",
      rating: 4.6,
      reviewCount: 176,
    },
    {
      name: "Core Pilates Lab",
      tagline: "Reformer & mat",
      bio: "Small-group Pilates focused on strength and posture.",
      categoryId: "pilates",
      city: "Gdańsk",
      country: "Poland",
      lat: 54.352,
      lng: 18.6466,
      publicCode: "CORE-9925",
      rating: 4.7,
      reviewCount: 133,
    },
    {
      name: "Still Point",
      tagline: "Guided meditation",
      bio: "Drop-in mindfulness and breathwork sessions.",
      categoryId: "meditation",
      city: "Wrocław",
      country: "Poland",
      lat: 51.1079,
      lng: 17.0385,
      publicCode: "STILL-2044",
      rating: 4.8,
      reviewCount: 98,
    },
    {
      name: "Forge Strength",
      tagline: "Small-group conditioning",
      bio: "Coached strength circuits, capped at twelve per session.",
      categoryId: "strength",
      city: "Poznań",
      country: "Poland",
      lat: 52.4064,
      lng: 16.9252,
      publicCode: "FORGE-6710",
      rating: 4.5,
      reviewCount: 71,
    },
    {
      name: "Sunrise Vinyasa",
      tagline: "Morning flows",
      bio: "Energetic dawn classes to start the day.",
      categoryId: "vinyasa",
      city: "Kraków",
      country: "Poland",
      lat: 50.0619,
      lng: 19.9368,
      publicCode: "SUNRISE-4416",
      rating: 4.7,
      reviewCount: 154,
    },
  ],
  demoServices: [
    {
      name: "Vinyasa Flow",
      description: "A dynamic, breath-led flow for all levels.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 1,
      priceMinorUnits: 1800,
      cancellationCutoffHours: 12,
      grid: { daysBack: 28, daysForward: 56, startTimes: SESSIONS },
      resources: [
        {
          name: "Studio A",
          description: "Main room, sprung floor, 12 mats.",
          capacity: 12,
          attributes: [
            { label: "Capacity", value: "12 spots" },
            { label: "Level", value: "All levels" },
            { label: "Heated", value: "No" },
          ],
        },
      ],
    },
    {
      name: "Hatha Basics",
      description: "Slower, alignment-focused practice for beginners.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 1,
      priceMinorUnits: 1600,
      cancellationCutoffHours: 12,
      grid: { daysBack: 28, daysForward: 56, startTimes: SESSIONS.slice(0, 3) },
      resources: [
        {
          name: "Studio B",
          description: "Quiet room, 10 mats.",
          capacity: 10,
          attributes: [
            { label: "Capacity", value: "10 spots" },
            { label: "Level", value: "Beginner" },
            { label: "Heated", value: "No" },
          ],
        },
      ],
    },
    {
      name: "Candlelight Meditation",
      description: "A restorative evening wind-down.",
      slotDurationMinutes: 60,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: 1,
      priceMinorUnits: 1400,
      cancellationCutoffHours: 12,
      grid: { daysBack: 28, daysForward: 56, startTimes: [{ hour: 20, minute: 0 }] },
      resources: [
        {
          name: "Studio A",
          description: "Main room, dimmed, bolsters provided.",
          capacity: 16,
          attributes: [
            { label: "Capacity", value: "16 spots" },
            { label: "Level", value: "All levels" },
            { label: "Props", value: "Provided" },
          ],
        },
      ],
    },
  ],
  simpleService: {
    name: "Open class",
    description: "A drop-in group session for every level.",
    slotDurationMinutes: 60,
    minSlotsPerBooking: 1,
    maxSlotsPerBooking: 1,
    priceMinorUnits: 1500,
    cancellationCutoffHours: 12,
    grid: { daysBack: 7, daysForward: 42, startTimes: SESSIONS.slice(0, 3) },
    resource: {
      name: "Main room",
      description: "Shared studio space.",
      capacity: 12,
      attributes: [
        { label: "Capacity", value: "12 spots" },
        { label: "Level", value: "All levels" },
      ],
    },
  },
};

export function seedGroup(): MockStore {
  return assembleStore(config);
}
