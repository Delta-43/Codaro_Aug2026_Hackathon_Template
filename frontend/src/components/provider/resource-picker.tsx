// Arbor: a config-driven booking engine
// Copyright (C) 2026 Alban Billiette and the Arbor contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

/**
 * Resource picker for unit_selection services, appears before the calendar.
 * A scrollable list of units (image, name, attribute rows), plus, where the
 * vertical allows it and there is more than one unit to choose between, an
 * "Any available unit" option that shows the union of availability.
 */
import { Layers } from "lucide-react";
import { MediaTile } from "@/components/media-tile";
import type { Resource, Service } from "@/types/domain";
import { getResources } from "@/api";
import { useAsync } from "@/hooks/use-async";
import { useVertical } from "@/context/app-context";
import { buttonFx } from "@/config/buttons";
import { cn } from "@/lib/utils";
import { Modal } from "@/components/modal";
import { Skeleton } from "@/components/skeleton";

export function ResourcePicker({
  service,
  open,
  onClose,
  onPick,
}: {
  service: Service | null;
  open: boolean;
  onClose: () => void;
  onPick: (resource: Resource | null) => void;
}) {
  const vertical = useVertical();
  const noun = vertical.resourceNoun.toLowerCase();
  const resources = useAsync(
    () => (service ? getResources(service.id) : Promise.resolve([])),
    [service?.id],
  );
  const list = resources.data ?? [];
  // The union view only means something when the units are interchangeable AND
  // there is more than one of them. `allowAnyResource: false` opts a
  // vertical out entirely; a single-unit service makes the option a no-op that
  // hides which unit the family is actually getting.
  const showAny = vertical.allowAnyResource && list.length > 1;

  return (
    <Modal open={open} onClose={onClose} title={`Choose a ${noun}`}>
      {showAny ? (
        <button
          type="button"
          onClick={() => onPick(null)}
          className={cn(
            "mb-2 flex w-full items-center gap-3 rounded-lg border border-border p-3 text-left",
            buttonFx.surface,
          )}
        >
          <span className="grid aspect-[4/3] w-24 shrink-0 place-items-center rounded-md bg-muted sm:w-28">
            <Layers className="size-5 text-muted-foreground" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-medium">Any available {noun}</span>
            <span className="block text-xs text-muted-foreground">Show all availability</span>
          </span>
        </button>
      ) : null}

      <div className="space-y-2">
        {resources.loading && !resources.data ? (
          <>
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </>
        ) : resources.error ? (
          <p className="text-sm text-destructive">Couldn&apos;t load {noun}s.</p>
        ) : (
          list.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => onPick(r)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg border border-border p-3 text-left",
                buttonFx.surface,
              )}
            >
              {/* Landscape, not a 48px square: these are rooms and vehicles, and
                  the crop is what tells one resource from another before
                  the family has read a single word. */}
              <MediaTile
                src={r.imageUrl}
                alt=""
                rounded="rounded-md"
                className="aspect-[4/3] w-24 sm:w-28"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{r.name}</span>
                {r.description ? (
                  <span className="block line-clamp-2 text-xs text-muted-foreground">
                    {r.description}
                  </span>
                ) : null}
                <span className="mt-1 flex flex-wrap gap-1">
                  {r.attributes.slice(0, 3).map((a) => (
                    <span
                      key={a.label}
                      className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
                    >
                      {a.label}: {a.value}
                    </span>
                  ))}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
    </Modal>
  );
}
