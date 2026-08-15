"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Term, useDomain } from "@/lib/domain";
import { ApiError, api, type Resource, type ResourceAnalytics } from "@/lib/api";

/** A datetime-local value (local wall-clock, no offset) `hours` from now,
 *  formatted YYYY-MM-DDTHH:mm. `new Date(value)` parses it as local time, so
 *  `.toISOString()` at submit converts to the UTC the backend stores. */
function defaultSlotStart(hours = 48): string {
  const d = new Date(Date.now() + hours * 3_600_000);
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Build a metadata object from the config-declared fields, coercing to the
 *  declared type. Empty optional fields are skipped -- the `metadata jsonb`
 *  column is the extension point, so we never send blank keys. */
function buildMetadata(
  fields: Array<{ key: string; label: string; type: string }>,
  values: Record<string, string | boolean>
): Record<string, unknown> {
  const meta: Record<string, unknown> = {};
  for (const f of fields) {
    const v = values[f.key];
    if (f.type === "boolean") {
      if (v) meta[f.key] = true;
      continue;
    }
    if (v === undefined || v === "") continue;
    meta[f.key] = f.type === "number" ? Number(v) : v;
  }
  return meta;
}

export default function OwnerDashboard() {
  const { terms, rules, metaFields } = useDomain();
  const resourceMeta = metaFields.resources ?? [];

  const [resources, setResources] = useState<Resource[]>([]);
  const [analytics, setAnalytics] = useState<Record<string, ResourceAnalytics>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Create-resource form.
  const [rName, setRName] = useState("");
  const [rDesc, setRDesc] = useState("");
  const [rMeta, setRMeta] = useState<Record<string, string | boolean>>({});

  // Create-slot form.
  const [slotResource, setSlotResource] = useState("");
  const [slotStart, setSlotStart] = useState(defaultSlotStart());
  const [slotCapacity, setSlotCapacity] = useState("");

  const reload = useCallback(async () => {
    const rs = await api.listResources();
    setResources(rs);
    const entries = await Promise.all(
      rs.map(async (r) => [r.id, await api.resourceAnalytics(r.id)] as const)
    );
    setAnalytics(Object.fromEntries(entries));
  }, []);

  useEffect(() => {
    reload()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [reload]);

  // Default the slot form's resource to the first one, once loaded.
  useEffect(() => {
    if (!slotResource && resources.length > 0) setSlotResource(resources[0].id);
  }, [resources, slotResource]);

  async function run(fn: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await reload();
      setNotice(success);
    } catch (e) {
      // ApiError.detail is the backend's own message; a 422 with a structured
      // metaFields detail falls back to the request line, which is fine here.
      setError(e instanceof ApiError ? e.detail : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function submitResource(e: React.FormEvent) {
    e.preventDefault();
    if (!rName.trim()) return;
    run(async () => {
      await api.createResource({
        name: rName.trim(),
        description: rDesc.trim() || undefined,
        metadata: buildMetadata(resourceMeta, rMeta)
      });
      setRName("");
      setRDesc("");
      setRMeta({});
    }, `${terms.resource} created.`);
  }

  function submitSlot(e: React.FormEvent) {
    e.preventDefault();
    if (!slotResource || !slotStart) return;
    run(async () => {
      await api.createSlot({
        resource_id: slotResource,
        starts_at: new Date(slotStart).toISOString(),
        capacity: slotCapacity ? Number(slotCapacity) : undefined
      });
      setSlotStart(defaultSlotStart());
      setSlotCapacity("");
    }, `${terms.slot} created.`);
  }

  const inputClass = "w-full rounded border border-gray-300 px-3 py-2 text-sm";
  const durationMinutes = rules.slotDurationMinutes;
  const defaultCapacity = rules.maxBookingsPerSlot;

  if (loading) return <main className="mx-auto max-w-3xl p-8 text-sm text-gray-500">Loading...</main>;

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">
          <Term term="admin" /> dashboard
        </h1>
        <Link href="/" className="text-sm text-gray-500 underline hover:text-gray-800">
          Public page
        </Link>
      </div>
      <p className="mt-1 text-sm text-gray-600">
        Set up your <Term term="resources" /> and open <Term term="slot" plural />, then watch
        them fill up.
      </p>

      {error && (
        <p role="alert" className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p className="mt-4 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
          {notice}
        </p>
      )}

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {/* -- Create resource -------------------------------------------- */}
        <form onSubmit={submitResource} className="rounded border border-gray-200 p-4">
          <h2 className="text-lg font-medium">
            New <Term term="resource" />
          </h2>
          <div className="mt-3 space-y-3">
            <input
              value={rName}
              onChange={(e) => setRName(e.target.value)}
              placeholder={`${terms.resource} name`}
              aria-label={`${terms.resource} name`}
              required
              className={inputClass}
            />
            <input
              value={rDesc}
              onChange={(e) => setRDesc(e.target.value)}
              placeholder="Description (optional)"
              aria-label="Description"
              className={inputClass}
            />
            {/* Config-driven: these inputs appear only because the current
                domain declares them in metaFields.resources. */}
            {resourceMeta.map((f) =>
              f.type === "boolean" ? (
                <label key={f.key} className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={Boolean(rMeta[f.key])}
                    onChange={(e) => setRMeta((m) => ({ ...m, [f.key]: e.target.checked }))}
                  />
                  {f.label}
                </label>
              ) : (
                <input
                  key={f.key}
                  type={f.type === "number" ? "number" : "text"}
                  value={(rMeta[f.key] as string) ?? ""}
                  onChange={(e) => setRMeta((m) => ({ ...m, [f.key]: e.target.value }))}
                  placeholder={f.label}
                  aria-label={f.label}
                  className={inputClass}
                />
              )
            )}
          </div>
          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? "..." : `Add ${terms.resource}`}
          </button>
        </form>

        {/* -- Create slot ------------------------------------------------ */}
        <form onSubmit={submitSlot} className="rounded border border-gray-200 p-4">
          <h2 className="text-lg font-medium">
            New <Term term="slot" />
          </h2>
          <div className="mt-3 space-y-3">
            <select
              value={slotResource}
              onChange={(e) => setSlotResource(e.target.value)}
              aria-label={terms.resource}
              disabled={resources.length === 0}
              className={inputClass}
            >
              {resources.length === 0 ? (
                <option value="">No {terms.resources.toLowerCase()} yet</option>
              ) : (
                resources.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))
              )}
            </select>
            <label className="block text-xs text-gray-500">
              Starts at
              <input
                type="datetime-local"
                value={slotStart}
                onChange={(e) => setSlotStart(e.target.value)}
                aria-label="Starts at"
                required
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <input
              type="number"
              min={1}
              value={slotCapacity}
              onChange={(e) => setSlotCapacity(e.target.value)}
              placeholder={`Capacity (default ${defaultCapacity})`}
              aria-label="Capacity"
              className={inputClass}
            />
            <p className="text-xs text-gray-500">
              Ends {durationMinutes} min later (from rules.slotDurationMinutes).
            </p>
          </div>
          <button
            type="submit"
            disabled={busy || resources.length === 0}
            className="mt-4 rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? "..." : `Add ${terms.slot}`}
          </button>
        </form>
      </div>

      {/* -- Resources + analytics ---------------------------------------- */}
      <section className="mt-10">
        <h2 className="text-lg font-medium">
          Your <Term term="resource" plural />
        </h2>
        {resources.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">
            No <Term term="resources" /> yet. Add one above to get started.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {resources.map((r) => {
              const a = analytics[r.id];
              const rate = a ? Math.round(a.occupancy_rate * 100) : 0;
              return (
                <li key={r.id} className="rounded border border-gray-200 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{r.name}</p>
                      {r.description && <p className="mt-1 text-sm text-gray-600">{r.description}</p>}
                      {Object.keys(r.metadata ?? {}).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {Object.entries(r.metadata).map(([k, v]) => (
                            <span
                              key={k}
                              className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                            >
                              {k}: {String(v)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {a && (
                      <div className="text-right">
                        <p className="text-2xl font-semibold text-indigo-600">{rate}%</p>
                        <p className="text-xs text-gray-500">
                          {a.booked_count}/{a.total_capacity} booked · {a.total_slots}{" "}
                          <Term term="slot" plural={a.total_slots !== 1} />
                        </p>
                      </div>
                    )}
                  </div>
                  {a && Object.keys(a.bookings_by_status).length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {Object.entries(a.bookings_by_status).map(([status, count]) => (
                        <span
                          key={status}
                          className="rounded-full border border-gray-200 px-2 py-0.5 text-xs text-gray-600"
                        >
                          {count} {status}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
