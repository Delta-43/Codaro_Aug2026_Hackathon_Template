"use client";

/**
 * Owner dashboard — set up a business end to end and manage it: create/edit/
 * delete a provider, its services (with per-service rules), its units, and open
 * slots. Every write goes through the owner-gated backend endpoints (ownership
 * stamped from the token, enforced by RLS). Progressive disclosure: pick a
 * business → manage its services → pick a service → manage its units + slots.
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
  deleteProvider,
  deleteResource,
  deleteService,
  getMyProviders,
  getResourceAnalytics,
  getResourceBookings,
  getResources,
  getServices,
  updateProvider,
  updateResource,
  updateService,
  type OwnerBooking,
  type ResourceAnalytics,
} from "@/api";
import type { BookingModel, Provider, Resource, Service } from "@/types/domain";

const CATEGORIES = ["economy", "suv", "van", "electric", "luxury"];
const MODELS: { id: BookingModel; label: string }[] = [
  { id: "unit_selection", label: "Unit selection (many units, pick one)" },
  { id: "one_to_one", label: "One-to-one (single unit)" },
  { id: "shared_capacity", label: "Shared capacity (party size)" },
];
const modelLabel = (m: BookingModel) => MODELS.find((x) => x.id === m)?.label ?? m;

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

/** Inline "are you sure?" — two-step so a stray click never deletes. */
function ConfirmDelete({ what, onConfirm }: { what: string; onConfirm: () => Promise<void> }) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (e) {
      setError(errMsg(e));
      setBusy(false);
    }
  }

  if (!armed) {
    return (
      <Button variant="destructive" size="xs" onPress={() => setArmed(true)}>
        Delete
      </Button>
    );
  }
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-xs text-muted-foreground">Delete {what}?</span>
      <Button variant="destructive" size="xs" isDisabled={busy} onPress={go}>
        {busy ? "…" : "Yes"}
      </Button>
      <Button variant="ghost" size="xs" isDisabled={busy} onPress={() => setArmed(false)}>
        No
      </Button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </span>
  );
}

export default function OwnerDashboard() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [editingProvider, setEditingProvider] = useState(false);
  const [services, setServices] = useState<Service[] | null>(null);
  const [sid, setSid] = useState<string | null>(null);
  const [editingService, setEditingService] = useState(false);
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

  const selectedProvider = providers?.find((p) => p.id === pid) ?? null;
  const selectedService = services?.find((s) => s.id === sid) ?? null;

  async function onProviderDeleted(id: string) {
    if (id === pid) {
      setPid(null);
      setServices(null);
      setSid(null);
      setResources(null);
    }
    await loadProviders();
  }

  async function onServiceDeleted(id: string) {
    if (id === sid) {
      setSid(null);
      setResources(null);
    }
    if (pid) await loadServices(pid);
  }

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
                onPress={() => {
                  setEditingProvider(false);
                  setPid(p.id);
                }}
              >
                {p.name}
              </Button>
            ))}
          </div>
        )}

        {selectedProvider && !editingProvider && (
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              Managing <span className="font-medium text-foreground">{selectedProvider.name}</span>
            </span>
            <Button variant="ghost" size="xs" onPress={() => setEditingProvider(true)}>
              Edit
            </Button>
            <ConfirmDelete
              what="this business and everything under it"
              onConfirm={async () => {
                await deleteProvider(selectedProvider.id);
                await onProviderDeleted(selectedProvider.id);
              }}
            />
          </div>
        )}

        {/* Distinct keys so React remounts on create↔edit switch (otherwise the
            same component instance keeps its stale useState-initialised fields). */}
        {selectedProvider && editingProvider ? (
          <ProviderForm
            key={`edit-${selectedProvider.id}`}
            initial={selectedProvider}
            onSaved={async () => {
              setEditingProvider(false);
              await loadProviders();
            }}
            onCancel={() => setEditingProvider(false)}
          />
        ) : (
          <ProviderForm
            key="create"
            onSaved={async (p) => {
              await loadProviders();
              setPid(p.id);
            }}
          />
        )}
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
                  onPress={() => {
                    setEditingService(false);
                    setSid(s.id);
                  }}
                >
                  {s.name}
                </Button>
              ))}
            </div>
          )}

          {selectedService && !editingService && (
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Managing <span className="font-medium text-foreground">{selectedService.name}</span>
              </span>
              <Button variant="ghost" size="xs" onPress={() => setEditingService(true)}>
                Edit
              </Button>
              <ConfirmDelete
                what="this service and its units"
                onConfirm={async () => {
                  await deleteService(selectedService.id);
                  await onServiceDeleted(selectedService.id);
                }}
              />
            </div>
          )}

          {selectedService && editingService ? (
            <ServiceForm
              key={`edit-${selectedService.id}`}
              providerId={pid}
              initial={selectedService}
              onSaved={async () => {
                setEditingService(false);
                await loadServices(pid);
              }}
              onCancel={() => setEditingService(false)}
            />
          ) : (
            <ServiceForm key="create" providerId={pid} onSaved={() => loadServices(pid)} />
          )}
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
                <UnitRow
                  key={r.id}
                  resource={r}
                  shared={selectedService.bookingModel === "shared_capacity"}
                  onChanged={() => loadResources(selectedService.id)}
                />
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

function CardForm({ onSubmit, children, cta, busy, onCancel }: {
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
  cta: string;
  busy: boolean;
  onCancel?: () => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4"
    >
      {children}
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" isDisabled={busy}>
          {busy ? "Saving…" : cta}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" size="sm" isDisabled={busy} onPress={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

/** Create (no `initial`) or edit (with `initial`) a business. */
function ProviderForm({ initial, onSaved, onCancel }: {
  initial?: Provider;
  onSaved: (p: Provider) => void;
  onCancel?: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [publicCode, setPublicCode] = useState(initial?.publicCode ?? "");
  const [categoryId, setCategoryId] = useState(initial?.categoryId || CATEGORIES[0]);
  const [city, setCity] = useState(initial?.location.city ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = {
        name,
        publicCode: publicCode || undefined,
        categoryId,
        location: city
          ? { city, country: initial?.location.country ?? "", lat: initial?.location.lat ?? 0, lng: initial?.location.lng ?? 0 }
          : undefined,
      };
      const p = initial ? await updateProvider(initial.id, body) : await createProvider(body);
      if (!initial) {
        setName("");
        setPublicCode("");
        setCity("");
      }
      onSaved(p);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CardForm onSubmit={submit} cta={initial ? "Save changes" : "Create business"} busy={busy} onCancel={onCancel}>
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

/** Create (no `initial`) or edit (with `initial`) a service. The booking model
 *  is fixed after creation (changing it would break existing bookings). */
function ServiceForm({ providerId, initial, onSaved, onCancel }: {
  providerId: string;
  initial?: Service;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [model, setModel] = useState<BookingModel>(initial?.bookingModel ?? "unit_selection");
  const [duration, setDuration] = useState(initial?.slotDurationMinutes ?? 60);
  const [maxSlots, setMaxSlots] = useState(initial?.maxSlotsPerBooking ?? 1);
  const [price, setPrice] = useState(initial?.priceMinorUnits ?? 2000);
  const [cutoff, setCutoff] = useState(initial?.cancellationCutoffHours ?? 24);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (initial) {
        await updateService(initial.id, {
          name,
          slotDurationMinutes: duration,
          maxSlotsPerBooking: Math.max(1, maxSlots),
          priceMinorUnits: price,
          cancellationCutoffHours: cutoff,
        });
      } else {
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
      }
      onSaved();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <CardForm onSubmit={submit} cta={initial ? "Save changes" : "Add service"} busy={busy} onCancel={onCancel}>
      <Field label="Service name">
        <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Compact class" />
      </Field>
      <Field label="Booking model">
        {initial ? (
          <p className="text-sm text-muted-foreground">{modelLabel(model)} (fixed)</p>
        ) : (
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
        )}
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

const STATUS_CLASS: Record<string, string> = {
  confirmed: "text-primary",
  completed: "text-muted-foreground",
  cancelled: "text-destructive",
};

function UnitRow({ resource, shared, onChanged }: {
  resource: Resource;
  shared: boolean;
  onChanged: () => void;
}) {
  const [stats, setStats] = useState<ResourceAnalytics | null>(null);
  const [bookings, setBookings] = useState<OwnerBooking[] | null>(null);
  const [showBookings, setShowBookings] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      setStats(await getResourceAnalytics(resource.id));
    } catch {
      /* analytics is best-effort; leave the row without stats */
    }
  }, [resource.id]);
  useEffect(() => {
    load();
  }, [load]);

  const loadBookings = useCallback(async () => {
    try {
      setBookings(await getResourceBookings(resource.id));
    } catch {
      setBookings([]);
    }
  }, [resource.id]);

  async function toggleBookings() {
    const next = !showBookings;
    setShowBookings(next);
    if (next && bookings === null) await loadBookings();
  }

  return (
    <li className="rounded-xl border border-border bg-card px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">{resource.name}</span>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="xs" onPress={() => setEditing((v) => !v)}>
            {editing ? "Close" : "Edit"}
          </Button>
          <Button variant="ghost" size="xs" onPress={toggleBookings}>
            {showBookings ? "Hide" : "Bookings"}
          </Button>
          <AddSlots
            resourceId={resource.id}
            onAdded={() => {
              load();
              if (showBookings) loadBookings();
            }}
          />
          <ConfirmDelete
            what="this unit and its slots"
            onConfirm={async () => {
              await deleteResource(resource.id);
              onChanged();
            }}
          />
        </div>
      </div>
      {stats && !editing && (
        <p className="mt-1 text-xs text-muted-foreground">
          {stats.total_slots} slot{stats.total_slots === 1 ? "" : "s"} ·{" "}
          {Math.round((stats.occupancy_rate || 0) * 100)}% booked · {stats.booked_count}/
          {stats.total_capacity} seats
        </p>
      )}
      {editing && (
        <UnitEdit
          resource={resource}
          shared={shared}
          onSaved={() => {
            setEditing(false);
            onChanged();
          }}
        />
      )}
      {showBookings && (
        <ul className="mt-2 space-y-1 border-t border-border pt-2">
          {bookings === null ? (
            <li className="text-xs text-muted-foreground">Loading…</li>
          ) : bookings.length === 0 ? (
            <li className="text-xs text-muted-foreground">No bookings yet.</li>
          ) : (
            bookings.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
                <span className="font-medium">{b.reference}</span>
                <span className="text-muted-foreground">{b.clientEmail}</span>
                <span className="text-muted-foreground">
                  {new Date(b.startUtc).toLocaleDateString()}
                </span>
                {b.partySize > 1 && <span className="text-muted-foreground">×{b.partySize}</span>}
                <span className={STATUS_CLASS[b.status] ?? ""}>{b.status}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </li>
  );
}

function UnitEdit({ resource, shared, onSaved }: {
  resource: Resource;
  shared: boolean;
  onSaved: () => void;
}) {
  const [name, setName] = useState(resource.name);
  const [capacity, setCapacity] = useState(resource.capacity);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateResource(resource.id, { name, capacity: Math.max(1, capacity) });
      onSaved();
    } catch (e) {
      setError(errMsg(e));
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2 border-t border-border pt-2">
      <div className="flex flex-col gap-1">
        <Label className="text-xs">Name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} className="h-7 text-xs" />
      </div>
      <div className="flex flex-col gap-1">
        <Label className="text-xs">{shared ? "Capacity (seats)" : "Capacity"}</Label>
        <Input
          type="number"
          value={String(capacity)}
          onChange={(e) => setCapacity(+e.target.value)}
          className="h-7 w-24 text-xs"
        />
      </div>
      <Button size="xs" isDisabled={busy} onPress={save}>
        {busy ? "…" : "Save"}
      </Button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}

function AddSlots({ resourceId, onAdded }: { resourceId: string; onAdded?: () => void }) {
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
      onAdded?.();
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
