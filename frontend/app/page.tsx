"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Term, useDomain } from "@/lib/domain";
import { useAuth } from "@/lib/auth";
import { api, type Resource, type SlotOccupancy } from "@/lib/api";

export default function LandingPage() {
  const { copy } = useDomain();
  const { user } = useAuth();
  const [resources, setResources] = useState<Resource[]>([]);
  const [slots, setSlots] = useState<SlotOccupancy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listResources(), api.slotOccupancy()])
      .then(([r, s]) => {
        setResources(r);
        setSlots(s);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

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

      <div className="mt-6 flex flex-wrap items-center gap-2">
        {user ? (
          <>
            <Link
              href="/dashboard"
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Go to your dashboard
            </Link>
            <span className="text-sm text-gray-500">Signed in as {user.email}</span>
          </>
        ) : (
          <>
            <Link
              href="/login"
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Sign in
            </Link>
            <Link
              href="/login"
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Create account
            </Link>
          </>
        )}
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Sign in to book and manage your <Term term="booking" plural />.
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

      <p className="mt-10 text-xs text-gray-400">
        Are you the <Term term="admin" />?{" "}
        {user ? (
          <Link href="/owner" className="underline hover:text-gray-600">
            Manage <Term term="resources" /> &amp; <Term term="slot" plural />
          </Link>
        ) : (
          <Link href="/owner/register" className="underline hover:text-gray-600">
            Register as a professional
          </Link>
        )}
      </p>
    </main>
  );
}
