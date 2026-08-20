"use client";

/**
 * Selection → confirmation → create → result, wrapped around the calendar.
 * Single-slot services open confirmation on tap; range services (maxSlots > 1)
 * use tap-start / tap-end to build a contiguous span (validated inline, no
 * modal) with a running total. On SLOT_UNAVAILABLE the user stays on the
 * calendar: a banner explains, availability refreshes, other choices survive.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Booking, Provider, Resource, Service, Slot } from "@/types/domain";
import { createBooking, getAvailability, getResources, isApiError, joinWaitlist } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { CalendarView } from "@/components/calendar/calendar-view";
import { MediaTile } from "@/components/media-tile";
import { ConfirmScreen } from "@/components/booking/confirm-screen";
import { ResultScreen } from "@/components/booking/result-screen";
import { SelectionBar } from "@/components/booking/selection-bar";
import { Button } from "@/components/ui/button";
import { InlineMessage } from "@/components/ui/inline-message";
import { pruneValues, type FieldValues } from "@/components/booking/field-form";
import { ms } from "@/lib/format";
import { validateSpan } from "@/lib/slot-span";

type Phase = "browse" | "confirm" | "result";

export function BookingFlow({
  provider,
  service,
  resource,
  tz,
}: {
  provider: Provider;
  service: Service;
  resource: Resource | null;
  tz: string;
}) {
  const { vertical, copy } = useApp();
  const router = useRouter();
  const isRange = service.maxSlotsPerBooking > 1;
  /** `booking.granularity: "none"` — the customer picks no date at all. They
   *  submit a request and the business assigns the date afterwards, announcing
   *  it through messaging. The calendar must never render in this mode. */
  const requestMode = service.granularity === "none";

  const [phase, setPhase] = useState<Phase>("browse");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [start, setStart] = useState<Slot | null>(null);
  const [partySize, setPartySize] = useState(1);
  // Repeat count, 1 = no repeat. Only offered where the config enables
  // `recurrence` AND the capability is on; every other deployment never sees it.
  const [repeatCount, setRepeatCount] = useState(1);
  // The engine accepts one pattern per series, but the config may declare
  // several. Defaulting to the first and letting the customer change it is what
  // makes `recurrence.patterns[1..]` reachable at all — they used to be dead.
  const patterns = service.recurrence.enabled ? service.recurrence.patterns : [];
  const [repeatPattern, setRepeatPattern] = useState<string | null>(null);
  const pattern = repeatPattern ?? patterns[0] ?? null;

  // What the config additionally asks for, and the customer answers:
  // `party.composition` bands, `booking.options`, `booking.subject` and
  // `metaFields.bookings`. Every one is empty on a deployment that declares
  // none, which is the pre-v2 behaviour exactly.
  const bands = service.party.composition;
  const [partyBands, setPartyBands] = useState<Record<string, number>>({});
  const [options, setOptions] = useState<Record<string, string | boolean>>({});
  const [subject, setSubject] = useState<FieldValues>({});
  const [metaValues, setMetaValues] = useState<FieldValues>({});
  // `booking.sequence` — the customer buys the course, not the first session.
  // Defaults ON where the config declares one: a sequence service that sold a
  // single session would be mis-sold, which is why the block exists.
  const [bookSequence, setBookSequence] = useState(true);
  const [rangeError, setRangeError] = useState<string | null>(null);
  // Request mode still needs a real slot: the DB requires `slot_id not null`,
  // so the flow resolves a PLACEHOLDER behind the customer's back. It is never
  // presented as "their date" — that is the design, not an oversight.
  const [resolving, setResolving] = useState(requestMode);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [booking, setBooking] = useState<Booking | null>(null);

  const resources = useAsync(() => getResources(service.id), [service.id]);
  const unitFor = (id: string) => resources.data?.find((r) => r.id === id);
  const nameFor = (id: string) => unitFor(id)?.name ?? "";
  const selectedIds = useMemo(() => new Set(slots.map((s) => s.id)), [slots]);

  // Built as plain strings so the effect below can depend on them: `vertical`
  // is a NEW object on every AppProvider render (it is rebuilt by
  // applyPivotVocabulary), so depending on it directly would re-run the resolve
  // forever. Strings compare by value, so these deps settle.
  const noIntakeMessage = `${provider.name} is not accepting new ${vertical.bookingNounPlural.toLowerCase()} at this time. Please contact the ${vertical.providerNoun.toLowerCase()} directly.`;
  const resolveFailedMessage = `Couldn't open an ${vertical.bookingNoun.toLowerCase()} request. Please try again.`;

  // Resolve the placeholder and go straight to confirm. Absolute-instant date
  // maths only (a 30-day UTC window) — nothing here is a wall-clock date, so no
  // timezone is involved.
  useEffect(() => {
    if (!requestMode) return;
    // Only ever resolve from the entry phase. Without this, a re-render that
    // changed the deps would resolve a fresh placeholder while the customer was
    // mid-form on the confirm screen and wipe what they had typed.
    if (phase !== "browse") return;
    let cancelled = false;
    setResolving(true);
    setResolveError(null);
    const now = new Date();
    getAvailability({
      serviceId: service.id,
      resourceId: resource?.id,
      fromUtc: now.toISOString(),
      toUtc: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    })
      .then((days) => {
        if (cancelled) return;
        const placeholder = days
          .flatMap((d) => d.slots)
          .find((slot) => slot.status === "available");
        if (!placeholder) {
          setResolveError(noIntakeMessage);
          setResolving(false);
          return;
        }
        setSlots([placeholder]);
        setPartySize(1);
        if (bands.length) setPartyBands({ [bands[0].key]: 1 });
        setConfirmError(null);
        setResolving(false);
        setPhase("confirm");
      })
      .catch((e) => {
        if (cancelled) return;
        setResolveError(isApiError(e) ? e.message : resolveFailedMessage);
        setResolving(false);
      });
    return () => {
      cancelled = true;
    };
    // `reloadKey` re-runs the resolve after a placeholder was taken from under us.
  }, [
    requestMode,
    service.id,
    resource?.id,
    reloadKey,
    phase,
    // `.length` deliberately: the array identity changes whenever the service is
    // refetched, and re-resolving on that would discard the customer's answers.
    bands.length,
    noIntakeMessage,
    resolveFailedMessage,
  ]);

  function resetSelection() {
    setSlots([]);
    setStart(null);
    setRangeError(null);
    setPartySize(1);
    setPartyBands({});
    setOptions({});
    setSubject({});
    setMetaValues({});
  }

  /** Party bands and party size are two views of one number, and the server
   *  rejects them when they disagree — so the bands drive the size. */
  function changeBands(next: Record<string, number>) {
    setPartyBands(next);
    setPartySize(Math.max(1, Object.values(next).reduce((sum, n) => sum + n, 0)));
  }

  async function handleSelect(slot: Slot) {
    setBanner(null);
    if (!isRange) {
      setSlots([slot]);
      setPartySize(1);
      // Seed one head in the first band, so a composition deployment opens on a
      // party of one rather than zero (which the server rejects).
      if (bands.length) setPartyBands({ [bands[0].key]: 1 });
      setConfirmError(null);
      setPhase("confirm");
      return;
    }
    setRangeError(null);
    // Start (or restart) the range when there's no anchor, a different
    // resource, or a tap at/before the anchor.
    if (!start || slot.resourceId !== start.resourceId || ms(slot.startUtc) <= ms(start.startUtc)) {
      setStart(slot);
      setSlots([slot]);
      return;
    }
    // Second tap: build the contiguous span on the anchor's resource.
    try {
      const avail = await getAvailability({
        serviceId: service.id,
        resourceId: start.resourceId,
        fromUtc: start.startUtc,
        toUtc: slot.endUtc,
      });
      const span = avail
        .flatMap((d) => d.slots)
        .filter((s) => s.resourceId === start.resourceId)
        .sort((a, b) => ms(a.startUtc) - ms(b.startUtc));
      const problem = validateSpan(span, service, vertical.slotNounPlural);
      if (problem) {
        setRangeError(problem);
        return;
      }
      setSlots(span);
    } catch {
      setRangeError("Couldn't build that range. Try again.");
    }
  }

  async function confirm() {
    if (busy || slots.length === 0) return;
    setBusy(true);
    setConfirmError(null);
    try {
      const b = await createBooking({
        serviceId: service.id,
        resourceId: slots[0].resourceId,
        slotIds: slots.map((s) => s.id),
        partySize,
        // Only sent where the config declares the block, so a deployment
        // without it posts the same body it always did.
        partyBands: bands.length ? partyBands : undefined,
        options: Object.keys(options).length ? options : undefined,
        subject: service.subject.enabled ? pruneValues(subject) : undefined,
        metadata: Object.keys(metaValues).length ? pruneValues(metaValues) : undefined,
        // A service is a sequence OR a repeatable one-off; the sequence wins
        // because it describes what is being SOLD, not how often it recurs.
        repeat:
          service.sequence.enabled && service.sequence.steps > 1 && bookSequence
            ? { pattern: "sequence", count: service.sequence.steps }
            : repeatCount > 1 && pattern
              ? { pattern, count: repeatCount }
              : undefined,
      });
      setBooking(b);
      setPhase("result");
    } catch (e) {
      const msg = isApiError(e) ? e.message : `Couldn't complete the ${vertical.bookingNoun.toLowerCase()}.`;
      if (isApiError(e) && (e.code === "SLOT_UNAVAILABLE" || e.code === "CAPACITY_EXCEEDED")) {
        setBanner(msg);
        resetSelection();
        setReloadKey((k) => k + 1);
        setPhase("browse");
      } else {
        setConfirmError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  /** Take a place in the queue for a full slot. Feedback goes through the same
   *  banner the calendar already uses for "that slot was just taken", so the
   *  flow gains no new UI state for a rare action. */
  async function joinQueue(slot: Slot) {
    try {
      const entry = await joinWaitlist(slot.id, partySize);
      setBanner(
        entry.peopleAhead
          ? `You're on the waitlist — ${entry.peopleAhead} ahead of you.`
          : (copy.waitlistJoined ?? "You're on the waitlist."),
      );
    } catch (e) {
      setBanner(isApiError(e) ? e.message : "Couldn't join the waitlist.");
    }
  }

  function done() {
    setBooking(null);
    resetSelection();
    // In request mode there is nothing to go back TO — no calendar, and
    // re-entering "browse" would just resolve another placeholder forever. The
    // request now lives in the bookings list, so send them there.
    if (requestMode) {
      router.push("/bookings");
      return;
    }
    setReloadKey((k) => k + 1); // reflect the decremented capacity
    setPhase("browse");
  }

  if (phase === "result" && booking) {
    return <ResultScreen booking={booking} service={service} tz={tz} onDone={done} />;
  }

  if (phase === "confirm") {
    return (
      <ConfirmScreen
        provider={provider}
        service={service}
        resourceName={nameFor(slots[0]?.resourceId ?? "")}
        resourceImageUrl={unitFor(slots[0]?.resourceId ?? "")?.imageUrl}
        slots={slots}
        tz={tz}
        vertical={vertical}
        partySize={partySize}
        onPartyChange={setPartySize}
        partyBands={partyBands}
        onPartyBandsChange={changeBands}
        options={options}
        onOptionsChange={setOptions}
        subject={subject}
        onSubjectChange={setSubject}
        metaValues={metaValues}
        onMetaChange={setMetaValues}
        repeatPattern={pattern}
        repeatPatterns={patterns}
        onRepeatPatternChange={setRepeatPattern}
        repeatCount={repeatCount}
        onRepeatChange={setRepeatCount}
        bookSequence={bookSequence}
        onBookSequenceChange={setBookSequence}
        busy={busy}
        error={confirmError}
        onConfirm={confirm}
        onBack={() => {
          if (requestMode) {
            router.back();
            return;
          }
          setPhase("browse");
          if (!isRange) resetSelection();
        }}
      />
    );
  }

  // Request mode never reaches the calendar: it is either resolving the
  // placeholder or explaining why it could not.
  if (requestMode) {
    return (
      <div>
        {/* No calendar competes for the space here, so the unit gets a full
            banner rather than the compact thumbnail the date view uses. This
            screen is otherwise a title and a status line — the photo is the
            only thing on it that shows what was chosen. */}
        <div className="mb-3">
          <MediaTile
            src={resource?.imageUrl ?? service.imageUrl}
            alt=""
            rounded="rounded-xl"
            className="mb-3 h-40 w-full"
          />
          <h1 className="text-lg font-semibold tracking-tight">{service.name}</h1>
          <p className="text-sm text-muted-foreground">
            {provider.name}
            {resource ? ` · ${resource.name}` : ""}
          </p>
        </div>
        {banner ? (
          <InlineMessage tone="notice" live="assertive" className="mb-3">
            {banner}
          </InlineMessage>
        ) : null}
        {resolveError ? (
          <div className="rounded-xl border border-border bg-card p-4">
            <InlineMessage>{resolveError}</InlineMessage>
            <Button
              variant="outline"
              className="mt-3"
              onPress={() => setReloadKey((k) => k + 1)}
            >
              Try again
            </Button>
          </div>
        ) : (
          <div
            role="status"
            className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground"
          >
            {resolving
              ? `Opening an ${vertical.bookingNoun.toLowerCase()} request…`
              : vertical.copy.noAvailability}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {/* The unit the family just chose stays on screen while they pick a date.
          Without this the chapel is a photo in a modal that closes and a name in
          a subtitle — the picture never returns. Falls back to the service's own
          tile when no single unit is bound ("any available"). */}
      <div className="mb-3 flex items-center gap-3">
        <MediaTile
          src={resource?.imageUrl ?? service.imageUrl}
          alt=""
          className="aspect-[4/3] w-24"
        />
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight">{service.name}</h1>
          <p className="text-sm text-muted-foreground">
            {provider.name}
            {resource ? ` · ${resource.name}` : ""}
          </p>
        </div>
      </div>

      {banner ? (
        <InlineMessage tone="notice" live="assertive" className="mb-3">
          {banner}
        </InlineMessage>
      ) : null}

      <CalendarView
        service={service}
        resourceId={resource?.id ?? null}
        tz={tz}
        selectedIds={selectedIds}
        onSelect={handleSelect}
        onWaitlist={service.waitlist.enabled ? joinQueue : undefined}
        reloadKey={reloadKey}
      />

      {isRange && slots.length > 0 ? (
        <SelectionBar
          service={service}
          slots={slots}
          error={rangeError}
          onContinue={() => {
            setConfirmError(null);
            // Same seeding as the single-slot path: a composition deployment
            // must open the confirm screen on a party of one, not of none.
            if (bands.length && !Object.keys(partyBands).length) {
              changeBands({ [bands[0].key]: 1 });
            }
            setPhase("confirm");
          }}
          onClear={resetSelection}
        />
      ) : isRange && rangeError ? (
        <p className="mt-2 text-sm text-destructive">{rangeError}</p>
      ) : null}
    </div>
  );
}
