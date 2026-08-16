"use client";

/**
 * Owner dashboard — set up a business end to end: create a provider, add
 * services (with their per-service rules), add resources, and open slots. Each
 * write goes through the owner-gated backend endpoints (ownership stamped from
 * the token, enforced by RLS). Progressive disclosure: pick a business → manage
 * its services → pick a service → manage its resources + slots.
 */
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isApiError } from "@/api/errors";
import {
  createProvider,
  createResource,
  createService,
  createSlot,
  getMyProviders,
  getResources,
  getServices,
} from "@/api";
import type { BookingModel, Provider, Resource, Service } from "@/types/domain";

const CATEGORIES = ["economy", "suv", "van", "electric", "luxury"];
const MODELS: { id: BookingModel; label: string }[] = [
  { id: "unit_selection", label: "Unit selection (many units, pick one)" },
  { id: "one_to_one", label: "One-to-one (single unit)" },
  { id: "shared_capacity", label: "Shared capacity (party size)" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function ErrorNote({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{msg}</p>;
}

const errMsg = (e: unknown) =>
  isApiError(e) ? e.message : e instanceof Error ? e.message : "Something went wrong.";

export default function OwnerDashboard() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [services, setServices] = useState<Service[] | null>(null);
  const [sid, setSid] = useState<string | null>(null);
  const [resources, setResources] = useState<Resource[] | null>(null);
  const [topError, setTopError] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    try {
      setProviders(await getMyProviders());
    } catch (e) {
      setTopError(errMsg(e));
    }
  }, []);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const loadServices = useCallback(async (providerId: string) => {
    setServices(null);
    setSid(null);
    setResources(null);
    setServices(await getServices(providerId));
  }, []);

  const loadResources = useCallback(async (serviceId: string) => {
    setResources(null);
    setResources(await getResources(serviceId));
  }, []);

  useEffect(() => {
    if (pid) loadServices(pid);
  }, [pid, loadServices]);
  useEffect(() => {
    if (sid) loadResources(sid);
  }, [sid, loadResources]);

  const selectedService = services?.find((s) => s.id === sid) ?? null;

  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold tracking-tight">Your businesses</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Create a business, add services and units, then open slots for customers to book.
      </p>
      <ErrorNote msg={topError} />

      {/* Providers */}
      <Section title="Businesses">
        {providers === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : providers.length === 0 ? (
          <p className="mb-3 text-sm text-muted-foreground">No businesses yet — create your first below.</p>
        ) : (
          <div className="mb-3 flex flex-wrap gap-2">
            {providers.map((p) => (
              <Button
                key={p.id}
                variant={p.id === pid ? "default" : "outline"}
                size="sm"
                onPress={() => setPid(p.id)}
              >
                {p.name}
              </Button>
            ))}
          </div>
        )}
        <CreateProviderForm
          onCreated={async (p) => {
            await loadProviders();
            setPid(p.id);
          }}
        />
      </Section>

      {/* Services for the selected provider */}
      {pid && (
        <Section title="Services">
          {services === null ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : services.length === 0 ? (
            <p className="mb-3 text-sm text-muted-foreground">No services yet.</p>
          ) : (
            <div className="mb-3 flex flex-wrap gap-2">
              {services.map((s) => (
                <Button
                  key={s.id}
                  variant={s.id === sid ? "default" : "outline"}
                  size="sm"
                  onPress={() => setSid(s.id)}
                >
                  {s.name}
                </Button>
              ))}
            </div>
          )}
          <CreateServiceForm providerId={pid} onCreated={() => loadServices(pid)} />
        </Section>
      )}

      {/* Resources + slots for the selected service */}
      {selectedService && (
        <Section title={`Units in “${selectedService.name}”`}>
          {resources === null ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : resources.length === 0 ? (
            <p className="mb-3 text-sm text-muted-foreground">No units yet.</p>
          ) : (
            <ul className="mb-3 space-y-2">
              {resources.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between rounded-xl border border-border bg-card px-3 py-2"
                >
                  <span className="text-sm font-medium">{r.name}</span>
                  <AddSlots resourceId={r.id} />
                </li>
              ))}
            </ul>
          )}
          <CreateResourceForm
            serviceId={selectedService.id}
            shared={selectedService.bookingModel === "shared_capacity"}
            onCreated={() => loadResources(selectedService.id)}
          />
        </Section>
      )}
    </div>
  );
}

function CardForm({ onSubmit, children, cta, busy }: {
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
  cta: string;
  busy: boolean;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4"
    >
      {children}
      <Button type="submit" size="sm" isDisabled={busy} className="self-start">
        {busy ? "Saving…" : cta}
      </Button>
    </form>
  );
}

function CreateProviderForm({ onCreated }: { onCreated: (p: Provider) => void }) {
  const [name, setName] = useState("");
  const [publicCode, setPublicCode] = useState("");
  const [categoryId, setCategoryId] = useState(CATEGORIES[0]);
  const [city, setCity] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await createProvider({
        name,
        publicCode: publicCode || undefined,
        categoryId,
        location: city ? { city, country: "", lat: 0, lng: 0 } : undefined,
      });
      setName("");
      setPublicCode("");
      setCity("");
      onCreated(p);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CardForm onSubmit={submit} cta="Create business" busy={busy}>
      <Field label="Business name">
        <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Acme Rentals" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Public code">
          <Input value={publicCode} onChange={(e) => setPublicCode(e.target.value)} placeholder="ACME-1234" />
        </Field>
        <Field label="City">
          <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Warsaw" />
        </Field>
      </div>
      <Field label="Category">
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="h-8 rounded-2xl border border-transparent bg-input/50 px-2.5 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>
      <ErrorNote msg={error} />
    </CardForm>
  );
}

function CreateServiceForm({ providerId, onCreated }: { providerId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [model, setModel] = useState<BookingModel>("unit_selection");
  const [duration, setDuration] = useState(60);
  const [maxSlots, setMaxSlots] = useState(1);
  const [price, setPrice] = useState(2000);
  const [cutoff, setCutoff] = useState(24);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createService({
        providerId,
        name,
        bookingModel: model,
        slotDurationMinutes: duration,
        minSlotsPerBooking: 1,
        maxSlotsPerBooking: Math.max(1, maxSlots),
        priceMinorUnits: price,
        currency: "EUR",
        cancellationCutoffHours: cutoff,
      });
      setName("");
      onCreated();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CardForm onSubmit={submit} cta="Add service" busy={busy}>
      <Field label="Service name">
        <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Compact class" />
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
        <Field label="Slot duration (min)">
          <Input type="number" value={String(duration)} onChange={(e) => setDuration(+e.target.value)} />
        </Field>
        <Field label="Max slots / booking">
          <Input type="number" value={String(maxSlots)} onChange={(e) => setMaxSlots(+e.target.value)} />
        </Field>
        <Field label="Price (minor units)">
          <Input type="number" value={String(price)} onChange={(e) => setPrice(+e.target.value)} />
        </Field>
        <Field label="Cancel cutoff (h)">
          <Input type="number" value={String(cutoff)} onChange={(e) => setCutoff(+e.target.value)} />
        </Field>
      </div>
      <ErrorNote msg={error} />
    </CardForm>
  );
}

function CreateResourceForm({ serviceId, shared, onCreated }: {
  serviceId: string;
  shared: boolean;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [capacity, setCapacity] = useState(shared ? 10 : 1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createResource({ serviceId, name, capacity: Math.max(1, capacity) });
      setName("");
      onCreated();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CardForm onSubmit={submit} cta="Add unit" busy={busy}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Unit name">
          <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Unit A-1" />
        </Field>
        <Field label={shared ? "Capacity (seats)" : "Capacity"}>
          <Input type="number" value={String(capacity)} onChange={(e) => setCapacity(+e.target.value)} />
        </Field>
      </div>
      <ErrorNote msg={error} />
    </CardForm>
  );
}

function AddSlots({ resourceId }: { resourceId: string }) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("09:00");
  const [days, setDays] = useState(5);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function add() {
    if (!date) return;
    setBusy(true);
    setMsg(null);
    try {
      let created = 0;
      for (let i = 0; i < Math.max(1, days); i++) {
        const d = new Date(`${date}T${time}:00`);
        d.setDate(d.getDate() + i);
        await createSlot({ resourceId, startsAt: d.toISOString() });
        created++;
      }
      setMsg(`Added ${created} slot${created === 1 ? "" : "s"}.`);
    } catch (e) {
      setMsg(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button variant="ghost" size="xs" onPress={() => setOpen(true)}>
        Add slots
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        className="h-7 rounded-xl border border-border bg-input/50 px-2 text-xs"
      />
      <input
        type="time"
        value={time}
        onChange={(e) => setTime(e.target.value)}
        className="h-7 rounded-xl border border-border bg-input/50 px-2 text-xs"
      />
      <input
        type="number"
        value={String(days)}
        onChange={(e) => setDays(+e.target.value)}
        className="h-7 w-14 rounded-xl border border-border bg-input/50 px-2 text-xs"
        title="days"
      />
      <Button size="xs" isDisabled={busy} onPress={add}>
        {busy ? "…" : "Go"}
      </Button>
      {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
    </div>
  );
}
