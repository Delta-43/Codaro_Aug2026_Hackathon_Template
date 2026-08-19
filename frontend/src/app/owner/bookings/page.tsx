"use client";

/**
 * Business tab 4 — Bookings. Calendar + list merged into one panel: every
 * approved (confirmed/completed) booking laid out across the three standard
 * views (month / week / day, week by default) on top, then an Upcoming / Past
 * list of the same feed below. Tapping either opens a booking for detail,
 * messaging the customer, and cancellation. The feed is real — /owner/calendar
 * across all the owner's resources; cancel hits /bookings/{id}.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, Star, Users } from "lucide-react";
import { useOwner } from "@/context/owner-context";
import { Skeleton } from "@/components/skeleton";
import { Modal } from "@/components/modal";
import { Button } from "@/components/ui/button";
import { BookingCalendar } from "@/components/business/booking-calendar";
import {
  cancelBooking,
  getOwnerCalendar,
  getOwnerServices,
  rateClient,
  startConversation,
  ApiError,
} from "@/api";
import type { OwnerBooking, OwnerServiceSummary } from "@/types/domain";
import type { DemoBooking } from "@/lib/business-demo";
import { ownerBookingToCal } from "@/lib/owner-view";
import { formatBookingWhen, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

type Scope = "upcoming" | "past";

const browserTz = () =>
  typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";

const STATUS_CLASS: Record<DemoBooking["status"], string> = {
  confirmed: "bg-primary/10 text-primary",
  completed: "bg-muted text-muted-foreground",
  pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export default function BookingsPage() {
  const { ready, vocab, capability } = useOwner();
  const router = useRouter();
  const tz = browserTz();
  const [raw, setRaw] = useState<OwnerBooking[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  // serviceId -> whether reviews are on for THAT service. The routers gate
  // `capability("reviews", service)` per service, so the global block is not
  // enough to decide whether this control would 404.
  const [reviewsByService, setReviewsByService] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<DemoBooking | null>(null);
  const [cancelled, setCancelled] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  // Past/upcoming pivot, frozen at mount so re-renders don't reshuffle the list.
  const [now] = useState(() => Date.now());
  const [messaging, setMessaging] = useState(false);
  const [scope, setScope] = useState<Scope>("upcoming");

  // Open (or resume) the thread with this booking's customer, then jump to it.
  async function messageClient() {
    const booking = raw.find((b) => b.id === selected?.id);
    if (!booking) return;
    setMessaging(true);
    try {
      const conv = await startConversation(booking.providerId, booking.userId);
      router.push(`/owner/messages/${conv.id}`);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Couldn't open that conversation.");
    } finally {
      setMessaging(false);
    }
  }

  useEffect(() => {
    let cancel = false;
    Promise.all([
      getOwnerCalendar().catch(() => [] as OwnerBooking[]),
      getOwnerServices().catch(() => [] as OwnerServiceSummary[]),
    ]).then(([bookings, services]) => {
      if (cancel) return;
      setRaw(bookings);
      setNames(Object.fromEntries(services.map((s) => [s.id, s.name])));
      setReviewsByService(
        Object.fromEntries(services.map((s) => [s.id, s.capabilities.reviews !== false])),
      );
      setLoading(false);
    });
    return () => {
      cancel = true;
    };
  }, []);

  // Prefer the per-service value; fall back to the global block for any service
  // the map does not cover. `getOwnerServices()` swallows its own failure, so
  // without the fallback a failed services call left the map empty and every
  // booking read as reviewable — showing a control the API then refuses.
  const reviewable = useMemo(
    () =>
      Object.fromEntries(
        raw.map((b) => [
          b.id,
          b.serviceId in reviewsByService ? reviewsByService[b.serviceId] : capability("reviews"),
        ]),
      ),
    [raw, reviewsByService, capability],
  );

  const live = useMemo(() => raw.filter((b) => !cancelled.has(b.id)), [raw, cancelled]);
  const bookings = useMemo(
    () => live.map((b) => ownerBookingToCal(b, names[b.serviceId])),
    [live, names],
  );

  // Split the same feed for the list below the calendar. Past = ended or
  // completed; upcoming = everything still ahead, soonest first.
  const listed = useMemo(() => {
    const rows = live
      .map((b) => ownerBookingToCal(b, names[b.serviceId]))
      .filter((b) =>
        scope === "past"
          ? b.status === "completed" || new Date(b.endUtc).getTime() < now
          : b.status !== "completed" && new Date(b.endUtc).getTime() >= now,
      );
    rows.sort((a, b) => {
      const da = new Date(a.startUtc).getTime();
      const db = new Date(b.startUtc).getTime();
      return scope === "past" ? db - da : da - db;
    });
    return rows;
  }, [live, names, scope, now]);

  async function doCancel(id: string) {
    setBusy(true);
    try {
      await cancelBooking(id);
      setCancelled((prev) => new Set(prev).add(id));
      setSelected(null);
    } catch (e) {
      // Surface the backend's reason inline in the modal footer.
      alert(e instanceof ApiError ? e.message : "Couldn't cancel that booking.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || loading) return <Skeleton className="h-96 w-full" />;

  return (
    <section className="space-y-4 py-2">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Bookings</h1>
        <p className="text-sm text-muted-foreground">Your confirmed bookings across every offer.</p>
      </div>

      {bookings.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {vocab.copy.noAvailability}
        </p>
      ) : (
        <>
          <BookingCalendar bookings={bookings} timezone={tz} defaultView="week" onOpen={setSelected} />

          {/* List of the same feed, split upcoming / past. */}
          <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
            {(["upcoming", "past"] as Scope[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                aria-pressed={scope === s}
                className={cn(
                  "rounded-md px-4 py-1 text-sm font-medium capitalize transition-colors",
                  scope === s
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {listed.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
              No {scope} bookings.
            </p>
          ) : (
            <ul className="space-y-2">
              {listed.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(b)}
                    className="flex w-full items-center gap-3 rounded-xl border border-border bg-card p-3 text-left transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate font-medium">{b.title}</span>
                        <span
                          className={cn(
                            "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                            STATUS_CLASS[b.status],
                          )}
                        >
                          {b.status}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-sm text-muted-foreground">{b.client}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="size-3.5" aria-hidden /> {formatBookingWhen(b.startUtc, b.endUtc, tz)}
                        </span>
                        <span>{formatMoney(b.priceMinorUnits, b.currency)}</span>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Booking">
        {selected ? (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">{selected.title}</h3>
                <p className="text-sm text-muted-foreground">{selected.client}</p>
              </div>
              <span className={cn("shrink-0 rounded-full px-2.5 py-1 text-xs font-medium capitalize", STATUS_CLASS[selected.status])}>
                {selected.status}
              </span>
            </div>

            <dl className="space-y-2 text-sm">
              <Row icon={<Clock className="size-4" aria-hidden />}>
                {formatBookingWhen(selected.startUtc, selected.endUtc, tz)}
              </Row>
              {vocab.partyNoun && selected.partySize > 1 ? (
                <Row icon={<Users className="size-4" aria-hidden />}>
                  {selected.partySize} {vocab.partyNoun}
                </Row>
              ) : null}
              <Row icon={<span className="grid size-4 place-items-center text-xs">€</span>}>
                {formatMoney(selected.priceMinorUnits, selected.currency)} total
              </Row>
            </dl>

            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              <Button size="sm" variant="outline" isDisabled={messaging} onPress={messageClient}>
                Message client
              </Button>
              <Button size="sm" variant="outline" isDisabled>
                Reschedule
              </Button>
              <Button
                size="sm"
                variant="destructive"
                isDisabled={busy || selected.status === "completed"}
                onPress={() => doCancel(selected.id)}
              >
                Cancel booking
              </Button>
            </div>
            {selected.status === "completed" && reviewable[selected.id] ? (
              <RateClient bookingId={selected.id} clientName={selected.client} />
            ) : null}

            <p className="text-[11px] text-muted-foreground">
              Reschedule is coming to the owner console next.
            </p>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}

function Row({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <span>{children}</span>
    </div>
  );
}

/** Rate the customer after a completed booking — feeds their reputation. */
function RateClient({ bookingId, clientName }: { bookingId: string; clientName: string }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(value: number) {
    setRating(value);
    setBusy(true);
    try {
      await rateClient(bookingId, value);
      setDone(true);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Couldn't submit the rating.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p className="rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-primary">
        Thanks — you rated {clientName} {rating}★. It shows on their customer profile.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-background/40 px-3 py-2">
      <p className="mb-1 text-xs font-medium">Rate this customer</p>
      <div className="flex items-center gap-1" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((v) => (
          <button
            key={v}
            type="button"
            disabled={busy}
            aria-label={`${v} star${v > 1 ? "s" : ""}`}
            onMouseEnter={() => setHover(v)}
            onClick={() => submit(v)}
            className="p-0.5 disabled:opacity-50"
          >
            <Star
              className={cn(
                "size-5",
                (hover || rating) >= v ? "fill-amber-400 text-amber-400" : "fill-muted text-muted-foreground/40",
              )}
              aria-hidden
            />
          </button>
        ))}
      </div>
    </div>
  );
}
