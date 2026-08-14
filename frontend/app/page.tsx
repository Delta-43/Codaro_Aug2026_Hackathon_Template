"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Term, useDomain } from "@/lib/domain";
import { api, type Resource, type SlotOccupancy } from "@/lib/api";
import { getClientEmail, setClientEmail } from "@/lib/session";

export default function LandingPage() {
  const { copy } = useDomain();
  const router = useRouter();
  const [resources, setResources] = useState<Resource[]>([]);
  const [slots, setSlots] = useState<SlotOccupancy[]>([]);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Prefill with whoever was identified last so a returning visitor just
    // hits Continue.
    setEmail(getClientEmail() ?? "");
    Promise.all([api.listResources(), api.slotOccupancy()])
      .then(([r, s]) => {
        setResources(r);
        setSlots(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function identify(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setClientEmail(email);
    router.push("/dashboard");
  }

  // Open slots per resource, so the showcase says something useful rather than
  // just listing names.
  const openByResource = new Map<string, number>();
  for (const s of slots) {
    if (s.available_count > 0) {
      openByResource.set(s.resource_id, (openByResource.get(s.resource_id) ?? 0) + 1);
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">{copy.landingTitle}</h1>
      <p className="mt-1 text-gray-600">{copy.landingSubtitle}</p>

      <form onSubmit={identify} className="mt-6 flex flex-wrap gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="Email"
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Continue
        </button>
      </form>
      <p className="mt-1 text-xs text-gray-500">
        No password needed. Your email identifies your <Term term="booking" plural />.
      </p>

      <section className="mt-10">
        <h2 className="text-lg font-medium">
          Available <Term term="resource" plural />
        </h2>
        {loading ? (
          <p className="mt-2 text-sm text-gray-500">Loading...</p>
        ) : resources.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">{copy.emptyStateSlots}</p>
        ) : (
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {resources.map((r) => {
              const open = openByResource.get(r.id) ?? 0;
              return (
                <li key={r.id} className="rounded border border-gray-200 p-4">
                  <p className="font-medium">{r.name}</p>
                  {r.description && <p className="mt-1 text-sm text-gray-600">{r.description}</p>}
                  <p className="mt-2 text-sm text-gray-500">
                    {open} open <Term term="slot" plural={open !== 1} />
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
