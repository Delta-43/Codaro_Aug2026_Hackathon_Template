"use client";

/**
 * Resources and availability for one service, inside the owner console.
 *
 * The console could create a service but never the resources it is booked on,
 * nor the slots that make it bookable — so a service created through the UI was
 * inert and only the seed could produce a working catalogue. This closes that:
 * add a unit, then open a run of times on it.
 *
 * Vocabulary comes from the vertical, so a pivot calling its resources "Rooms"
 * or "Tutors" labels this accordingly.
 */
import { useCallback, useEffect, useState } from "react";
import { ApiError, createResource, createSlotRun, deleteResource, getResources } from "@/api";
import type { Resource, Service } from "@/types/domain";
import { useOwner } from "@/context/owner-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/skeleton";

/** `datetime-local` yields wall-clock with no zone; the API takes UTC. */
function toUtc(local: string): string {
  return new Date(local).toISOString();
}

/** Tomorrow 09:00 local, as the `datetime-local` value format. */
function defaultStart(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ServiceResources({ service }: { service: Service }) {
  const { vocab } = useOwner();
  const noun = vocab.resourceNoun.toLowerCase();
  const [resources, setResources] = useState<Resource[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [capacity, setCapacity] = useState(1);
  const [start, setStart] = useState(defaultStart());
  const [count, setCount] = useState(8);

  // Bumped after every write to re-read the list. A plain `load()` called from
  // the effect body reads as a synchronous setState to the linter and to anyone
  // skimming it; a counter keeps the fetch entirely inside the effect.
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    getResources(service.id)
      .then((rows) => !cancelled && setResources(rows))
      .catch(() => !cancelled && setResources([]));
    return () => {
      cancelled = true;
    };
  }, [service.id, reloadKey]);

  async function act(action: () => Promise<unknown>, done?: () => void) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await action();
      done?.();
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <h3 className="text-sm font-semibold">{vocab.resourceNounPlural}</h3>

      {resources === null ? (
        <Skeleton className="mt-2 h-16 w-full" />
      ) : resources.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">
          No {vocab.resourceNounPlural.toLowerCase()} yet — this {vocab.serviceNoun.toLowerCase()}{" "}
          cannot be booked until it has one.
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {resources.map((r) => (
            <li key={r.id} className="rounded-lg border border-border p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{r.name}</div>
                  <div className="text-xs text-muted-foreground">
                    capacity {r.capacity}
                    {r.active ? "" : " · inactive"}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  isDisabled={busy}
                  onPress={() => act(() => deleteResource(r.id))}
                >
                  Remove
                </Button>
              </div>

              {/* Availability. The engine never invents slots, so a resource
                  with none is invisible to customers however well configured. */}
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="text-xs text-muted-foreground">
                  From
                  <Input
                    type="datetime-local"
                    value={start}
                    className="mt-1 h-9"
                    onChange={(e) => setStart(e.target.value)}
                  />
                </label>
                <label className="text-xs text-muted-foreground">
                  How many
                  <Input
                    type="number"
                    min={1}
                    max={48}
                    value={count}
                    className="mt-1 h-9 w-24"
                    onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
                <Button
                  size="sm"
                  isDisabled={busy}
                  onPress={() =>
                    act(async () => {
                      const res = await createSlotRun({
                        resourceId: r.id,
                        startsAt: toUtc(start),
                        durationMinutes: service.slotDurationMinutes,
                        count,
                        capacity: r.capacity,
                      });
                      // Partial success is the normal case — a run that overlaps
                      // existing availability opens the rest. Say so rather than
                      // reporting a flat success the calendar contradicts.
                      setNote(
                        res.rejected.length
                          ? `Opened ${res.created.length}; ${res.rejected.length} skipped (${res.rejected[0].message})`
                          : `Opened ${res.created.length} ${vocab.slotNounPlural.toLowerCase()}.`,
                      );
                    })
                  }
                >
                  Add availability
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add a unit */}
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted-foreground">
          New {noun}
          <Input
            value={name}
            placeholder={vocab.resourceNoun}
            className="mt-1 h-9"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Capacity
          <Input
            type="number"
            min={1}
            value={capacity}
            className="mt-1 h-9 w-24"
            onChange={(e) => setCapacity(Math.max(1, Number(e.target.value) || 1))}
          />
        </label>
        <Button
          size="sm"
          variant="outline"
          isDisabled={busy || !name.trim()}
          onPress={() =>
            act(
              () =>
                createResource({
                  serviceId: service.id,
                  name: name.trim(),
                  capacity,
                }),
              () => setName(""),
            )
          }
        >
          Add {noun}
        </Button>
      </div>

      {note ? <p className="mt-2 text-sm text-muted-foreground">{note}</p> : null}
      {error ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
