"use client";

/**
 * Resource picker for unit_selection services — appears before the calendar.
 * A scrollable list of units (image, name, attribute rows) plus an "Any
 * available unit" option that shows the union of availability.
 */
import { Layers } from "lucide-react";
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

  return (
    <Modal open={open} onClose={onClose} title={`Choose a ${noun}`}>
      <button
        type="button"
        onClick={() => onPick(null)}
        className={cn(
          "mb-2 flex w-full items-center gap-3 rounded-lg border border-border p-3 text-left",
          buttonFx.surface,
        )}
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-md bg-muted">
          <Layers className="size-5 text-muted-foreground" aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-medium">Any available {noun}</span>
          <span className="block text-xs text-muted-foreground">Show all availability</span>
        </span>
      </button>

      <div className="space-y-2">
        {resources.loading && !resources.data ? (
          <>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
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
                "flex w-full items-start gap-3 rounded-lg border border-border p-3 text-left",
                buttonFx.surface,
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={r.imageUrl ?? ""}
                alt=""
                className="size-12 shrink-0 rounded-md bg-muted object-cover"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{r.name}</span>
                {r.description ? (
                  <span className="block truncate text-xs text-muted-foreground">
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
