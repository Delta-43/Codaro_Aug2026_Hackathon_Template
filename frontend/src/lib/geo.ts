/**
 * Distance for search results.
 *
 * The origin used to be a hardcoded Warsaw constant, which meant every user
 * anywhere saw distances measured from the demo's home city — and a pivot to a
 * business in another country had no way to correct it. It now comes from the
 * pivot file (`location.origin` / `location.distanceUnit`), applied once at app
 * boot by `AppProvider`. The Warsaw values remain the fallback so the app still
 * renders if `/config` is unreachable.
 *
 * Swap the origin for the real device location when geolocation is wired — this
 * is the one place that would need to change.
 */
export type Point = { lat: number; lng: number };
export type DistanceUnit = "km" | "mi";

const DEFAULT_ORIGIN = { city: "Warsaw", lat: 52.2297, lng: 21.0122 };
const KM_PER_MILE = 1.609344;

let origin: Point & { city?: string } = DEFAULT_ORIGIN;
let unit: DistanceUnit = "km";

/** Apply the pivot file's location settings. Called once at boot; partial
 *  input leaves the untouched field at its current value. */
export function setGeoSettings(next: {
  origin?: (Point & { city?: string }) | null;
  distanceUnit?: DistanceUnit | null;
}): void {
  if (next.origin && Number.isFinite(next.origin.lat) && Number.isFinite(next.origin.lng)) {
    origin = next.origin;
  }
  if (next.distanceUnit === "km" || next.distanceUnit === "mi") unit = next.distanceUnit;
}

/** The point distances are measured from. */
export function geoOrigin(): Point & { city?: string } {
  return origin;
}

export function distanceUnit(): DistanceUnit {
  return unit;
}

const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Great-circle distance in kilometres (haversine). */
export function distanceKm(a: Point, b: Point): number {
  const R = 6371;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Format a kilometre distance in the configured unit. */
export function formatDistance(km: number): string {
  if (unit === "mi") {
    const mi = km / KM_PER_MILE;
    if (mi < 0.1) return `${Math.round(mi * 5280)} ft`;
    if (mi < 10) return `${mi.toFixed(1)} mi`;
    return `${Math.round(mi)} mi`;
  }
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}

/** Distance from the configured origin to a point, pre-formatted. */
export function distanceFromHome(point: Point): string {
  return formatDistance(distanceKm(geoOrigin(), point));
}
