import type { ServiceAnimationComponent } from "./service-animation-contract";
import { OrbitalCommittalAnimation } from "./orbital-committal";
import { MemorialGatheringAnimation } from "./memorial-gathering";
import { TraditionalFuneralServiceAnimation } from "./traditional-funeral-service";
import { DiscreetArrangementAnimation } from "./discreet-arrangement";
import { PreNeedArrangementAnimation } from "./pre-need-arrangement";
import { CremationAnimation } from "./cremation";
import { CryogenicSuspensionAnimation } from "./cryogenic-suspension";
import { BurialAnimation } from "./burial";
import { NocturnalAftercareAnimation } from "./nocturnal-aftercare-programme";
import { AdjacentPlotReservationAnimation } from "./adjacent-plot-reservation";
import { DirectCommittalAnimation } from "./direct-committal";

export type { ServiceAnimationComponent } from "./service-animation-contract";

/**
 * Exact-name lookup, keyed to the real seeded catalogue (`GET /services`).
 * Each service now gets a bespoke animation authored from its own
 * description, rather than a shared taxonomy of reusable "kinds" — the
 * generic creature-icon system this replaced is gone.
 */
const SERVICE_ANIMATIONS: Record<string, ServiceAnimationComponent> = {
  "Orbital Committal": OrbitalCommittalAnimation,
  "Memorial Gathering": MemorialGatheringAnimation,
  "Traditional Funeral Service": TraditionalFuneralServiceAnimation,
  "Discreet Arrangement": DiscreetArrangementAnimation,
  "Pre-Need Arrangement": PreNeedArrangementAnimation,
  "Cremation": CremationAnimation,
  "Cryogenic Suspension": CryogenicSuspensionAnimation,
  "Burial": BurialAnimation,
  "Nocturnal Aftercare Programme": NocturnalAftercareAnimation,
  "Adjacent Plot Reservation": AdjacentPlotReservationAnimation,
  "Direct Committal": DirectCommittalAnimation,
};

/**
 * Fallback for any service name outside the curated set above (a future
 * addition to the catalogue, or a re-pivot) — the plain coffin from "Direct
 * Committal" doubles as a generic, tasteful default rather than leaving the
 * row without an animation.
 */
const DEFAULT_ANIMATION: ServiceAnimationComponent = DirectCommittalAnimation;

export function getServiceAnimation(serviceName: string): ServiceAnimationComponent {
  return SERVICE_ANIMATIONS[serviceName] ?? DEFAULT_ANIMATION;
}
