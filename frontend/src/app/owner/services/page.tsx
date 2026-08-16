"use client";

/**
 * Business tab 2 — Services. An editable overview of every offer the business
 * runs, driven by the active demo use case so it stays coherent with the rest
 * of business mode across all niches. Glanceable stats per offer (price, margin,
 * upcoming/past bookings, rating), a drill-in editor for the offer's parameters,
 * and add/remove — each destructive/edit action gated behind the full-screen
 * "are you sure?" confirm. Edits are demo-local (per session); swap this for the
 * owner-gated write API when a single niche is wired end-to-end.
 */
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ChevronDown, Plus, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/business/confirm-dialog";
import { useOwner } from "@/context/owner-context";
import { serviceStats } from "@/lib/business-demo";
import { formatDuration, formatMoney } from "@/lib/format";
import type { BookingModel } from "@/types/domain";
import type { UseCase } from "@/config/useCases";

const MODELS: { id: BookingModel; label: string }[] = [
  { id: "unit_selection", label: "Unit selection (many units, pick one)" },
  { id: "one_to_one", label: "One-to-one (single unit)" },
  { id: "shared_capacity", label: "Shared capacity (party size)" },
];
const modelLabel = (m: BookingModel) => MODELS.find((x) => x.id === m)?.label ?? m;

interface Offer {
  id: string;
  name: string;
  priceMajor: number;
  currency: string;
  model: BookingModel;
  durationMinutes: number;
  maxSlots: number;
  cutoffHours: number;
}

/** Per-niche default slot length: multi-day niches bill per day. */
function defaultDuration(uc: UseCase): number {
  return ["stays", "rentals", "hires"].includes(uc.bookingUnit) ? 1440 : 60;
}

function seedOffers(uc: UseCase): Offer[] {
  const dur = defaultDuration(uc);
  return uc.services.map((s, i) => ({
    id: `${uc.id}-${i}`,
    name: s.name,
    priceMajor: s.priceMajor,
    currency: s.currency,
    model: s.model,
    durationMinutes: dur,
    maxSlots: s.model === "shared_capacity" ? 12 : 1,
    cutoffHours: 24,
  }));
}

export default function ServicesPage() {
  const { useCase } = useOwner();
  const [offers, setOffers] = useState<Offer[]>(() => seedOffers(useCase));
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  // Reseed when the demo use case changes so offers match the niche.
  useEffect(() => {
    setOffers(seedOffers(useCase));
    setOpenId(null);
    setCreating(false);
  }, [useCase.id]);

  return (
    <section className="space-y-5 py-2">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">{useCase.serviceNounPlural}</h1>
          <p className="text-sm text-muted-foreground">
            What {useCase.business.name} offers, and the rules for each.
          </p>
        </div>
        <Button size="sm" onPress={() => setCreating((v) => !v)}>
          <Plus aria-hidden /> Add offer
        </Button>
      </div>

      {creating ? (
        <OfferForm
          useCase={useCase}
          onCancel={() => setCreating(false)}
          onCreate={(o) => {
            setOffers((prev) => [...prev, o]);
            setCreating(false);
          }}
        />
      ) : null}

      {offers.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No {useCase.serviceNounPlural.toLowerCase()} yet — add your first offer.
        </p>
      ) : (
        <ul className="space-y-3">
          {offers.map((o) => (
            <ServiceCard
              key={o.id}
              offer={o}
              open={openId === o.id}
              onToggle={() => setOpenId((id) => (id === o.id ? null : o.id))}
              onSave={(next) => setOffers((prev) => prev.map((x) => (x.id === o.id ? next : x)))}
              onDelete={() => {
                setOffers((prev) => prev.filter((x) => x.id !== o.id));
                setOpenId(null);
              }}
            />
          ))}
        </ul>
      )}

      <p className="text-[11px] text-muted-foreground">
        Offers are demo data for the selected use case; edits apply for this session. Switch use cases in Settings → Demo.
      </p>
    </section>
  );
}

function ServiceCard({
  offer,
  open,
  onToggle,
  onSave,
  onDelete,
}: {
  offer: Offer;
  open: boolean;
  onToggle: () => void;
  onSave: (next: Offer) => void;
  onDelete: () => void;
}) {
  const stats = useMemo(() => serviceStats(offer.id), [offer.id]);
  return (
    <li className="overflow-hidden rounded-2xl border border-border bg-card">
      <button onClick={onToggle} className="flex w-full items-start gap-3 p-4 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">{offer.name}</span>
            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {modelLabel(offer.model).split(" (")[0]}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatMoney(Math.round(offer.priceMajor * 100), offer.currency)} · per{" "}
            {formatDuration(offer.durationMinutes)}
            {offer.maxSlots > 1 ? ` · up to ${offer.maxSlots}` : ""}
          </p>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center">
            <Stat label="Margin" value={`${stats.marginPct}%`} />
            <Stat label="Upcoming" value={String(stats.upcoming)} />
            <Stat label="Past" value={String(stats.pastTotal)} />
            <Stat
              label="Rating"
              value={
                <span className="inline-flex items-center gap-0.5">
                  <Star className="size-3 fill-amber-400 text-amber-400" aria-hidden />
                  {stats.rating.toFixed(1)}
                </span>
              }
            />
          </div>
        </div>
        <ChevronDown
          className={`mt-1 size-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {open ? (
        <div className="border-t border-border p-4">
          <ServiceEditor offer={offer} onSave={onSave} onDelete={onDelete} />
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

function ServiceEditor({ offer, onSave, onDelete }: { offer: Offer; onSave: (o: Offer) => void; onDelete: () => void }) {
  const [name, setName] = useState(offer.name);
  const [priceMajor, setPriceMajor] = useState(offer.priceMajor);
  const [duration, setDuration] = useState(offer.durationMinutes);
  const [maxSlots, setMaxSlots] = useState(offer.maxSlots);
  const [cutoff, setCutoff] = useState(offer.cutoffHours);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const dirty =
    name !== offer.name ||
    priceMajor !== offer.priceMajor ||
    duration !== offer.durationMinutes ||
    maxSlots !== offer.maxSlots ||
    cutoff !== offer.cutoffHours;

  return (
    <div className="rounded-2xl border border-border bg-background/40 p-3">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Edit offer</p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name" className="col-span-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={`Price (${offer.currency})`}>
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
      <p className="mt-2 text-[11px] text-muted-foreground">Booking model: {modelLabel(offer.model)}.</p>

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
            ...offer,
            name,
            priceMajor,
            durationMinutes: duration,
            maxSlots: Math.max(1, maxSlots),
            cutoffHours: cutoff,
          });
          setConfirming(false);
        }}
        confirmLabel="Yes, apply changes"
      >
        <p className="text-muted-foreground">You&apos;re updating</p>
        <p className="font-medium">{name}</p>
        <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
          <li>Price {formatMoney(Math.round(priceMajor * 100), offer.currency)}</li>
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
        <p className="font-medium">{offer.name}</p>
      </ConfirmDialog>
    </div>
  );
}

function OfferForm({
  useCase,
  onCreate,
  onCancel,
}: {
  useCase: UseCase;
  onCreate: (o: Offer) => void;
  onCancel: () => void;
}) {
  const currency = useCase.services[0]?.currency ?? "EUR";
  const [name, setName] = useState("");
  const [model, setModel] = useState<BookingModel>(useCase.services[0]?.model ?? "unit_selection");
  const [priceMajor, setPriceMajor] = useState(20);
  const [duration, setDuration] = useState(defaultDuration(useCase));
  const [maxSlots, setMaxSlots] = useState(1);
  const [cutoff, setCutoff] = useState(24);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate({
      id: `${useCase.id}-new-${Date.now()}`,
      name: name.trim(),
      priceMajor,
      currency,
      model,
      durationMinutes: duration,
      maxSlots: Math.max(1, maxSlots),
      cutoffHours: cutoff,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-border bg-card p-4">
      <Field label={`New ${useCase.serviceNoun.toLowerCase()}`}>
        <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder={useCase.services[0]?.name} />
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
