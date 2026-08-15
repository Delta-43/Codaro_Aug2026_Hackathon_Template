/**
 * Distance for search results. The mock user has no coordinates, so we measure
 * from a fixed reference (the demo's home city). Swap for the real user
 * location when geolocation is wired.
 */
export const REFERENCE_LOCATION = { city: "Warsaw", lat: 52.2297, lng: 21.0122 };

type Point = { lat: number; lng: number };

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

export function formatDistance(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}

/** Distance from the reference location to a point, pre-formatted. */
export function distanceFromHome(point: Point): string {
  return formatDistance(distanceKm(REFERENCE_LOCATION, point));
}
