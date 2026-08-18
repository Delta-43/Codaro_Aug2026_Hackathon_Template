"use client";

/**
 * Business tab 2 — Services. An editable overview of every offer the business
 * runs, backed by the real owner API: glanceable stats per offer (upcoming/past
 * bookings, revenue, rating) from /owner/services, a per-offer auto-approve
 * toggle, a drill-in editor (PATCH /services/{id}), and add/remove
 * (POST/DELETE /services) — each destructive/edit action gated behind the
 * full-screen "are you sure?" confirm.
 */
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ChevronDown, Plus, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/business/confirm-dialog";
import { useOwner } from "@/context/owner-context";
import {
  createService,
  deleteService,
  getOwnerServices,
  updateService,
  ApiError,
} from "@/api";
import type { BookingModel, OwnerServiceSummary } from "@/types/domain";
import { formatDuration, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const MODELS: { id: BookingModel; label: string }[] = [
  { id: "unit_selection", label: "Unit selection (many units, pick one)" },
  { id: "one_to_one", label: "One-to-one (single unit)" },
  { id: "shared_capacity", label: "Shared capacity (party size)" },
];
const modelLabel = (m: BookingModel) => MODELS.find((x) => x.id === m)?.label ?? m;

export default function ServicesPage() {
  const { ready, activeProvider, vocab } = useOwner();
  const [services, setServices] = useState<OwnerServiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const all = await getOwnerServices().catch(() => [] as OwnerServiceSummary[]);
    setServices(activeProvider ? all.filter((s) => s.providerId === activeProvider.id) : all);
    setLoading(false);
  }, [activeProvider]);

  useEffect(() => {
    void load();
  }, [load]);

  const currency = services[0]?.currency ?? "EUR";

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That change didn't go through.");
    }
  }

  if (!ready || loading) {
    return (
      <div className="space-y-3 py-2">
        <div className="h-6 w-40 animate-pulse rounded bg-muted" />
        <div className="h-32 w-full animate-pulse rounded-2xl bg-muted" />
      </div>
    );
  }

  return (
    <section className="space-y-5 py-2">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">{vocab.serviceNounPlural}</h1>
          <p className="text-sm text-muted-foreground">
            What {activeProvider?.name ?? "your business"} offers, and the rules for each.
          </p>
        </div>
        {activeProvider ? (
          <Button size="sm" onPress={() => setCreating((v) => !v)}>
            <Plus aria-hidden /> Add offer
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {creating && activeProvider ? (
        <OfferForm
          currency={currency}
          serviceNoun={vocab.serviceNoun}
          onCancel={() => setCreating(false)}
          onCreate={(input) =>
            run(() => createService({ providerId: activeProvider.id, ...input })).then(() => setCreating(false))
          }
        />
      ) : null}

      {services.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No {vocab.serviceNounPlural.toLowerCase()} yet — add your first offer.
        </p>
      ) : (
        <ul className="space-y-3">
          {services.map((s) => (
            <ServiceCard
              key={s.id}
              service={s}
              open={openId === s.id}
              onToggle={() => setOpenId((id) => (id === s.id ? null : s.id))}
              onToggleAutoApprove={() => run(() => updateService(s.id, { autoApprove: !s.autoApprove }))}
              onSave={(patch) => run(() => updateService(s.id, patch)).then(() => setOpenId(null))}
              onDelete={() => run(() => deleteService(s.id)).then(() => setOpenId(null))}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function ServiceCard({
  service: s,
  open,
  onToggle,
  onToggleAutoApprove,
  onSave,
  onDelete,
}: {
  service: OwnerServiceSummary;
  open: boolean;
  onToggle: () => void;
  onToggleAutoApprove: () => void;
  onSave: (patch: EditPatch) => void;
  onDelete: () => void;
}) {
  return (
    <li className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-start gap-3 p-4">
        <button onClick={onToggle} className="min-w-0 flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">{s.name}</span>
            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {modelLabel(s.bookingModel).split(" (")[0]}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatMoney(s.priceMinorUnits, s.currency)} · per {formatDuration(s.slotDurationMinutes)}
            {s.maxSlotsPerBooking > 1 ? ` · up to ${s.maxSlotsPerBooking}` : ""}
          </p>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center">
            <Stat label="Upcoming" value={String(s.stats.upcomingBookings)} />
            <Stat label="Past" value={String(s.stats.pastBookings)} />
            <Stat label="Revenue" value={formatMoney(s.stats.revenueMinorUnits, s.stats.currency)} />
            <Stat
              label="Rating"
              value={
                s.stats.reviewCount ? (
                  <span className="inline-flex items-center gap-0.5">
                    <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                    {s.stats.avgRating.toFixed(1)}
                  </span>
                ) : (
                  "—"
                )
              }
            />
          </div>
        </button>
        <ChevronDown
          className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2.5">
        <div className="min-w-0">
          <p className="text-xs font-medium">Auto-approve</p>
          <p className="truncate text-[11px] text-muted-foreground">
            {s.autoApprove ? "Bookings confirm instantly." : "Requests wait for your review."}
            {s.stats.pendingRequests > 0 ? ` · ${s.stats.pendingRequests} pending` : ""}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={s.autoApprove}
          aria-label="Toggle auto-approve"
          onClick={onToggleAutoApprove}
          className={cn(
            "flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors",
            s.autoApprove ? "bg-primary" : "bg-muted",
          )}
        >
          <span
            className={cn(
              "size-5 rounded-full bg-card shadow-sm transition-transform",
              s.autoApprove ? "translate-x-5" : "translate-x-0",
            )}
          />
        </button>
      </div>

      {open ? (
        <div className="border-t border-border p-4">
          <ServiceEditor service={s} onSave={onSave} onDelete={onDelete} />
        </div>
      ) : null}
    </li>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-muted/50 py-1.5">
      <div className="text-sm font-semibold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}

interface EditPatch {
  name: string;
  priceMinorUnits: number;
  slotDurationMinutes: number;
  maxSlotsPerBooking: number;
  cancellationCutoffHours: number;
}

function ServiceEditor({
  service: s,
  onSave,
  onDelete,
}: {
  service: OwnerServiceSummary;
  onSave: (patch: EditPatch) => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(s.name);
  const [priceMajor, setPriceMajor] = useState(s.priceMinorUnits / 100);
  const [duration, setDuration] = useState(s.slotDurationMinutes);
  const [maxSlots, setMaxSlots] = useState(s.maxSlotsPerBooking);
  const [cutoff, setCutoff] = useState(s.cancellationCutoffHours);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const dirty =
    name !== s.name ||
    Math.round(priceMajor * 100) !== s.priceMinorUnits ||
    duration !== s.slotDurationMinutes ||
    maxSlots !== s.maxSlotsPerBooking ||
    cutoff !== s.cancellationCutoffHours;

  return (
    <div className="rounded-2xl border border-border bg-background/40 p-3">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Edit offer</p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name" className="col-span-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={`Price (${s.currency})`}>
          <Input type="number" step="0.01" value={String(priceMajor)} onChange={(e) => setPriceMajor(+e.target.value)} />
        </Field>
        <Field label="Slot duration (min)">
          <Input type="number" value={String(duration)} onChange={(e) => setDuration(+e.target.value)} />
        </Field>
        <Field label="Max slots / booking">
          <Input type="number" value={String(maxSlots)} onChange={(e) => setMaxSlots(+e.target.value)} />
        </Field>
        <Field label="Cancel cutoff (h)">
          <Input type="number" value={String(cutoff)} onChange={(e) => setCutoff(+e.target.value)} />
        </Field>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">Booking model: {modelLabel(s.bookingModel)}.</p>

      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" isDisabled={!dirty} onPress={() => setConfirming(true)}>
          Save changes
        </Button>
        <Button variant="destructive" size="sm" onPress={() => setDeleting(true)}>
          Delete offer
        </Button>
      </div>

      <ConfirmDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        onConfirm={() => {
          onSave({
            name,
            priceMinorUnits: Math.round(priceMajor * 100),
            slotDurationMinutes: duration,
            maxSlotsPerBooking: Math.max(1, maxSlots),
            cancellationCutoffHours: cutoff,
          });
          setConfirming(false);
        }}
        confirmLabel="Yes, apply changes"
      >
        <p className="text-muted-foreground">You&apos;re updating</p>
        <p className="font-medium">{name}</p>
        <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
          <li>Price {formatMoney(Math.round(priceMajor * 100), s.currency)}</li>
          <li>{formatDuration(duration)} per slot · up to {Math.max(1, maxSlots)}</li>
          <li>{cutoff}h cancellation cutoff</li>
        </ul>
      </ConfirmDialog>

      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        onConfirm={() => {
          onDelete();
          setDeleting(false);
        }}
        title="Delete this offer?"
        body="This removes the offer from your listing. Existing bookings may be affected."
        confirmLabel="Yes, delete offer"
      >
        <p className="font-medium">{s.name}</p>
      </ConfirmDialog>
    </div>
  );
}

interface CreateInput {
  name: string;
  description?: string;
  bookingModel: BookingModel;
  slotDurationMinutes: number;
  minSlotsPerBooking: number;
  maxSlotsPerBooking: number;
  priceMinorUnits: number;
  currency: string;
  cancellationCutoffHours: number;
  autoApprove: boolean;
}

function OfferForm({
  currency,
  serviceNoun,
  onCreate,
  onCancel,
}: {
  currency: string;
  serviceNoun: string;
  onCreate: (input: CreateInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [model, setModel] = useState<BookingModel>("unit_selection");
  const [priceMajor, setPriceMajor] = useState(20);
  const [duration, setDuration] = useState(60);
  const [maxSlots, setMaxSlots] = useState(1);
  const [cutoff, setCutoff] = useState(24);
  const [autoApprove, setAutoApprove] = useState(true);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate({
      name: name.trim(),
      bookingModel: model,
      slotDurationMinutes: duration,
      minSlotsPerBooking: 1,
      maxSlotsPerBooking: Math.max(1, maxSlots),
      priceMinorUnits: Math.round(priceMajor * 100),
      currency,
      cancellationCutoffHours: cutoff,
      autoApprove,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-border bg-card p-4">
      <Field label={`New ${serviceNoun.toLowerCase()}`}>
        <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder={serviceNoun} />
      </Field>
      <Field label="Booking model">
        <select
          value={model}
          onChange={(e) => setModel(e.target.value as BookingModel)}
          className="h-8 rounded-2xl border border-transparent bg-input/50 px-2.5 text-sm"
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={`Price (${currency})`}>
          <Input type="number" step="0.01" value={String(priceMajor)} onChange={(e) => setPriceMajor(+e.target.value)} />
        </Field>
        <Field label="Slot duration (min)">
          <Input type="number" value={String(duration)} onChange={(e) => setDuration(+e.target.value)} />
        </Field>
        <Field label="Max slots / booking">
          <Input type="number" value={String(maxSlots)} onChange={(e) => setMaxSlots(+e.target.value)} />
        </Field>
        <Field label="Cancel cutoff (h)">
          <Input type="number" value={String(cutoff)} onChange={(e) => setCutoff(+e.target.value)} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={autoApprove}
          onChange={(e) => setAutoApprove(e.target.checked)}
          className="size-4 rounded border-border accent-primary"
        />
        Auto-approve new bookings (off = review each request)
      </label>
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm">
          Create offer
        </Button>
        <Button type="button" variant="ghost" size="sm" onPress={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col gap-1 ${className ?? ""}`}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
