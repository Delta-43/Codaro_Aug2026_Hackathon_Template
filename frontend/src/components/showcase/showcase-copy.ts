/**
 * Content module for `/showcase` — the "morbid.com" brand voice. Everything
 * that reads as copy on the page (not layout, not data) lives here so the
 * layout/panel work happening in parallel can pull strings without owning
 * their wording.
 *
 * Nothing here fabricates service data: `getServiceTagline` only supplies an
 * optional extra line layered on top of the real `service.name` /
 * `service.description` / price the backend returns. Unrecognized names
 * resolve to `undefined` on purpose — new services need no copy update to
 * render correctly, they just render without an eyebrow line.
 */

export const BRAND_NAME = "morbid.com";

export const BRAND_TAGLINE = "Booking software for your final booking.";

export const HERO_TITLE = "Everything ends. Reserve your slot.";

export const HERO_SUBTITLE =
  "The full catalogue, live from the calendar. Same-day availability cannot be guaranteed — for obvious reasons, neither can next-day.";

export const EMPTY_STATE_TITLE = "Nothing on the books.";

export const EMPTY_STATE_BODY =
  "The catalogue is empty right now. Check back shortly — inventory here has a way of turning over.";

export const PAGE_META_TITLE = `Services — ${BRAND_NAME}`;

export const PAGE_META_DESCRIPTION =
  "The full service catalogue, live from the calendar. Traditional, discreet, orbital, and everything in between.";

/**
 * Curated eyebrow/subtitle copy, keyed by the real service name exactly as
 * seeded (`GET /services`). Deliberately a plain lookup, not a fuzzy match —
 * an unrecognized name (a future service, a renamed one) returns `undefined`
 * rather than guessing, so callers can skip the eyebrow line cleanly instead
 * of risking a mismatched joke on the wrong service.
 */
const SERVICE_TAGLINES: Record<string, string> = {
  "Traditional Funeral Service": "The classics never go out of style.",
  "Memorial Gathering": "No body, no problem.",
  "Direct Committal": "No fuss. No frills. No further questions.",
  "Nocturnal Aftercare Programme":
    "For light-sensitive families. We do not ask why.",
  "Orbital Committal": "Ashes to ashes, orbit to orbit.",
  "Burial": "Time-tested. Ground floor.",
  "Cremation": "Faster than burial. Lighter, too.",
  "Discreet Arrangement": "No questions asked. We mean that.",
  "Pre-Need Arrangement": "Plan ahead. You'll thank yourself later, briefly.",
  "Adjacent Plot Reservation": "Choose your neighbours wisely.",
  "Cryogenic Suspension": "See you when the technology catches up.",
};

export function getServiceTagline(serviceName: string): string | undefined {
  return SERVICE_TAGLINES[serviceName];
}
